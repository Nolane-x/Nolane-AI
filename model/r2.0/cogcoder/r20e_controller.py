from __future__ import annotations

import hashlib
import random

import torch

from .neural_system2 import encode_action_descriptions, encode_structured_observation, structured_numeric_delta_sketch
from .r18_causal_memory import ConditionalEvidenceMemory, public_context_fingerprint
from .r18_training import _public_state
from .r19_frontier import FrontierRolloutHead
from .neural_system2 import NeuralSystem2Workspace
from .r20e_executive import EvidenceEffectExecutive
from .r20e_imagination import EvidenceConditionedImaginationPlanner
from .r20e_training import _action_memory, _evidence_tensors, _imagined_tensors

_MODES = {"random", "greedy_parent", "fixed_depth_1", "fixed_depth_2", "fixed_depth_8", "adaptive"}


def run_r20e_episode(
    parent: NeuralSystem2Workspace,
    rollout: FrontierRolloutHead,
    executive: EvidenceEffectExecutive,
    task,
    *,
    mode: str = "fixed_depth_2",
    random_repeat: int = 0,
    beam_width: int = 1,
) -> dict[str, object]:
    if mode not in _MODES:
        raise ValueError(f"mode must be one of {sorted(_MODES)}")
    descriptions = tuple(str(x) for x in task.action_descriptions)
    action_count = len(descriptions)
    actions_taken: list[int] = []
    depths_used: list[int] = []

    if mode == "random":
        rng = random.Random(int.from_bytes(hashlib.sha256(f"{task.task_id}|r20e|{int(random_repeat)}".encode()).digest()[:8], "big"))
        while not task.done:
            chosen = rng.randrange(action_count)
            actions_taken.append(chosen)
            task.step(chosen)
        return {"task_id": task.task_id, "family": task.family, "mode": mode, "solved": bool(task.solved), "done": bool(task.done), "steps": len(actions_taken), "actions": actions_taken, "depths_used": depths_used}

    parent.eval(); rollout.eval(); executive.eval()
    planner = EvidenceConditionedImaginationPlanner(parent, rollout, beam_width=beam_width)
    tokens = encode_action_descriptions(descriptions, max_bytes=64).unsqueeze(0)
    with torch.no_grad():
        action_embeddings = parent.action_encoder(tokens)[0].detach().cpu()
    evidence_memory = ConditionalEvidenceMemory(action_count=action_count, effect_dim=parent.psr_sketch_dim)
    last_progress = [0.0] * action_count
    progress_counts = [0] * action_count
    last_information = [0.0] * action_count
    failures = [0] * action_count
    attempts = [0] * action_count
    previous_feedback = torch.zeros(3, dtype=torch.float32)
    initial_budget = max(1.0, float(task.observe()["budget_remaining"]))
    recurrent = executive.init_state(batch_size=1)

    while not task.done:
        obs = task.observe()
        before_text = task.render_observation()
        before_ids, before_values, state = _public_state(before_text, sketch_dim=parent.psr_sketch_dim)
        context = public_context_fingerprint(before_text, dims=parent.conditional_law_context_dim)
        evidence_effects, evidence_meta, lookups = _evidence_tensors(evidence_memory, context, action_count)
        parent_effects = planner.parent_effects(state, context, action_embeddings, evidence_effects, evidence_meta).detach().cpu()
        memory_features = _action_memory(lookups, last_progress=last_progress, progress_counts=progress_counts, last_information=last_information, failures=failures, attempts=attempts)

        if mode == "greedy_parent":
            impact = parent_effects.square().mean(dim=-1).sqrt()
            chosen = min(range(action_count), key=lambda idx: (-float(impact[idx].item()), idx))
            depth = 1
        else:
            if mode.startswith("fixed_depth_"):
                depth = int(mode.rsplit("_", 1)[1])
            else:
                # First pass at depth 1 estimates compute allocation.  The state
                # transition is not committed until the chosen-depth pass.
                im1, un1, val1 = _imagined_tensors(planner, state=state, context=context, action_embeddings=action_embeddings, evidence_effects=evidence_effects, evidence_meta=evidence_meta, depth=1)
                with torch.no_grad():
                    probe = executive(
                        state=state.unsqueeze(0), context=context.unsqueeze(0), action_embeddings=action_embeddings.unsqueeze(0), parent_effects=parent_effects.unsqueeze(0), imagined_effects=im1.unsqueeze(0), imagined_uncertainty=un1.unsqueeze(0), imagined_value=val1.unsqueeze(0), evidence_effects=evidence_effects.unsqueeze(0), action_memory=memory_features.unsqueeze(0), progress=torch.tensor([[float(obs["progress_signal"])]], dtype=torch.float32), budget_fraction=torch.tensor([[float(obs["budget_remaining"]) / initial_budget]], dtype=torch.float32), previous_feedback=previous_feedback.unsqueeze(0), recurrent_state=recurrent,
                    )
                depth = int(executive.depth_values[int(probe["depth_logits"].argmax(-1).item())])
            imagined_effects, imagined_uncertainty, imagined_value = _imagined_tensors(planner, state=state, context=context, action_embeddings=action_embeddings, evidence_effects=evidence_effects, evidence_meta=evidence_meta, depth=depth)
            with torch.no_grad():
                out = executive(
                    state=state.unsqueeze(0),
                    context=context.unsqueeze(0),
                    action_embeddings=action_embeddings.unsqueeze(0),
                    parent_effects=parent_effects.unsqueeze(0),
                    imagined_effects=imagined_effects.unsqueeze(0),
                    imagined_uncertainty=imagined_uncertainty.unsqueeze(0),
                    imagined_value=imagined_value.unsqueeze(0),
                    evidence_effects=evidence_effects.unsqueeze(0),
                    action_memory=memory_features.unsqueeze(0),
                    progress=torch.tensor([[float(obs["progress_signal"])]], dtype=torch.float32),
                    budget_fraction=torch.tensor([[float(obs["budget_remaining"]) / initial_budget]], dtype=torch.float32),
                    previous_feedback=previous_feedback.unsqueeze(0),
                    recurrent_state=recurrent,
                )
            chosen = int(out["action_logits"].argmax(-1).item())
            recurrent = out["next_state"].detach()
        depths_used.append(depth)
        actions_taken.append(chosen)
        result = task.step(chosen)
        after_ids, after_values = encode_structured_observation(task.render_observation(), max_atoms=96)
        observed = structured_numeric_delta_sketch(before_ids, before_values, after_ids.unsqueeze(0), after_values.unsqueeze(0), sketch_dim=parent.psr_sketch_dim).squeeze(0).detach().cpu()
        evidence_memory.update(chosen, context, state, observed)
        attempts[chosen] += 1
        last_progress[chosen] = float(result.progress_delta)
        progress_counts[chosen] += 1
        last_information[chosen] = float(result.information_gain)
        failures[chosen] += int(result.failed)
        previous_feedback = torch.tensor([float(result.progress_delta), float(result.information_gain), float(result.failed)], dtype=torch.float32)

    return {
        "task_id": task.task_id,
        "family": task.family,
        "mode": mode,
        "solved": bool(task.solved),
        "done": bool(task.done),
        "steps": len(actions_taken),
        "actions": actions_taken,
        "depths_used": depths_used,
    }
