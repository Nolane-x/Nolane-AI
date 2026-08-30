from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Mapping, Sequence

from .experimentation import ExperimentProbe, ShadowExperimentReceipt


COMPONENT_ID = "external.experimentation"
COMPONENT_VERSION = "0.0.2"
SCHEMA_VERSION = "experiment-design-v1"
DESIGN_LINEAGE = (
    "post-Epoch-0 experiment-design extension over accepted R2.60 shadow experimentation; "
    "design and execution receipts never acquire promotion authority"
)


class ExperimentProbeRole(str, Enum):
    TREATMENT = "treatment"
    NEGATIVE_CONTROL = "negative_control"
    ABLATION = "ablation"
    INDEPENDENT_VERIFICATION = "independent_verification"


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise TypeError("value must be finite JSON-compatible data") from exc


def _identity(prefix: str, state: Mapping[str, object]) -> str:
    raw = _canonical_json(dict(state)).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(raw).hexdigest()}"


def _nonempty(value: object, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _sequence(value: object, name: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a sequence")
    return value


def _normalized_ids(values: object, name: str, *, minimum: int = 0) -> tuple[str, ...]:
    source = _sequence(values, name)
    rows = tuple(_nonempty(value, name) for value in source)
    if len(rows) < minimum:
        raise ValueError(f"{name} must contain at least {minimum} values")
    if len(rows) != len(set(rows)):
        raise ValueError(f"{name} must not contain duplicates")
    return tuple(sorted(rows))


def _positive_finite(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be a positive finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a positive finite number") from exc
    if not isfinite(number):
        raise ValueError(f"{name} must be finite")
    if number <= 0.0:
        raise ValueError(f"{name} must be positive")
    return number


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a positive integer")
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


def _version_space_id(hypothesis_ids: Sequence[object]) -> str:
    rows = _normalized_ids(hypothesis_ids, "version-space hypothesis ids", minimum=1)
    raw = _canonical_json({"hypothesis_ids": list(rows)}).encode("utf-8")
    return f"xspace:{hashlib.sha256(raw).hexdigest()}"


@dataclass(frozen=True, slots=True)
class PlannedExperimentProbe:
    probe: ExperimentProbe
    role: ExperimentProbeRole
    estimated_cost: float

    def __post_init__(self) -> None:
        if not isinstance(self.probe, ExperimentProbe):
            raise TypeError("planned experiment probe requires ExperimentProbe")
        object.__setattr__(self, "role", ExperimentProbeRole(self.role))
        object.__setattr__(
            self,
            "estimated_cost",
            _positive_finite(self.estimated_cost, "estimated probe cost"),
        )

    def to_state(self) -> dict[str, object]:
        return {
            "probe": self.probe.to_state(),
            "role": self.role.value,
            "estimated_cost": self.estimated_cost,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "PlannedExperimentProbe":
        raw_probe = state.get("probe")
        if not isinstance(raw_probe, Mapping):
            raise TypeError("planned probe state requires probe mapping")
        row = cls(
            ExperimentProbe.from_state(raw_probe),
            ExperimentProbeRole(str(state["role"])),
            state["estimated_cost"],
        )
        if row.to_state() != dict(state):
            raise ValueError("non-canonical planned experiment probe state")
        return row


_REQUIRED_ROLES = frozenset(ExperimentProbeRole)
_SELECTION_ROLES = frozenset(
    {
        ExperimentProbeRole.TREATMENT,
        ExperimentProbeRole.NEGATIVE_CONTROL,
        ExperimentProbeRole.ABLATION,
    }
)


@dataclass(frozen=True, slots=True)
class ExperimentDesign:
    reasoning_hypothesis_id: str
    verification_plan_id: str
    version_space_id: str
    probes: tuple[PlannedExperimentProbe, ...]
    max_selection_oracle_calls: int
    max_total_cost: float
    stop_condition_ids: tuple[str, ...]
    design_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reasoning_hypothesis_id",
            _nonempty(self.reasoning_hypothesis_id, "reasoning hypothesis id"),
        )
        object.__setattr__(
            self,
            "verification_plan_id",
            _nonempty(self.verification_plan_id, "verification plan id"),
        )
        object.__setattr__(
            self,
            "version_space_id",
            _nonempty(self.version_space_id, "version-space id"),
        )
        source = tuple(_sequence(self.probes, "planned probes"))
        if not source or not all(isinstance(row, PlannedExperimentProbe) for row in source):
            raise TypeError("planned probes must contain PlannedExperimentProbe values")
        probe_ids = tuple(row.probe.probe_id for row in source)
        if len(probe_ids) != len(set(probe_ids)):
            raise ValueError("planned probes must not contain duplicate probe ids")
        roles = frozenset(row.role for row in source)
        missing = _REQUIRED_ROLES - roles
        if missing:
            names = ", ".join(sorted(row.value for row in missing))
            raise ValueError(f"experiment design is missing required probe roles: {names}")
        probes = tuple(sorted(source, key=lambda row: row.probe.probe_id))
        object.__setattr__(self, "probes", probes)
        object.__setattr__(
            self,
            "max_selection_oracle_calls",
            _positive_int(self.max_selection_oracle_calls, "max selection oracle calls"),
        )
        max_total_cost = _positive_finite(self.max_total_cost, "max total cost")
        worst_case_cost = sum(row.estimated_cost for row in probes)
        if max_total_cost + 1e-12 < worst_case_cost:
            raise ValueError("max total cost must cover declared worst-case probe cost")
        object.__setattr__(self, "max_total_cost", max_total_cost)
        object.__setattr__(
            self,
            "stop_condition_ids",
            _normalized_ids(self.stop_condition_ids, "stop condition ids", minimum=1),
        )
        object.__setattr__(self, "design_id", _identity("experiment-design", self._semantic_state()))

    @property
    def selection_probe_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(row.probe.probe_id for row in self.probes if row.role in _SELECTION_ROLES)
        )

    @property
    def verification_probe_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                row.probe.probe_id
                for row in self.probes
                if row.role is ExperimentProbeRole.INDEPENDENT_VERIFICATION
            )
        )

    @property
    def worst_case_cost(self) -> float:
        return sum(row.estimated_cost for row in self.probes)

    def cost_for_probe_id(self, probe_id: str) -> float:
        target = str(probe_id)
        for row in self.probes:
            if row.probe.probe_id == target:
                return row.estimated_cost
        raise KeyError(f"probe is outside experiment design: {target}")

    def _semantic_state(self) -> dict[str, object]:
        return {
            "reasoning_hypothesis_id": self.reasoning_hypothesis_id,
            "verification_plan_id": self.verification_plan_id,
            "version_space_id": self.version_space_id,
            "probes": [row.to_state() for row in self.probes],
            "max_selection_oracle_calls": self.max_selection_oracle_calls,
            "max_total_cost": self.max_total_cost,
            "stop_condition_ids": list(self.stop_condition_ids),
        }

    def to_state(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "design_id": self.design_id,
            **self._semantic_state(),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ExperimentDesign":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported experiment-design schema")
        raw_probes = _sequence(state.get("probes", ()), "planned probe state")
        probes: list[PlannedExperimentProbe] = []
        for raw in raw_probes:
            if not isinstance(raw, Mapping):
                raise TypeError("planned probe state rows must be mappings")
            probes.append(PlannedExperimentProbe.from_state(raw))
        row = cls(
            reasoning_hypothesis_id=state["reasoning_hypothesis_id"],
            verification_plan_id=state["verification_plan_id"],
            version_space_id=state["version_space_id"],
            probes=tuple(probes),
            max_selection_oracle_calls=state["max_selection_oracle_calls"],
            max_total_cost=state["max_total_cost"],
            stop_condition_ids=tuple(
                _sequence(state.get("stop_condition_ids", ()), "stop condition id state")
            ),
        )
        if str(state.get("design_id")) != row.design_id:
            raise ValueError("experiment design id does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical experiment design state")
        return row


@dataclass(frozen=True, slots=True)
class ExperimentDesignExecutionReceipt:
    design_id: str
    reasoning_hypothesis_id: str
    verification_plan_id: str
    experiment_id: str
    selected_hypothesis_id: str
    executed_selection_probe_ids: tuple[str, ...]
    verification_probe_ids: tuple[str, ...]
    selection_oracle_calls: int
    verification_oracle_calls: int
    actual_cost: float
    promoted: bool = False
    receipt_id: str = field(init=False)

    def __post_init__(self) -> None:
        for field_name in (
            "design_id",
            "reasoning_hypothesis_id",
            "verification_plan_id",
            "experiment_id",
            "selected_hypothesis_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _nonempty(getattr(self, field_name), field_name.replace("_", " ")),
            )
        object.__setattr__(
            self,
            "executed_selection_probe_ids",
            _normalized_ids(
                self.executed_selection_probe_ids,
                "executed selection probe ids",
                minimum=1,
            ),
        )
        object.__setattr__(
            self,
            "verification_probe_ids",
            _normalized_ids(self.verification_probe_ids, "verification probe ids", minimum=1),
        )
        object.__setattr__(
            self,
            "selection_oracle_calls",
            _positive_int(self.selection_oracle_calls, "selection oracle calls"),
        )
        object.__setattr__(
            self,
            "verification_oracle_calls",
            _positive_int(self.verification_oracle_calls, "verification oracle calls"),
        )
        actual_cost = _positive_finite(self.actual_cost, "actual experiment cost")
        object.__setattr__(self, "actual_cost", actual_cost)
        if bool(self.promoted):
            raise ValueError("experiment-design execution receipts cannot self-promote")
        object.__setattr__(self, "promoted", False)
        object.__setattr__(self, "receipt_id", _identity("experiment-design-execution", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "design_id": self.design_id,
            "reasoning_hypothesis_id": self.reasoning_hypothesis_id,
            "verification_plan_id": self.verification_plan_id,
            "experiment_id": self.experiment_id,
            "selected_hypothesis_id": self.selected_hypothesis_id,
            "executed_selection_probe_ids": list(self.executed_selection_probe_ids),
            "verification_probe_ids": list(self.verification_probe_ids),
            "selection_oracle_calls": self.selection_oracle_calls,
            "verification_oracle_calls": self.verification_oracle_calls,
            "actual_cost": self.actual_cost,
            "promoted": False,
        }

    def to_state(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "receipt_id": self.receipt_id,
            **self._semantic_state(),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ExperimentDesignExecutionReceipt":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported experiment-design execution schema")
        row = cls(
            design_id=state["design_id"],
            reasoning_hypothesis_id=state["reasoning_hypothesis_id"],
            verification_plan_id=state["verification_plan_id"],
            experiment_id=state["experiment_id"],
            selected_hypothesis_id=state["selected_hypothesis_id"],
            executed_selection_probe_ids=tuple(
                _sequence(
                    state.get("executed_selection_probe_ids", ()),
                    "executed selection probe state",
                )
            ),
            verification_probe_ids=tuple(
                _sequence(state.get("verification_probe_ids", ()), "verification probe state")
            ),
            selection_oracle_calls=state["selection_oracle_calls"],
            verification_oracle_calls=state["verification_oracle_calls"],
            actual_cost=state["actual_cost"],
            promoted=bool(state.get("promoted", False)),
        )
        if str(state.get("receipt_id")) != row.receipt_id:
            raise ValueError("execution receipt id does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical experiment-design execution state")
        return row


def bind_experiment_design_execution(
    design: ExperimentDesign,
    receipt: ShadowExperimentReceipt,
) -> ExperimentDesignExecutionReceipt:
    if not isinstance(design, ExperimentDesign):
        raise TypeError("design must be ExperimentDesign")
    if not isinstance(receipt, ShadowExperimentReceipt):
        raise TypeError("receipt must be ShadowExperimentReceipt")
    if receipt.status != "accept" or receipt.selected is None:
        raise ValueError("experiment design can bind only an independently verified accepted receipt")
    if receipt.promoted:
        raise ValueError("promoted shadow receipts are outside experiment-design authority")
    if _version_space_id(receipt.version_space_hypothesis_ids) != design.version_space_id:
        raise ValueError("receipt version space does not match experiment design")
    if tuple(receipt.selection_probe_ids) != design.selection_probe_ids:
        raise ValueError("receipt selection probes do not match experiment design")
    if tuple(receipt.verification_probe_ids) != design.verification_probe_ids:
        raise ValueError("receipt verification probes do not match experiment design")
    if receipt.max_selection_oracle_calls > design.max_selection_oracle_calls:
        raise ValueError("receipt selection budget exceeds experiment design")

    executed_selection_probe_ids = tuple(row.probe.probe_id for row in receipt.rounds)
    if receipt.selection_oracle_calls != len(executed_selection_probe_ids):
        raise ValueError("receipt selection calls are not fully provenance-bound")
    if receipt.verification_oracle_calls != len(design.verification_probe_ids):
        raise ValueError("receipt did not execute every independent verification probe")

    actual_cost = sum(design.cost_for_probe_id(pid) for pid in executed_selection_probe_ids)
    actual_cost += sum(design.cost_for_probe_id(pid) for pid in design.verification_probe_ids)
    if actual_cost > design.max_total_cost + 1e-12:
        raise ValueError("executed experiment cost exceeds experiment design")

    return ExperimentDesignExecutionReceipt(
        design_id=design.design_id,
        reasoning_hypothesis_id=design.reasoning_hypothesis_id,
        verification_plan_id=design.verification_plan_id,
        experiment_id=receipt.experiment_id,
        selected_hypothesis_id=receipt.selected.hypothesis_id,
        executed_selection_probe_ids=executed_selection_probe_ids,
        verification_probe_ids=design.verification_probe_ids,
        selection_oracle_calls=receipt.selection_oracle_calls,
        verification_oracle_calls=receipt.verification_oracle_calls,
        actual_cost=actual_cost,
        promoted=False,
    )


__all__ = (
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "SCHEMA_VERSION",
    "DESIGN_LINEAGE",
    "ExperimentProbeRole",
    "PlannedExperimentProbe",
    "ExperimentDesign",
    "ExperimentDesignExecutionReceipt",
    "bind_experiment_design_execution",
)
