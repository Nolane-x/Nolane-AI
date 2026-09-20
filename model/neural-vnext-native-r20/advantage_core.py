from __future__ import annotations

from typing import Any

import torch
from torch import Tensor, nn

from native_core import TARGET_VISIBLE_FEATURE_INDEX, state_dict_sha256
from latent_goal_core import NativeR4LatentGoalBeliefPolicy
from public_planner import GOAL_CARDINALITY, GOAL_DIMENSIONS, GOAL_HYPOTHESIS_COUNT, GOAL_TABLE

CAUSAL_FEATURE_DIM = 10


class _AdvantageScorer(nn.Module):
    def __init__(
        self,
        *,
        action_token_dim: int,
        parent_hidden_dim: int,
        goal_embedding_dim: int,
        posterior_embedding_dim: int,
        hidden_dim: int,
    ) -> None:
        super().__init__()
        self.posterior_projection = nn.Sequential(
            nn.Linear(GOAL_HYPOTHESIS_COUNT, posterior_embedding_dim),
            nn.GELU(),
            nn.LayerNorm(posterior_embedding_dim),
        )
        input_dim = (
            action_token_dim
            + parent_hidden_dim
            + goal_embedding_dim
            + posterior_embedding_dim
            + GOAL_DIMENSIONS * GOAL_CARDINALITY
            + CAUSAL_FEATURE_DIM
            + 1
        )
        self.score = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, 1),
        )

    def forward(
        self,
        *,
        action_tokens: Tensor,
        parent_hidden: Tensor,
        goal_embedding: Tensor,
        posterior: Tensor,
        marginals: Tensor,
        causal_action_features: Tensor,
        r11_flag: Tensor,
    ) -> Tensor:
        batch, actions, _ = action_tokens.shape
        posterior_embedding = self.posterior_projection(posterior)
        hidden_expanded = parent_hidden[:, None, :].expand(batch, actions, parent_hidden.shape[-1])
        goal_expanded = goal_embedding[:, None, :].expand(batch, actions, goal_embedding.shape[-1])
        posterior_expanded = posterior_embedding[:, None, :].expand(
            batch, actions, posterior_embedding.shape[-1]
        )
        marginal_expanded = marginals[:, None, :].expand(batch, actions, marginals.shape[-1])
        features = torch.cat(
            (
                action_tokens,
                hidden_expanded,
                goal_expanded,
                posterior_expanded,
                marginal_expanded,
                causal_action_features,
                r11_flag,
            ),
            dim=-1,
        )
        return self.score(features).squeeze(-1)


class NativeR20AdvantageConsensus(nn.Module):
    """Frozen accepted R4 substrate plus an ensemble of action-advantage scorers.

    R20 does not replace R11's policy. It estimates whether one alternative action
    has a sufficiently strong learned advantage over R11. Runtime gating remains
    fail-closed unless every scorer agrees on the same alternative.
    """

    def __init__(
        self,
        parent: NativeR4LatentGoalBeliefPolicy,
        *,
        ensemble_size: int = 3,
        posterior_embedding_dim: int = 24,
        hidden_dim: int = 96,
    ) -> None:
        super().__init__()
        if ensemble_size < 2:
            raise ValueError("ensemble_size must be >=2")
        if posterior_embedding_dim < 1 or hidden_dim < 1:
            raise ValueError("R20 dimensions must be positive")
        self.parent = parent
        self.ensemble_size = int(ensemble_size)
        self.posterior_embedding_dim = int(posterior_embedding_dim)
        self.hidden_dim = int(hidden_dim)
        for parameter in self.parent.parameters():
            parameter.requires_grad_(False)
        self.parent.eval()

        native_hidden = int(parent.parent.parent.parent.hidden_dim)
        action_token_dim = native_hidden
        goal_embedding_dim = int(parent.goal_embedding_dim)
        self.scorers = nn.ModuleList(
            [
                _AdvantageScorer(
                    action_token_dim=action_token_dim,
                    parent_hidden_dim=native_hidden,
                    goal_embedding_dim=goal_embedding_dim,
                    posterior_embedding_dim=self.posterior_embedding_dim,
                    hidden_dim=self.hidden_dim,
                )
                for _ in range(self.ensemble_size)
            ]
        )

        goal_onehot = torch.zeros(
            GOAL_HYPOTHESIS_COUNT,
            GOAL_DIMENSIONS * GOAL_CARDINALITY,
        )
        for row, goal in enumerate(GOAL_TABLE.tolist()):
            for dimension, value in enumerate(goal):
                goal_onehot[row, dimension * GOAL_CARDINALITY + int(value)] = 1.0
        self.register_buffer("goal_onehot", goal_onehot, persistent=True)

    def train(self, mode: bool = True) -> "NativeR20AdvantageConsensus":
        super().train(mode)
        self.parent.eval()
        return self

    def architecture(self) -> dict[str, Any]:
        return {
            **self.parent.architecture(),
            "r20_ensemble_size": self.ensemble_size,
            "r20_posterior_embedding_dim": self.posterior_embedding_dim,
            "r20_hidden_dim": self.hidden_dim,
            "r20_causal_feature_dim": CAUSAL_FEATURE_DIM,
        }

    def successor_parameters(self) -> list[nn.Parameter]:
        return [p for scorer in self.scorers for p in scorer.parameters()]

    def successor_parameter_count(self) -> int:
        return sum(p.numel() for p in self.successor_parameters())

    def full_parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def successor_state_dict(self) -> dict[str, Tensor]:
        return {
            name: tensor.detach().cpu().clone()
            for name, tensor in self.state_dict().items()
            if not name.startswith("parent.")
        }

    def successor_state_sha256(self) -> str:
        return state_dict_sha256(self.successor_state_dict())

    def load_successor_state_dict(self, state: dict[str, Tensor]) -> None:
        expected = {
            name for name in self.state_dict()
            if not name.startswith("parent.")
        }
        if set(state) != expected:
            raise ValueError("R20 successor state keys mismatch")
        merged = self.state_dict()
        for name, tensor in state.items():
            merged[name] = tensor
        self.load_state_dict(merged, strict=True)

    def score_from_parent(
        self,
        *,
        global_features: Tensor,
        action_features: Tensor,
        valid_actions: Tensor,
        parent_output: dict[str, Tensor],
        consistency_posterior: Tensor,
        causal_action_features: Tensor,
        r11_actions: Tensor,
    ) -> Tensor:
        if consistency_posterior.ndim != 2 or consistency_posterior.shape[-1] != GOAL_HYPOTHESIS_COUNT:
            raise ValueError("consistency_posterior must be [batch,125]")
        if causal_action_features.ndim != 3 or causal_action_features.shape[-1] != CAUSAL_FEATURE_DIM:
            raise ValueError("causal_action_features must be [batch,actions,10]")
        batch, actions, _ = causal_action_features.shape
        if action_features.shape[:2] != (batch, actions):
            raise ValueError("R20 action feature shape mismatch")
        if valid_actions.shape != (batch, actions) or valid_actions.dtype != torch.bool:
            raise ValueError("valid_actions must be bool [batch,actions]")
        if r11_actions.shape != (batch,):
            raise ValueError("r11_actions must be [batch]")

        mass = consistency_posterior.sum(dim=-1, keepdim=True)
        if bool((mass <= 0.0).any()):
            raise ValueError("posterior rows need positive mass")
        posterior = consistency_posterior / mass
        marginals = posterior @ self.goal_onehot.to(posterior.dtype)

        with torch.no_grad():
            action_tokens = self.parent.parent.parent.parent.action_encoder(
                action_features
            ).detach()
        parent_hidden = parent_output["next_parent_hidden"].detach()
        goal_embedding = parent_output["goal_embedding"].detach()

        r11_flag = torch.zeros(
            batch,
            actions,
            1,
            dtype=action_features.dtype,
            device=action_features.device,
        )
        r11_flag.scatter_(
            1,
            r11_actions[:, None, None],
            torch.ones(batch, 1, 1, dtype=action_features.dtype, device=action_features.device),
        )

        scores = torch.stack(
            [
                scorer(
                    action_tokens=action_tokens,
                    parent_hidden=parent_hidden,
                    goal_embedding=goal_embedding,
                    posterior=posterior,
                    marginals=marginals,
                    causal_action_features=causal_action_features,
                    r11_flag=r11_flag,
                )
                for scorer in self.scorers
            ],
            dim=0,
        )
        scores = scores.masked_fill(
            ~valid_actions.unsqueeze(0),
            torch.finfo(scores.dtype).min,
        )
        return scores


def consensus_advantage_action(
    scores: Tensor,
    *,
    valid_actions: Tensor,
    r11_action: int,
    threshold: float,
) -> tuple[int, dict[str, Any]]:
    """Return R11 unless all scorers agree on a high-margin alternative."""
    if scores.ndim != 2:
        raise ValueError("scores must be [ensemble,actions]")
    if valid_actions.ndim != 1 or valid_actions.dtype != torch.bool:
        raise ValueError("valid_actions must be bool [actions]")
    if scores.shape[1] != valid_actions.shape[0]:
        raise ValueError("score/action mismatch")
    if not 0 <= int(r11_action) < scores.shape[1]:
        raise ValueError("r11_action out of range")
    if not bool(valid_actions[int(r11_action)]):
        raise ValueError("r11_action must be valid")

    masked = scores.masked_fill(
        ~valid_actions.unsqueeze(0),
        torch.finfo(scores.dtype).min,
    )
    top = masked.argmax(dim=-1)
    agreed = bool((top == top[0]).all())
    if not agreed:
        return int(r11_action), {
            "override": False,
            "reason": "ensemble_disagreement",
            "threshold": float(threshold),
        }
    alternative = int(top[0].item())
    if alternative == int(r11_action):
        return int(r11_action), {
            "override": False,
            "reason": "ensemble_prefers_r11",
            "threshold": float(threshold),
        }

    margins = masked[:, alternative] - masked[:, int(r11_action)]
    minimum_margin = float(margins.min().item())
    if minimum_margin < float(threshold):
        return int(r11_action), {
            "override": False,
            "reason": "margin_below_threshold",
            "minimum_margin": minimum_margin,
            "threshold": float(threshold),
            "proposed_action": alternative,
        }
    return alternative, {
        "override": True,
        "reason": "consensus_advantage",
        "minimum_margin": minimum_margin,
        "threshold": float(threshold),
        "proposed_action": alternative,
    }
