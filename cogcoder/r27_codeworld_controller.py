from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import torch
from torch import Tensor, nn

ACTION_KINDS: tuple[str, ...] = (
    "inspect_tree",
    "search_code",
    "read_context",
    "reproduce_failure",
    "edit_small",
    "edit_multi",
    "run_targeted_tests",
    "run_full_tests",
    "inspect_diff",
    "revert",
    "query_docs",
    "finish",
)


@dataclass(frozen=True)
class CodeWorldControllerConfig:
    state_dim: int = 32
    action_feature_dim: int = 24
    history_feature_dim: int = 16
    hidden_dim: int = 192
    language_count: int = 12
    task_type_count: int = 8
    embedding_dim: int = 32


class CodeWorldControllerOutput(NamedTuple):
    action_logits: Tensor
    stop_logit: Tensor
    success_logit: Tensor


class CodeWorldController(nn.Module):
    """Small task/language-agnostic controller for a test-driven coding loop.

    It does not generate source code. It ranks candidate tool/edit actions from
    structured execution state so the much larger parent stays compact and can
    reuse the same controller across languages and task families.
    """

    def __init__(self, config: CodeWorldControllerConfig | None = None) -> None:
        super().__init__()
        self.config = config or CodeWorldControllerConfig()
        c = self.config
        h = c.hidden_dim

        self.state_encoder = nn.Sequential(
            nn.Linear(c.state_dim, h),
            nn.GELU(),
            nn.LayerNorm(h),
        )
        self.action_encoder = nn.Sequential(
            nn.Linear(c.action_feature_dim, h),
            nn.GELU(),
            nn.LayerNorm(h),
        )
        self.history_input = nn.Sequential(
            nn.Linear(c.history_feature_dim, h),
            nn.GELU(),
        )
        self.history_gru = nn.GRU(h, h, batch_first=True)
        self.language_embedding = nn.Embedding(c.language_count, c.embedding_dim)
        self.task_embedding = nn.Embedding(c.task_type_count, c.embedding_dim)
        self.context_encoder = nn.Sequential(
            nn.Linear(c.embedding_dim * 2, h),
            nn.GELU(),
            nn.LayerNorm(h),
        )
        self.fusion = nn.Sequential(
            nn.Linear(h * 3, h * 2),
            nn.GELU(),
            nn.LayerNorm(h * 2),
            nn.Linear(h * 2, h),
            nn.GELU(),
            nn.LayerNorm(h),
        )
        self.action_scorer = nn.Sequential(
            nn.Linear(h * 2, h),
            nn.GELU(),
            nn.Linear(h, 1),
        )
        self.stop_head = nn.Linear(h, 1)
        self.success_head = nn.Linear(h, 1)

    def _validate(
        self,
        state_features: Tensor,
        action_features: Tensor,
        history_features: Tensor,
        language_ids: Tensor,
        task_type_ids: Tensor,
        action_mask: Tensor,
    ) -> None:
        c = self.config
        if state_features.ndim != 2 or state_features.shape[-1] != c.state_dim:
            raise ValueError(f"state_features must be [B,{c.state_dim}]")
        if action_features.ndim != 3 or action_features.shape[-1] != c.action_feature_dim:
            raise ValueError(
                f"action_features must be [B,A,{c.action_feature_dim}]"
            )
        if history_features.ndim != 3 or history_features.shape[-1] != c.history_feature_dim:
            raise ValueError(
                f"history_features must be [B,T,{c.history_feature_dim}]"
            )
        batch = state_features.shape[0]
        if action_features.shape[0] != batch or history_features.shape[0] != batch:
            raise ValueError("all feature tensors must share batch size")
        if language_ids.shape != (batch,) or task_type_ids.shape != (batch,):
            raise ValueError("language_ids and task_type_ids must be [B]")
        if action_mask.shape != action_features.shape[:2] or action_mask.dtype != torch.bool:
            raise ValueError("action_mask must be boolean [B,A]")
        if not bool(action_mask.any(dim=1).all()):
            raise ValueError("every batch item must have at least one legal action")

    def forward(
        self,
        *,
        state_features: Tensor,
        action_features: Tensor,
        history_features: Tensor,
        language_ids: Tensor,
        task_type_ids: Tensor,
        action_mask: Tensor,
    ) -> CodeWorldControllerOutput:
        self._validate(
            state_features,
            action_features,
            history_features,
            language_ids,
            task_type_ids,
            action_mask,
        )
        state = self.state_encoder(state_features)
        actions = self.action_encoder(action_features)
        history_encoded = self.history_input(history_features)
        _, history_hidden = self.history_gru(history_encoded)
        history = history_hidden[-1]
        context = self.context_encoder(
            torch.cat(
                [
                    self.language_embedding(language_ids),
                    self.task_embedding(task_type_ids),
                ],
                dim=-1,
            )
        )
        fused = self.fusion(torch.cat([state, history, context], dim=-1))
        expanded = fused.unsqueeze(1).expand(-1, actions.shape[1], -1)
        logits = self.action_scorer(torch.cat([expanded, actions], dim=-1)).squeeze(-1)
        logits = logits.masked_fill(~action_mask, float("-inf"))
        return CodeWorldControllerOutput(
            action_logits=logits,
            stop_logit=self.stop_head(fused).squeeze(-1),
            success_logit=self.success_head(fused).squeeze(-1),
        )


def controller_parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())
