from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import torch
from torch import Tensor

from .neural_system2 import NeuralSystem2Workspace
from .r19_frontier import FrontierRolloutHead

_LOCKED_DEPTHS = (1, 2, 4, 8, 16)


@dataclass(frozen=True)
class ActionImagination:
    first_action: int
    actions: tuple[int, ...]
    score: float
    uncertainty: float
    value: float
    effect: tuple[float, ...]
    final_state: tuple[float, ...]


@dataclass(frozen=True)
class ImaginationResult:
    depths: tuple[int, ...]
    by_depth: dict[int, tuple[ActionImagination, ...]]
    parameter_count: int = 0
    used_hidden_task_fields: bool = False


class EvidenceConditionedImaginationPlanner:
    """Parameter-free search over the frozen R1.9 model using observed evidence.

    Evidence is held fixed during counterfactual simulation because imagined
    transitions are not observations.  It is refreshed only after a real
    environment step by the closed-loop controller.
    """

    def __init__(
        self,
        parent: NeuralSystem2Workspace,
        rollout: FrontierRolloutHead,
        *,
        beam_width: int = 1,
        uncertainty_penalty: float = 0.15,
    ) -> None:
        if beam_width < 1:
            raise ValueError("beam_width must be positive")
        self.parent = parent.eval()
        self.rollout = rollout.eval()
        self.beam_width = int(beam_width)
        self.uncertainty_penalty = float(uncertainty_penalty)
        self.parameter_count = 0

    def parent_effects(
        self,
        state: Tensor,
        context: Tensor,
        action_embeddings: Tensor,
        evidence_effects: Tensor,
        evidence_meta: Tensor,
    ) -> Tensor:
        if state.ndim == 1:
            state = state.unsqueeze(0)
        if context.ndim == 1:
            context = context.unsqueeze(0)
        if evidence_effects.ndim == 2:
            evidence_effects = evidence_effects.unsqueeze(0)
        if evidence_meta.ndim == 2:
            evidence_meta = evidence_meta.unsqueeze(0)
        batch = state.shape[0]
        action_batch = action_embeddings.unsqueeze(0).expand(batch, -1, -1) if action_embeddings.ndim == 2 else action_embeddings
        evidence_batch = evidence_effects.expand(batch, -1, -1) if evidence_effects.shape[0] == 1 and batch > 1 else evidence_effects
        meta_batch = evidence_meta.expand(batch, -1, -1) if evidence_meta.shape[0] == 1 and batch > 1 else evidence_meta
        with torch.no_grad():
            out = self.parent.conditional_law_scores(state, context, action_batch, evidence_batch, meta_batch)
        return out["predicted_effect"].detach().squeeze(0) if batch == 1 else out["predicted_effect"].detach()

    @staticmethod
    def _impact(effect: Tensor) -> Tensor:
        return effect.square().mean(dim=-1).sqrt()

    def _depth_one(
        self,
        state: Tensor,
        context: Tensor,
        action_embeddings: Tensor,
        evidence_effects: Tensor,
        evidence_meta: Tensor,
        legal: tuple[int, ...],
    ) -> tuple[ActionImagination, ...]:
        effects = self.parent_effects(state, context, action_embeddings, evidence_effects, evidence_meta)
        rows = []
        for action in legal:
            effect = effects[action]
            score = float(self._impact(effect).item())
            rows.append(ActionImagination(action, (action,), score, 0.0, 0.0, tuple(effect.tolist()), tuple((state + effect).tolist())))
        return tuple(rows)

    def _depth_two_from_state(
        self,
        state: Tensor,
        context: Tensor,
        action_embeddings: Tensor,
        evidence_effects: Tensor,
        evidence_meta: Tensor,
        legal: tuple[int, ...],
        first_action: int,
    ) -> ActionImagination:
        first_all = self.parent_effects(state, context, action_embeddings, evidence_effects, evidence_meta)
        first = first_all[first_action]
        mid_state = state + first
        second_all = self.parent_effects(mid_state, context, action_embeddings, evidence_effects, evidence_meta)
        programs = []
        parents = []
        second_indices = []
        for second_action in legal:
            programs.append(torch.stack((action_embeddings[first_action], action_embeddings[second_action])))
            parents.append(torch.stack((first, second_all[second_action])))
            second_indices.append(second_action)
        with torch.no_grad():
            out = self.rollout(
                state.unsqueeze(0).expand(len(programs), -1),
                context.unsqueeze(0).expand(len(programs), -1),
                torch.stack(programs),
                torch.stack(parents),
            )
        effects = out["predicted_effect"].detach()
        uncertainty = out["uncertainty"].detach().clamp(0.0, 1.0)
        value = out["value"].detach()
        scores = self._impact(effects) - self.uncertainty_penalty * uncertainty
        best_offset = min(range(len(second_indices)), key=lambda idx: (-float(scores[idx].item()), int(second_indices[idx])))
        effect = effects[best_offset]
        second = int(second_indices[best_offset])
        return ActionImagination(
            int(first_action),
            (int(first_action), second),
            float(scores[best_offset].item()),
            float(uncertainty[best_offset].item()),
            float(value[best_offset].item()),
            tuple(float(x) for x in effect.tolist()),
            tuple(float(x) for x in (state + effect).tolist()),
        )

    def imagine_actions(
        self,
        *,
        state: Tensor,
        context: Tensor,
        action_embeddings: Tensor,
        evidence_effects: Tensor,
        evidence_meta: Tensor,
        legal_actions: Iterable[int],
        depths: Iterable[int] = _LOCKED_DEPTHS,
    ) -> ImaginationResult:
        legal = tuple(dict.fromkeys(int(x) for x in legal_actions))
        wanted = tuple(dict.fromkeys(int(x) for x in depths))
        if not legal:
            raise ValueError("legal_actions cannot be empty")
        if any(depth not in _LOCKED_DEPTHS for depth in wanted):
            raise ValueError(f"depths must be chosen from {_LOCKED_DEPTHS}")
        by_depth: dict[int, tuple[ActionImagination, ...]] = {}
        depth1 = self._depth_one(state, context, action_embeddings, evidence_effects, evidence_meta, legal)
        if 1 in wanted:
            by_depth[1] = depth1
        if any(depth > 1 for depth in wanted):
            depth2 = tuple(self._depth_two_from_state(state, context, action_embeddings, evidence_effects, evidence_meta, legal, first) for first in legal)
            if 2 in wanted:
                by_depth[2] = depth2
            # For deeper budgets, recursively advance each first-action path using
            # the best public-effect continuation.  No parameters are introduced;
            # deeper compute reuses the same parent model and evidence.
            for depth in wanted:
                if depth <= 2:
                    continue
                rows = []
                for row in depth2:
                    current_state = torch.tensor(row.final_state, dtype=state.dtype)
                    cumulative = torch.tensor(row.effect, dtype=state.dtype)
                    actions = list(row.actions)
                    uncertainty = row.uncertainty
                    value = row.value
                    while len(actions) < depth:
                        effects = self.parent_effects(current_state, context, action_embeddings, evidence_effects, evidence_meta)
                        impacts = self._impact(effects[list(legal)])
                        offset = min(range(len(legal)), key=lambda idx: (-float(impacts[idx].item()), int(legal[idx])))
                        action = int(legal[offset])
                        effect = effects[action]
                        current_state = current_state + effect
                        cumulative = cumulative + effect
                        actions.append(action)
                    rows.append(ActionImagination(row.first_action, tuple(actions), float(self._impact(cumulative).item()), uncertainty, value, tuple(float(x) for x in cumulative.tolist()), tuple(float(x) for x in current_state.tolist())))
                by_depth[depth] = tuple(rows)
        return ImaginationResult(depths=wanted, by_depth=by_depth)
