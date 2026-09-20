from __future__ import annotations

from typing import Any, Mapping

import torch
from torch import Tensor, nn

from native_core import ACTION_FEATURE_DIM, state_dict_sha256
from public_planner import GOAL_CARDINALITY, GOAL_DIMENSIONS, GOAL_HYPOTHESIS_COUNT

STATE_ONEHOT_DIM = GOAL_DIMENSIONS * GOAL_CARDINALITY
PUBLIC_GOAL_FEATURE_DIM = GOAL_HYPOTHESIS_COUNT + STATE_ONEHOT_DIM + 6
ACTION_POLICY_SCALAR_DIM = 20

BELIEF_HIDDEN_DIM = 96
GOAL_EMBEDDING_DIM = 48
NATIVE_HIDDEN_DIM = 128
TRACE_HIDDEN_DIM = 128
ATTRIBUTION_HIDDEN_DIM = 128
LATENT_CONTEXT_DIM = (
    BELIEF_HIDDEN_DIM
    + GOAL_EMBEDDING_DIM
    + NATIVE_HIDDEN_DIM
    + TRACE_HIDDEN_DIM
    + ATTRIBUTION_HIDDEN_DIM
)

BASE_PAIR_FEATURE_DIM = (
    PUBLIC_GOAL_FEATURE_DIM
    + ACTION_FEATURE_DIM * 2
    + STATE_ONEHOT_DIM * 2
    + ACTION_POLICY_SCALAR_DIM
)
PAIR_FEATURE_DIM = BASE_PAIR_FEATURE_DIM + LATENT_CONTEXT_DIM

JOINT_OUTCOME_CLASS_COUNT = 4
BOTH_FAIL_CLASS = 0
RESCUE_CLASS = 1
HARM_CLASS = 2
BOTH_SOLVE_CLASS = 3

BRANCH_SEQUENCE_HORIZON = 6
BRANCH_SEQUENCE_CHANNELS = 4
TIME_EMBEDDING_DIM = 16


def goal_index(goal: tuple[int, int, int] | list[int]) -> int:
    if len(goal) != GOAL_DIMENSIONS:
        raise ValueError("goal needs three dimensions")
    a, b, c = (int(v) for v in goal)
    if not all(0 <= v < GOAL_CARDINALITY for v in (a, b, c)):
        raise ValueError("goal value out of range")
    return a * GOAL_CARDINALITY * GOAL_CARDINALITY + b * GOAL_CARDINALITY + c


def state_onehot(state: Tensor | list[int] | tuple[int, ...]) -> Tensor:
    values = [int(v) for v in (state.tolist() if isinstance(state, Tensor) else state)]
    if len(values) != GOAL_DIMENSIONS:
        raise ValueError("state needs three dimensions")
    out = torch.zeros(STATE_ONEHOT_DIM, dtype=torch.float32)
    for dim, value in enumerate(values):
        if not 0 <= value < GOAL_CARDINALITY:
            raise ValueError("state value out of range")
        out[dim * GOAL_CARDINALITY + value] = 1.0
    return out


def state_onehot_optional(state: Tensor | list[int] | tuple[int, ...] | None) -> Tensor:
    if state is None:
        return torch.zeros(STATE_ONEHOT_DIM, dtype=torch.float32)
    return state_onehot(state)


def encode_public_goal_features(
    *,
    support_mask: Tensor,
    observation: dict[str, Any],
    previous_feedback: list[float] | tuple[float, float, float],
) -> Tensor:
    if support_mask.shape != (GOAL_HYPOTHESIS_COUNT,):
        raise ValueError("support_mask must have shape [125]")
    state = observation.get("state")
    if not isinstance(state, list) or len(state) != GOAL_DIMENSIONS:
        raise ValueError("public state must contain three dimensions")
    feedback = [float(v) for v in previous_feedback]
    if len(feedback) != 3:
        raise ValueError("previous_feedback must contain three values")
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
    features = torch.cat((support_mask.float(), state_onehot(state), scalars), dim=0)
    if features.shape != (PUBLIC_GOAL_FEATURE_DIM,):
        raise AssertionError("unexpected R35 public goal feature shape")
    return features


def _single_batch_vector(
    parent_output: Mapping[str, Tensor],
    key: str,
    expected_dim: int,
) -> Tensor:
    value = parent_output.get(key)
    if not isinstance(value, Tensor):
        raise ValueError(f"missing R4 latent tensor: {key}")
    if value.shape != (1, int(expected_dim)):
        raise ValueError(
            f"R4 latent tensor {key} must have shape [1,{expected_dim}], got {tuple(value.shape)}"
        )
    return value[0].detach().float()


def encode_parent_latent_context(parent_output: Mapping[str, Tensor]) -> Tensor:
    latent = torch.cat(
        (
            _single_batch_vector(parent_output, "belief_hidden", BELIEF_HIDDEN_DIM),
            _single_batch_vector(parent_output, "goal_embedding", GOAL_EMBEDDING_DIM),
            _single_batch_vector(parent_output, "next_parent_hidden", NATIVE_HIDDEN_DIM),
            _single_batch_vector(parent_output, "r2_trace_hidden", TRACE_HIDDEN_DIM),
            _single_batch_vector(
                parent_output,
                "r3_attribution_hidden",
                ATTRIBUTION_HIDDEN_DIM,
            ),
        ),
        dim=0,
    )
    if latent.shape != (LATENT_CONTEXT_DIM,):
        raise AssertionError("unexpected R35 parent latent context shape")
    if not bool(torch.isfinite(latent).all().item()):
        raise ValueError("R4 latent context contains non-finite values")
    return latent


def encode_pair_features(
    *,
    public_goal_features: Tensor,
    latent_context: Tensor,
    r11_action_features: Tensor,
    candidate_action_features: Tensor,
    r11_next_state: Tensor | None,
    candidate_next_state: Tensor | None,
    support_count: int,
    candidate_min_mass: float,
    candidate_mean_mass: float,
    r11_mean_mass: float,
    mass_margin: float,
    candidate_mass_spread: float,
    r11_mass_spread: float,
    parent_logit_margin: float,
    r11_certified: bool,
    candidate_certified: bool,
    r11_rule_count: int,
    candidate_rule_count: int,
    current_expected_distance: float,
    r11_expected_distance: float,
    candidate_expected_distance: float,
    distance_advantage: float,
    rule_count_advantage: float,
    candidate_seen_in_context: int,
    r11_seen_in_context: int,
) -> Tensor:
    if public_goal_features.shape != (PUBLIC_GOAL_FEATURE_DIM,):
        raise ValueError("public goal feature shape mismatch")
    if latent_context.shape != (LATENT_CONTEXT_DIM,):
        raise ValueError("R4 latent context shape mismatch")
    if r11_action_features.shape != (ACTION_FEATURE_DIM,):
        raise ValueError("R11 action feature shape mismatch")
    if candidate_action_features.shape != (ACTION_FEATURE_DIM,):
        raise ValueError("candidate action feature shape mismatch")
    scalars = torch.tensor(
        [
            min(1.0, float(support_count) / float(GOAL_HYPOTHESIS_COUNT)),
            float(candidate_min_mass),
            float(candidate_mean_mass),
            float(r11_mean_mass),
            float(mass_margin),
            float(candidate_mass_spread),
            float(r11_mass_spread),
            float(parent_logit_margin),
            float(bool(r11_certified)),
            float(bool(candidate_certified)),
            min(1.0, float(r11_rule_count) / 18.0),
            min(1.0, float(candidate_rule_count) / 18.0),
            float(current_expected_distance) / 12.0,
            float(r11_expected_distance) / 12.0,
            float(candidate_expected_distance) / 12.0,
            float(distance_advantage) / 12.0,
            float(rule_count_advantage) / 18.0,
            min(1.0, float(candidate_seen_in_context) / 8.0),
            min(1.0, float(r11_seen_in_context) / 8.0),
            float(bool(r11_certified) and bool(candidate_certified)),
        ],
        dtype=torch.float32,
    )
    features = torch.cat(
        (
            public_goal_features.float(),
            r11_action_features.float(),
            candidate_action_features.float(),
            state_onehot_optional(r11_next_state),
            state_onehot_optional(candidate_next_state),
            scalars,
            latent_context.float(),
        ),
        dim=0,
    )
    if features.shape != (PAIR_FEATURE_DIM,):
        raise AssertionError("unexpected R35 pair feature shape")
    return features


class _GoalBeliefHead(nn.Module):
    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(PUBLIC_GOAL_FEATURE_DIM, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, GOAL_HYPOTHESIS_COUNT),
        )

    def forward(self, features: Tensor) -> Tensor:
        return self.net(features)


class _BranchSequenceDecoderHead(nn.Module):
    """Forecasts fixed-policy baseline/candidate branch signatures before joint rescue classification."""

    def __init__(
        self,
        hidden_dim: int,
        *,
        horizon: int = BRANCH_SEQUENCE_HORIZON,
        time_embedding_dim: int = TIME_EMBEDDING_DIM,
    ) -> None:
        super().__init__()
        self.hidden_dim = int(hidden_dim)
        self.horizon = int(horizon)
        self.context = nn.Sequential(
            nn.Linear(PAIR_FEATURE_DIM, self.hidden_dim),
            nn.GELU(),
            nn.LayerNorm(self.hidden_dim),
        )
        self.time_embedding = nn.Embedding(self.horizon, int(time_embedding_dim))
        self.baseline_decoder = nn.GRU(
            input_size=int(time_embedding_dim),
            hidden_size=self.hidden_dim,
            batch_first=True,
        )
        self.candidate_decoder = nn.GRU(
            input_size=int(time_embedding_dim),
            hidden_size=self.hidden_dim,
            batch_first=True,
        )
        self.baseline_projection = nn.Linear(
            self.hidden_dim, BRANCH_SEQUENCE_CHANNELS
        )
        self.candidate_projection = nn.Linear(
            self.hidden_dim, BRANCH_SEQUENCE_CHANNELS
        )
        self.joint_head = nn.Sequential(
            nn.Linear(self.hidden_dim * 3, self.hidden_dim),
            nn.GELU(),
            nn.LayerNorm(self.hidden_dim),
            nn.Linear(self.hidden_dim, JOINT_OUTCOME_CLASS_COUNT),
        )

    def forward(self, features: Tensor) -> dict[str, Tensor]:
        context = self.context(features)
        batch = int(features.shape[0])
        positions = torch.arange(
            self.horizon,
            device=features.device,
            dtype=torch.long,
        ).unsqueeze(0).expand(batch, -1)
        decoder_input = self.time_embedding(positions)
        initial = context.unsqueeze(0)
        baseline_hidden, baseline_final = self.baseline_decoder(
            decoder_input, initial
        )
        candidate_hidden, candidate_final = self.candidate_decoder(
            decoder_input, initial
        )
        baseline_sequence = self.baseline_projection(baseline_hidden)
        candidate_sequence = self.candidate_projection(candidate_hidden)
        joint_input = torch.cat(
            (
                context,
                baseline_final[0],
                candidate_final[0],
            ),
            dim=-1,
        )
        return {
            "joint_logits": self.joint_head(joint_input),
            "baseline_sequence": baseline_sequence,
            "candidate_sequence": candidate_sequence,
        }


class NativeR35BranchSequenceDecoderEnsemble(nn.Module):
    """Direct branch-sequence forecasting under fixed R11 continuation plus joint rescue classification."""

    def __init__(
        self,
        *,
        ensemble_size: int = 3,
        goal_hidden_dim: int = 96,
        decoder_hidden_dim: int = 64,
        horizon: int = BRANCH_SEQUENCE_HORIZON,
        time_embedding_dim: int = TIME_EMBEDDING_DIM,
    ) -> None:
        super().__init__()
        if ensemble_size < 2:
            raise ValueError("ensemble_size must be >=2")
        self.ensemble_size = int(ensemble_size)
        self.goal_hidden_dim = int(goal_hidden_dim)
        self.decoder_hidden_dim = int(decoder_hidden_dim)
        self.horizon = int(horizon)
        self.time_embedding_dim = int(time_embedding_dim)
        if self.horizon != BRANCH_SEQUENCE_HORIZON:
            raise ValueError("R35 horizon is preregistered")
        self.goal_heads = nn.ModuleList(
            [_GoalBeliefHead(self.goal_hidden_dim) for _ in range(self.ensemble_size)]
        )
        self.sequence_heads = nn.ModuleList(
            [
                _BranchSequenceDecoderHead(
                    self.decoder_hidden_dim,
                    horizon=self.horizon,
                    time_embedding_dim=self.time_embedding_dim,
                )
                for _ in range(self.ensemble_size)
            ]
        )

    def architecture(self) -> dict[str, Any]:
        return {
            "r35_ensemble_size": self.ensemble_size,
            "r35_goal_hidden_dim": self.goal_hidden_dim,
            "r35_decoder_hidden_dim": self.decoder_hidden_dim,
            "r35_pair_feature_dim": PAIR_FEATURE_DIM,
            "r35_branch_sequence_horizon": self.horizon,
            "r35_branch_sequence_channels": BRANCH_SEQUENCE_CHANNELS,
            "r35_time_embedding_dim": self.time_embedding_dim,
            "r35_joint_outcome_class_count": JOINT_OUTCOME_CLASS_COUNT,
            "mechanism": "direct_fixed_r11_branch_sequence_forecasting_with_joint_rescue_head",
        }

    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())

    def goal_parameter_count(self) -> int:
        return sum(
            parameter.numel()
            for head in self.goal_heads
            for parameter in head.parameters()
        )

    def sequence_parameter_count(self) -> int:
        return sum(
            parameter.numel()
            for head in self.sequence_heads
            for parameter in head.parameters()
        )

    def state_sha256(self) -> str:
        return state_dict_sha256(
            {
                name: tensor.detach().cpu().clone()
                for name, tensor in self.state_dict().items()
            }
        )

    def per_head_goal_probabilities(
        self,
        *,
        features: Tensor,
        support_mask: Tensor,
        temperature: float,
    ) -> Tensor:
        logits = torch.stack(
            [head(features.unsqueeze(0))[0] for head in self.goal_heads], dim=0
        )
        masked = logits.masked_fill(
            ~support_mask.bool().unsqueeze(0),
            torch.finfo(logits.dtype).min,
        )
        probabilities = torch.softmax(masked / float(temperature), dim=-1)
        probabilities = probabilities * support_mask.float().unsqueeze(0)
        return probabilities / probabilities.sum(dim=-1, keepdim=True).clamp_min(1.0e-12)

    def branch_outputs(self, features: Tensor) -> dict[str, Tensor]:
        if features.shape != (PAIR_FEATURE_DIM,):
            raise ValueError("R35 pair feature shape mismatch")
        outputs = [head(features.unsqueeze(0)) for head in self.sequence_heads]
        return {
            "joint_probabilities": torch.softmax(
                torch.stack([out["joint_logits"][0] for out in outputs], dim=0),
                dim=-1,
            ),
            "baseline_sequences": torch.stack(
                [out["baseline_sequence"][0] for out in outputs], dim=0
            ),
            "candidate_sequences": torch.stack(
                [out["candidate_sequence"][0] for out in outputs], dim=0
            ),
        }
