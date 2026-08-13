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
    beam_trace: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class ImaginationResult:
    depths: tuple[int, ...]
    by_depth: dict[int, tuple[ActionImagination, ...]]
    parameter_count: int = 0
    used_hidden_task_fields: bool = False


@dataclass
class _Node:
    actions: tuple[int, ...]
    state: Tensor
    cumulative_effect: Tensor
    score: float
    uncertainty: float
    value: float


class RecursiveImaginationPlanner:
    """Parameter-free recursive search over the frozen R1.9 world-model."""

    def __init__(self, parent: NeuralSystem2Workspace, rollout: FrontierRolloutHead, *, beam_width: int = 3, uncertainty_penalty: float = 0.15) -> None:
        if beam_width < 1:
            raise ValueError("beam_width must be positive")
        self.parent = parent
        self.rollout = rollout
        self.beam_width = int(beam_width)
        self.uncertainty_penalty = float(uncertainty_penalty)
        self.parent.eval()
        self.rollout.eval()

    def _validate(self, state: Tensor, context: Tensor, action_embeddings: Tensor, legal_actions: Iterable[int], depths: Iterable[int]) -> tuple[tuple[int, ...], tuple[int, ...]]:
        if state.ndim != 1 or state.shape[0] != self.parent.psr_sketch_dim:
            raise ValueError("state must be a single public state sketch")
        if context.ndim != 1 or context.shape[0] != self.parent.conditional_law_context_dim:
            raise ValueError("context must be a single public context fingerprint")
        if action_embeddings.ndim != 2 or action_embeddings.shape[1] != self.parent.workspace_dim:
            raise ValueError("action_embeddings must be [actions, workspace_dim]")
        legal = tuple(dict.fromkeys(int(index) for index in legal_actions))
        if not legal:
            raise ValueError("legal_actions cannot be empty")
        if min(legal) < 0 or max(legal) >= action_embeddings.shape[0]:
            raise ValueError("legal action index outside action embedding rows")
        wanted = tuple(dict.fromkeys(int(depth) for depth in depths))
        if not wanted or any(depth not in _LOCKED_DEPTHS for depth in wanted):
            raise ValueError(f"depths must be chosen from {_LOCKED_DEPTHS}")
        return legal, wanted

    def _parent_effects(self, states: Tensor, contexts: Tensor, action_embeddings: Tensor) -> Tensor:
        if states.ndim == 1:
            states = states.unsqueeze(0)
        if contexts.ndim == 1:
            contexts = contexts.unsqueeze(0)
        batch = states.shape[0]
        actions = action_embeddings.shape[0]
        action_batch = action_embeddings.unsqueeze(0).expand(batch, -1, -1)
        evidence = torch.zeros(batch, actions, self.parent.psr_sketch_dim, dtype=states.dtype)
        meta = torch.zeros(batch, actions, 3, dtype=states.dtype)
        with torch.no_grad():
            out = self.parent.conditional_law_scores(states, contexts, action_batch, evidence, meta)
        return out["predicted_effect"].detach()

    @staticmethod
    def _impact_score(effect: Tensor) -> Tensor:
        return effect.square().mean(dim=-1).sqrt()

    def _expand_one(self, node: _Node, context: Tensor, action_embeddings: Tensor, legal: tuple[int, ...]) -> list[_Node]:
        effects = self._parent_effects(node.state, context, action_embeddings)[0]
        selected = effects[list(legal)]
        impact = self._impact_score(selected)
        rows: list[_Node] = []
        for offset, action in enumerate(legal):
            effect = selected[offset]
            rows.append(_Node(actions=node.actions + (action,), state=(node.state + effect).detach(), cumulative_effect=(node.cumulative_effect + effect).detach(), score=node.score + float(impact[offset].item()), uncertainty=node.uncertainty, value=node.value))
        return rows

    def _expand_two(self, node: _Node, context: Tensor, action_embeddings: Tensor, legal: tuple[int, ...]) -> list[_Node]:
        first_all = self._parent_effects(node.state, context, action_embeddings)[0]
        legal_index = torch.tensor(legal, dtype=torch.long)
        first = first_all.index_select(0, legal_index)
        mid_states = node.state.unsqueeze(0) + first
        mid_contexts = context.unsqueeze(0).expand(len(legal), -1)
        second_all = self._parent_effects(mid_states, mid_contexts, action_embeddings)
        second = second_all.index_select(1, legal_index)
        pair_actions = []
        pair_parent = []
        pair_indices: list[tuple[int, int]] = []
        for i, first_action in enumerate(legal):
            for j, second_action in enumerate(legal):
                pair_actions.append(torch.stack((action_embeddings[first_action], action_embeddings[second_action])))
                pair_parent.append(torch.stack((first[i], second[i, j])))
                pair_indices.append((first_action, second_action))
        actions_tensor = torch.stack(pair_actions)
        parent_tensor = torch.stack(pair_parent)
        state_batch = node.state.unsqueeze(0).expand(len(pair_indices), -1)
        context_batch = context.unsqueeze(0).expand(len(pair_indices), -1)
        with torch.no_grad():
            out = self.rollout(state_batch, context_batch, actions_tensor, parent_tensor)
        predicted = out["predicted_effect"].detach()
        uncertainty = out["uncertainty"].detach().clamp(0.0, 1.0)
        value = out["value"].detach()
        impact = self._impact_score(predicted)
        combined_score = impact - self.uncertainty_penalty * uncertainty
        rows: list[_Node] = []
        for index, pair in enumerate(pair_indices):
            effect = predicted[index]
            rows.append(_Node(actions=node.actions + pair, state=(node.state + effect).detach(), cumulative_effect=(node.cumulative_effect + effect).detach(), score=node.score + float(combined_score[index].item()), uncertainty=max(node.uncertainty, float(uncertainty[index].item())), value=node.value + float(value[index].item())))
        return rows

    @staticmethod
    def _public_row(node: _Node, beam: list[_Node]) -> ActionImagination:
        return ActionImagination(first_action=int(node.actions[0]), actions=tuple(int(item) for item in node.actions), score=float(node.score), uncertainty=float(min(1.0, max(0.0, node.uncertainty))), value=float(node.value), effect=tuple(float(item) for item in node.cumulative_effect.cpu().tolist()), final_state=tuple(float(item) for item in node.state.cpu().tolist()), beam_trace=tuple(tuple(int(item) for item in candidate.actions) for candidate in beam))

    def imagine_actions(self, *, state: Tensor, context: Tensor, action_embeddings: Tensor, legal_actions: Iterable[int], depths: Iterable[int] = _LOCKED_DEPTHS) -> ImaginationResult:
        legal, wanted = self._validate(state, context, action_embeddings, legal_actions, depths)
        by_depth: dict[int, tuple[ActionImagination, ...]] = {}
        for depth in wanted:
            rows: list[ActionImagination] = []
            for first_action in legal:
                root = _Node((), state.detach(), torch.zeros_like(state), 0.0, 0.0, 0.0)
                beam = self._expand_one(root, context, action_embeddings, (first_action,))
                remaining = depth - 1
                if remaining % 2 == 1:
                    candidates: list[_Node] = []
                    for node in beam:
                        candidates.extend(self._expand_one(node, context, action_embeddings, legal))
                    candidates.sort(key=lambda row: (-row.score, row.actions))
                    beam = candidates[: self.beam_width]
                    remaining -= 1
                while remaining > 0:
                    candidates = []
                    for node in beam:
                        candidates.extend(self._expand_two(node, context, action_embeddings, legal))
                    candidates.sort(key=lambda row: (-row.score, row.actions))
                    beam = candidates[: self.beam_width]
                    remaining -= 2
                best = sorted(beam, key=lambda row: (-row.score, row.actions))[0]
                rows.append(self._public_row(best, beam))
            rows.sort(key=lambda row: row.first_action)
            by_depth[depth] = tuple(rows)
        return ImaginationResult(depths=wanted, by_depth=by_depth)
