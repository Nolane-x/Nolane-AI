from __future__ import annotations

from typing import Any, Mapping

import torch
from torch import Tensor, nn

from native_core import ACTION_FEATURE_DIM, state_dict_sha256
from public_planner import GOAL_CARDINALITY, GOAL_DIMENSIONS, GOAL_HYPOTHESIS_COUNT

STATE_ONEHOT_DIM = GOAL_DIMENSIONS * GOAL_CARDINALITY
PUBLIC_SCALAR_DIM = 6
DECISION_FEATURE_DIM = 12
PUBLIC_BASE_FEATURE_DIM = (
    GOAL_HYPOTHESIS_COUNT
    + STATE_ONEHOT_DIM
    + PUBLIC_SCALAR_DIM
    + DECISION_FEATURE_DIM
)
DETECTOR_INPUT_DIM = PUBLIC_BASE_FEATURE_DIM + ACTION_FEATURE_DIM
CORRECTOR_INPUT_DIM = PUBLIC_BASE_FEATURE_DIM + ACTION_FEATURE_DIM * 2

_REASON_KEYS = (
    "target_visible_r9_exact",
    "r9_public_progress_complete",
    "posterior_too_broad_r9_fallback",
    "no_certified_causal_advantage",
    "certified_causal_advantage",
)


def _state_onehot(observation: Mapping[str, Any]) -> Tensor:
    state = observation.get("state")
    if not isinstance(state, list) or len(state) != GOAL_DIMENSIONS:
        raise ValueError("public state must contain three dimensions")
    out = torch.zeros(STATE_ONEHOT_DIM, dtype=torch.float32)
    for dim, value in enumerate(state):
        value = int(value)
        if not 0 <= value < GOAL_CARDINALITY:
            raise ValueError("public state value out of range")
        out[dim * GOAL_CARDINALITY + value] = 1.0
    return out


def encode_public_base_features(
    *,
    support_mask: Tensor,
    observation: Mapping[str, Any],
    previous_feedback: list[float] | tuple[float, float, float],
    r11_decision: Mapping[str, Any],
) -> Tensor:
    if support_mask.shape != (GOAL_HYPOTHESIS_COUNT,):
        raise ValueError("support mask must be [125]")
    feedback = [float(value) for value in previous_feedback]
    if len(feedback) != 3:
        raise ValueError("previous feedback must contain three values")

    scalars = torch.tensor(
        [
            float(observation["progress_signal"]),
            min(1.0, float(observation["budget_remaining"]) / 32.0),
            min(1.0, float(observation["step"]) / 32.0),
            feedback[0],
            feedback[1],
            feedback[2],
        ],
        dtype=torch.float32,
    )

    reason = str(r11_decision.get("reason", "other"))
    reason_onehot = torch.zeros(6, dtype=torch.float32)
    if reason in _REASON_KEYS:
        reason_onehot[_REASON_KEYS.index(reason)] = 1.0
    else:
        reason_onehot[-1] = 1.0

    support_count = int(support_mask.sum().item())
    selected_final = float(
        r11_decision.get(
            "selected_final_distance",
            r11_decision.get("r9_reference_distance", 0.0),
        )
    )
    reference = float(r11_decision.get("r9_reference_distance", selected_final))
    diagnostics = torch.tensor(
        [
            min(1.0, support_count / float(GOAL_HYPOTHESIS_COUNT)),
            float(bool(r11_decision.get("override", False))),
            min(1.0, float(r11_decision.get("r9_rule_count", 0)) / 18.0),
            min(1.0, float(r11_decision.get("selected_rule_count", 0)) / 18.0),
            max(-1.0, min(1.0, (reference - selected_final) / 15.0)),
            min(1.0, float(r11_decision.get("selected_depth", 0)) / 3.0),
        ],
        dtype=torch.float32,
    )

    features = torch.cat(
        (
            support_mask.float(),
            _state_onehot(observation),
            scalars,
            reason_onehot,
            diagnostics,
        ),
        dim=0,
    )
    if features.shape != (PUBLIC_BASE_FEATURE_DIM,):
        raise AssertionError("unexpected R25 public feature shape")
    return features


class _SelectiveCorrectionHead(nn.Module):
    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.detector = nn.Sequential(
            nn.Linear(DETECTOR_INPUT_DIM, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
        )
        self.corrector = nn.Sequential(
            nn.Linear(CORRECTOR_INPUT_DIM, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
        )

    def detector_logit(
        self,
        base_features: Tensor,
        r11_action_features: Tensor,
    ) -> Tensor:
        if base_features.ndim == 1:
            base_features = base_features.unsqueeze(0)
        if r11_action_features.ndim == 1:
            r11_action_features = r11_action_features.unsqueeze(0)
        return self.detector(
            torch.cat((base_features, r11_action_features), dim=-1)
        ).squeeze(-1)

    def correction_logits(
        self,
        base_features: Tensor,
        r11_action_features: Tensor,
        action_features: Tensor,
    ) -> Tensor:
        if base_features.ndim != 1:
            raise ValueError("correction expects one public base feature row")
        if r11_action_features.shape != (ACTION_FEATURE_DIM,):
            raise ValueError("R11 action feature shape mismatch")
        if action_features.ndim != 2 or action_features.shape[-1] != ACTION_FEATURE_DIM:
            raise ValueError("candidate action features must be [actions, action_dim]")
        count = int(action_features.shape[0])
        base = base_features.unsqueeze(0).expand(count, -1)
        r11 = r11_action_features.unsqueeze(0).expand(count, -1)
        return self.corrector(
            torch.cat((base, r11, action_features), dim=-1)
        ).squeeze(-1)


class NativeR25SelectiveCorrectionEnsemble(nn.Module):
    """Separate R11 error detection from action correction."""

    def __init__(self, *, ensemble_size: int = 3, hidden_dim: int = 64) -> None:
        super().__init__()
        if ensemble_size < 2:
            raise ValueError("ensemble_size must be >=2")
        if hidden_dim < 1:
            raise ValueError("hidden_dim must be positive")
        self.ensemble_size = int(ensemble_size)
        self.hidden_dim = int(hidden_dim)
        self.heads = nn.ModuleList(
            [_SelectiveCorrectionHead(self.hidden_dim) for _ in range(self.ensemble_size)]
        )

    def architecture(self) -> dict[str, Any]:
        return {
            "r25_ensemble_size": self.ensemble_size,
            "r25_hidden_dim": self.hidden_dim,
            "r25_public_base_feature_dim": PUBLIC_BASE_FEATURE_DIM,
            "r25_detector_input_dim": DETECTOR_INPUT_DIM,
            "r25_corrector_input_dim": CORRECTOR_INPUT_DIM,
            "mechanism": "selective_r11_error_detector_plus_action_corrector",
        }

    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())

    def state_sha256(self) -> str:
        return state_dict_sha256(
            {
                name: tensor.detach().cpu().clone()
                for name, tensor in self.state_dict().items()
            }
        )

    def predict(
        self,
        *,
        base_features: Tensor,
        r11_action_features: Tensor,
        action_features: Tensor,
    ) -> tuple[Tensor, Tensor]:
        detector_probabilities: list[Tensor] = []
        correction_rows: list[Tensor] = []
        for head in self.heads:
            detector_probabilities.append(
                torch.sigmoid(
                    head.detector_logit(base_features, r11_action_features)[0]
                )
            )
            correction_rows.append(
                head.correction_logits(
                    base_features,
                    r11_action_features,
                    action_features,
                )
            )
        return (
            torch.stack(detector_probabilities, dim=0),
            torch.stack(correction_rows, dim=0),
        )
