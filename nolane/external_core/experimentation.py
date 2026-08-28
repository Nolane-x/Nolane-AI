from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

from .causal import InterventionSpec
from .evidence import EvidenceRecord


COMPONENT_ID = "external.experimentation"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder R2.60 active-probe lineage"
_LEDGER_SCHEMA_VERSION = 1


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


def _digest(prefix: str, value: object) -> str:
    raw = _canonical_json(value).encode("utf-8")
    return f"{prefix}{hashlib.sha256(raw).hexdigest()}"


def _nonempty(value: object, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _json_scalar(value: object) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("probe values must be finite")
        return value
    raise TypeError("probe args must be finite JSON scalar values")


def _outcome_json(value: object) -> str:
    return _canonical_json(value)


@dataclass(frozen=True, slots=True)
class ExperimentProbe:
    """Pure experiment description. It never executes its intervention itself."""

    args: tuple[object, ...]
    intervention: InterventionSpec | None = None

    def __post_init__(self) -> None:
        args = tuple(_json_scalar(value) for value in tuple(self.args))
        if not args:
            raise ValueError("probe args must be non-empty")
        if self.intervention is not None and not isinstance(self.intervention, InterventionSpec):
            raise TypeError("intervention must be an InterventionSpec or None")
        object.__setattr__(self, "args", args)

    @property
    def probe_id(self) -> str:
        # Preserve R2.60 plain-probe hash ordering for exact deterministic
        # tie parity while extending semantic identity for interventions.
        if self.intervention is None:
            payload: object = list(self.args)
        else:
            payload = {
                "args": list(self.args),
                "intervention": self.intervention.to_state(),
            }
        return _digest("xprobe:", payload)

    def to_state(self) -> dict[str, object]:
        return {
            "args": list(self.args),
            "intervention": self.intervention.to_state() if self.intervention is not None else None,
            "probe_id": self.probe_id,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ExperimentProbe":
        raw_args = state.get("args")
        if not isinstance(raw_args, Sequence) or isinstance(raw_args, (str, bytes)):
            raise TypeError("probe state args must be a sequence")
        raw_intervention = state.get("intervention")
        intervention = None
        if raw_intervention is not None:
            if not isinstance(raw_intervention, Mapping):
                raise TypeError("probe intervention state must be a mapping")
            intervention = InterventionSpec.from_state(raw_intervention)
        probe = cls(tuple(raw_args), intervention=intervention)
        expected = state.get("probe_id")
        if expected is not None and str(expected) != probe.probe_id:
            raise ValueError("probe id does not match canonical content")
        return probe


@dataclass(frozen=True, slots=True)
class ExperimentHypothesis:
    """Finite behavioral hypothesis over probe IDs.

    Prediction outcomes are canonicalized to JSON text internally so caller-owned
    lists/dicts cannot mutate semantic identity after construction. display_name is
    intentionally excluded from semantic identity.
    """

    predictions: tuple[tuple[str, object], ...]
    display_name: str = ""

    def __post_init__(self) -> None:
        normalized: list[tuple[str, str]] = []
        seen: set[str] = set()
        for probe_id, outcome in tuple(self.predictions):
            pid = _nonempty(probe_id, "probe_id")
            if pid in seen:
                raise ValueError("duplicate probe prediction")
            seen.add(pid)
            normalized.append((pid, _outcome_json(outcome)))
        if not normalized:
            raise ValueError("hypothesis predictions must be non-empty")
        normalized.sort(key=lambda row: row[0])
        object.__setattr__(self, "predictions", tuple(normalized))
        object.__setattr__(self, "display_name", str(self.display_name))

    @property
    def hypothesis_id(self) -> str:
        return _digest("xhyp:", self.semantic_state())

    def semantic_state(self) -> dict[str, object]:
        return {
            "predictions": [
                [probe_id, json.loads(str(outcome_json))]
                for probe_id, outcome_json in self.predictions
            ]
        }

    def prediction_key(self, probe_id: str) -> str:
        target = str(probe_id)
        for pid, outcome_json in self.predictions:
            if pid == target:
                return str(outcome_json)
        raise KeyError(f"hypothesis has no prediction for probe {target}")

    def to_state(self) -> dict[str, object]:
        state = self.semantic_state()
        state["display_name"] = self.display_name
        state["hypothesis_id"] = self.hypothesis_id
        return state

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ExperimentHypothesis":
        raw = state.get("predictions")
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            raise TypeError("hypothesis state predictions must be a sequence")
        predictions: list[tuple[str, object]] = []
        for row in raw:
            if not isinstance(row, Sequence) or isinstance(row, (str, bytes)) or len(row) != 2:
                raise ValueError("prediction rows must contain probe id and outcome")
            predictions.append((str(row[0]), row[1]))
        result = cls(tuple(predictions), display_name=str(state.get("display_name", "")))
        expected = state.get("hypothesis_id")
        if expected is not None and str(expected) != result.hypothesis_id:
            raise ValueError("hypothesis id does not match canonical content")
        return result


@dataclass(frozen=True, slots=True)
class VersionSpace:
    hypotheses: tuple[ExperimentHypothesis, ...]

    def __post_init__(self) -> None:
        rows = tuple(self.hypotheses)
        if not rows:
            raise ValueError("version space must be non-empty")
        if not all(isinstance(row, ExperimentHypothesis) for row in rows):
            raise TypeError("version space requires ExperimentHypothesis rows")
        ids = [row.hypothesis_id for row in rows]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate semantic hypothesis in version space")
        object.__setattr__(self, "hypotheses", tuple(sorted(rows, key=lambda row: row.hypothesis_id)))

    @property
    def version_space_id(self) -> str:
        return _digest("xspace:", {"hypothesis_ids": [row.hypothesis_id for row in self.hypotheses]})

    def to_state(self) -> dict[str, object]:
        return {
            "hypotheses": [row.to_state() for row in self.hypotheses],
            "version_space_id": self.version_space_id,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "VersionSpace":
        raw = state.get("hypotheses")
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            raise TypeError("version-space state hypotheses must be a sequence")
        rows: list[ExperimentHypothesis] = []
        for item in raw:
            if not isinstance(item, Mapping):
                raise TypeError("version-space hypothesis state must be a mapping")
            rows.append(ExperimentHypothesis.from_state(item))
        result = cls(tuple(rows))
        expected = state.get("version_space_id")
        if expected is not None and str(expected) != result.version_space_id:
            raise ValueError("version-space id does not match canonical content")
        return result


@dataclass(frozen=True, slots=True)
class ProbeSelectionReceipt:
    status: str
    probe: ExperimentProbe | None
    version_space_size: int
    partition_count: int
    largest_partition: int
    partition_signature: tuple[int, ...]
    probes_considered: int
    reason: str


@dataclass(frozen=True, slots=True)
class ExperimentRound:
    round_index: int
    probe: ExperimentProbe
    survivors_before: int
    survivors_after: int
    partition_count: int
    largest_partition: int
    partition_signature: tuple[int, ...]
    observed_outcome_json: str

    def to_state(self) -> dict[str, object]:
        return {
            "round_index": self.round_index,
            "probe": self.probe.to_state(),
            "survivors_before": self.survivors_before,
            "survivors_after": self.survivors_after,
            "partition_count": self.partition_count,
            "largest_partition": self.largest_partition,
            "partition_signature": list(self.partition_signature),
            "observed_outcome": json.loads(self.observed_outcome_json),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ExperimentRound":
        raw_probe = state.get("probe")
        if not isinstance(raw_probe, Mapping):
            raise TypeError("experiment round probe state must be a mapping")
        signature = tuple(int(value) for value in state.get("partition_signature", ()))
        return cls(
            int(state["round_index"]),
            ExperimentProbe.from_state(raw_probe),
            int(state["survivors_before"]),
            int(state["survivors_after"]),
            int(state["partition_count"]),
            int(state["largest_partition"]),
            signature,
            _outcome_json(state.get("observed_outcome")),
        )


def _unique_probes(probes: Sequence[ExperimentProbe], name: str) -> tuple[ExperimentProbe, ...]:
    rows = tuple(probes)
    if not rows:
        raise ValueError(f"{name} must be non-empty")
    if not all(isinstance(row, ExperimentProbe) for row in rows):
        raise TypeError(f"{name} must contain ExperimentProbe rows")
    by_id: dict[str, ExperimentProbe] = {}
    for row in rows:
        if row.probe_id in by_id:
            raise ValueError(f"{name} contains duplicate semantic probes")
        by_id[row.probe_id] = row
    return tuple(by_id[key] for key in sorted(by_id))


def _partitions(
    hypotheses: Sequence[ExperimentHypothesis],
    probe: ExperimentProbe,
) -> dict[str, tuple[ExperimentHypothesis, ...]]:
    buckets: dict[str, list[ExperimentHypothesis]] = {}
    for hypothesis in hypotheses:
        try:
            key = hypothesis.prediction_key(probe.probe_id)
        except KeyError as exc:
            raise ValueError("probe is not defined across the entire version space") from exc
        buckets.setdefault(key, []).append(hypothesis)
    return {key: tuple(rows) for key, rows in buckets.items()}


def select_informative_probe(
    version_space: VersionSpace,
    probes: Sequence[ExperimentProbe],
    *,
    excluded_probe_ids: Sequence[str] = (),
) -> ProbeSelectionReceipt:
    if not isinstance(version_space, VersionSpace):
        raise TypeError("version_space must be VersionSpace")
    rows = _unique_probes(probes, "probes")
    excluded = {str(value) for value in excluded_probe_ids}
    best_probe: ExperimentProbe | None = None
    best_signature: tuple[int, ...] = ()
    best_partition_count = 0
    best_largest = 0
    best_rank: tuple[object, ...] | None = None
    considered = 0

    for probe in rows:
        if probe.probe_id in excluded:
            continue
        considered += 1
        buckets = _partitions(version_space.hypotheses, probe)
        if len(buckets) <= 1:
            continue
        signature = tuple(sorted(len(bucket) for bucket in buckets.values()))
        rank = (
            signature[-1],
            sum(size * size for size in signature),
            -len(signature),
            probe.probe_id,
        )
        if best_rank is None or rank < best_rank:
            best_rank = rank
            best_probe = probe
            best_signature = signature
            best_partition_count = len(buckets)
            best_largest = signature[-1]

    if best_probe is None:
        return ProbeSelectionReceipt(
            "abstain",
            None,
            len(version_space.hypotheses),
            0,
            len(version_space.hypotheses),
            (),
            considered,
            "no_informative_probe",
        )
    return ProbeSelectionReceipt(
        "selected",
        best_probe,
        len(version_space.hypotheses),
        best_partition_count,
        best_largest,
        best_signature,
        considered,
        "maximally_discriminating_probe",
    )


def _experiment_id(
    version_space: VersionSpace,
    probes: Sequence[ExperimentProbe],
    verification_probes: Sequence[ExperimentProbe],
    budget: int,
) -> str:
    return _digest(
        "xexp:",
        {
            "version_space_id": version_space.version_space_id,
            "selection_probe_ids": [row.probe_id for row in probes],
            "verification_probe_ids": [row.probe_id for row in verification_probes],
            "max_selection_oracle_calls": budget,
        },
    )


@dataclass(frozen=True, slots=True)
class ShadowExperimentReceipt:
    experiment_id: str
    status: str
    selected: ExperimentHypothesis | None
    initial_survivors: int
    final_survivors: int
    selection_oracle_calls: int
    verification_oracle_calls: int
    rounds: tuple[ExperimentRound, ...]
    verification_failures: int
    reason: str
    promoted: bool = False
    trainable_parameter_count: int = 0

    def __post_init__(self) -> None:
        _nonempty(self.experiment_id, "experiment_id")
        if self.status not in {"accept", "abstain"}:
            raise ValueError("shadow experiment status must be accept or abstain")
        if self.promoted:
            raise ValueError("shadow experiment receipts cannot self-promote")
        for value in (
            self.initial_survivors,
            self.final_survivors,
            self.selection_oracle_calls,
            self.verification_oracle_calls,
            self.verification_failures,
            self.trainable_parameter_count,
        ):
            if int(value) < 0:
                raise ValueError("shadow experiment counters must be non-negative")
        if self.status == "accept" and self.selected is None:
            raise ValueError("accepted shadow experiment requires selected hypothesis")
        if self.status != "accept" and self.selected is not None:
            raise ValueError("abstained shadow experiment cannot expose a selected hypothesis")

    @property
    def oracle_calls_total(self) -> int:
        return self.selection_oracle_calls + self.verification_oracle_calls

    def to_state(self) -> dict[str, object]:
        return {
            "experiment_id": self.experiment_id,
            "status": self.status,
            "selected": self.selected.to_state() if self.selected is not None else None,
            "initial_survivors": self.initial_survivors,
            "final_survivors": self.final_survivors,
            "selection_oracle_calls": self.selection_oracle_calls,
            "verification_oracle_calls": self.verification_oracle_calls,
            "rounds": [row.to_state() for row in self.rounds],
            "verification_failures": self.verification_failures,
            "reason": self.reason,
            "promoted": False,
            "trainable_parameter_count": self.trainable_parameter_count,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ShadowExperimentReceipt":
        raw_selected = state.get("selected")
        selected = None
        if raw_selected is not None:
            if not isinstance(raw_selected, Mapping):
                raise TypeError("selected hypothesis state must be a mapping")
            selected = ExperimentHypothesis.from_state(raw_selected)
        raw_rounds = state.get("rounds", ())
        if not isinstance(raw_rounds, Sequence) or isinstance(raw_rounds, (str, bytes)):
            raise TypeError("experiment rounds state must be a sequence")
        rounds: list[ExperimentRound] = []
        for row in raw_rounds:
            if not isinstance(row, Mapping):
                raise TypeError("experiment round state must be a mapping")
            rounds.append(ExperimentRound.from_state(row))
        if bool(state.get("promoted", False)):
            raise ValueError("restored shadow experiment cannot be promoted")
        return cls(
            str(state["experiment_id"]),
            str(state["status"]),
            selected,
            int(state["initial_survivors"]),
            int(state["final_survivors"]),
            int(state["selection_oracle_calls"]),
            int(state["verification_oracle_calls"]),
            tuple(rounds),
            int(state.get("verification_failures", 0)),
            str(state["reason"]),
            False,
            int(state.get("trainable_parameter_count", 0)),
        )


def _abstain(
    experiment_id: str,
    initial: int,
    final: int,
    selection_calls: int,
    verification_calls: int,
    rounds: Sequence[ExperimentRound],
    reason: str,
    *,
    verification_failures: int = 0,
) -> ShadowExperimentReceipt:
    return ShadowExperimentReceipt(
        experiment_id,
        "abstain",
        None,
        initial,
        final,
        selection_calls,
        verification_calls,
        tuple(rounds),
        verification_failures,
        reason,
    )


def run_shadow_experiment(
    version_space: VersionSpace,
    probes: Sequence[ExperimentProbe],
    oracle: Callable[[ExperimentProbe], object],
    *,
    verification_probes: Sequence[ExperimentProbe],
    max_selection_oracle_calls: int = 8,
) -> ShadowExperimentReceipt:
    """Disambiguate a finite version space without acquiring promotion authority.

    Probe scoring is prediction-only. The oracle is called only after a probe has
    been selected, and accepted selection is independently verified before the
    receipt can later be admitted to an ExperimentLedger with clean Evidence.
    """

    if not isinstance(version_space, VersionSpace):
        raise TypeError("version_space must be VersionSpace")
    if not callable(oracle):
        raise TypeError("oracle must be callable")
    selection_probes = _unique_probes(probes, "probes")
    verification = _unique_probes(verification_probes, "verification_probes")
    budget = int(max_selection_oracle_calls)
    if budget < 0:
        raise ValueError("max_selection_oracle_calls must be non-negative")

    experiment_id = _experiment_id(version_space, selection_probes, verification, budget)
    survivors = version_space.hypotheses
    initial = len(survivors)
    used: set[str] = set()
    rounds: list[ExperimentRound] = []
    selection_calls = 0
    verification_calls = 0

    while len(survivors) > 1:
        if selection_calls >= budget:
            return _abstain(
                experiment_id,
                initial,
                len(survivors),
                selection_calls,
                verification_calls,
                rounds,
                "selection_oracle_budget_exhausted",
            )
        current = VersionSpace(tuple(survivors))
        selection = select_informative_probe(
            current,
            selection_probes,
            excluded_probe_ids=tuple(used),
        )
        if selection.probe is None:
            return _abstain(
                experiment_id,
                initial,
                len(survivors),
                selection_calls,
                verification_calls,
                rounds,
                "no_informative_probe",
            )
        probe = selection.probe
        try:
            observed_key = _outcome_json(oracle(probe))
        except Exception:
            selection_calls += 1
            return _abstain(
                experiment_id,
                initial,
                len(survivors),
                selection_calls,
                verification_calls,
                rounds,
                "selection_oracle_error",
            )
        selection_calls += 1
        used.add(probe.probe_id)
        before = len(survivors)
        buckets = _partitions(survivors, probe)
        survivors = buckets.get(observed_key, ())
        rounds.append(
            ExperimentRound(
                len(rounds),
                probe,
                before,
                len(survivors),
                selection.partition_count,
                selection.largest_partition,
                selection.partition_signature,
                observed_key,
            )
        )
        if not survivors:
            return _abstain(
                experiment_id,
                initial,
                0,
                selection_calls,
                verification_calls,
                rounds,
                "oracle_outside_candidate_version_space",
            )

    selected = survivors[0]
    for probe in verification:
        try:
            expected_key = selected.prediction_key(probe.probe_id)
        except KeyError:
            return _abstain(
                experiment_id,
                initial,
                1,
                selection_calls,
                verification_calls,
                rounds,
                "verification_probe_outside_hypothesis",
                verification_failures=1,
            )
        try:
            observed_key = _outcome_json(oracle(probe))
        except Exception:
            verification_calls += 1
            return _abstain(
                experiment_id,
                initial,
                1,
                selection_calls,
                verification_calls,
                rounds,
                "independent_verification_failed",
                verification_failures=1,
            )
        verification_calls += 1
        if observed_key != expected_key:
            return _abstain(
                experiment_id,
                initial,
                1,
                selection_calls,
                verification_calls,
                rounds,
                "independent_verification_failed",
                verification_failures=1,
            )

    return ShadowExperimentReceipt(
        experiment_id,
        "accept",
        selected,
        initial,
        1,
        selection_calls,
        verification_calls,
        tuple(rounds),
        0,
        "shadow_experiment_verified",
    )


@dataclass(frozen=True, slots=True)
class ExperimentLedgerRecord:
    experiment_id: str
    receipt_state_json: str
    evidence: EvidenceRecord

    def __post_init__(self) -> None:
        _nonempty(self.experiment_id, "experiment_id")
        if not isinstance(self.evidence, EvidenceRecord):
            raise TypeError("ledger record evidence must be EvidenceRecord")
        raw = json.loads(str(self.receipt_state_json))
        if not isinstance(raw, Mapping):
            raise ValueError("receipt state must decode to a mapping")
        receipt = ShadowExperimentReceipt.from_state(raw)
        if receipt.experiment_id != self.experiment_id:
            raise ValueError("ledger experiment id does not match receipt")
        object.__setattr__(self, "receipt_state_json", _canonical_json(receipt.to_state()))

    @property
    def receipt(self) -> ShadowExperimentReceipt:
        raw = json.loads(self.receipt_state_json)
        if not isinstance(raw, Mapping):
            raise ValueError("receipt state must decode to a mapping")
        return ShadowExperimentReceipt.from_state(raw)

    @property
    def record_id(self) -> str:
        return _digest("xledger:", self.to_state())

    def to_state(self) -> dict[str, object]:
        return {
            "experiment_id": self.experiment_id,
            "receipt": json.loads(self.receipt_state_json),
            "evidence": self.evidence.to_state(),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ExperimentLedgerRecord":
        raw_receipt = state.get("receipt")
        raw_evidence = state.get("evidence")
        if not isinstance(raw_receipt, Mapping) or not isinstance(raw_evidence, Mapping):
            raise TypeError("ledger record requires receipt and evidence mappings")
        return cls(
            str(state["experiment_id"]),
            _canonical_json(raw_receipt),
            EvidenceRecord.from_state(raw_evidence),
        )


@dataclass(slots=True)
class ExperimentLedger:
    causal_basis_digest: str
    _records: dict[str, ExperimentLedgerRecord] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self.causal_basis_digest = _nonempty(self.causal_basis_digest, "causal_basis_digest")

    def register(
        self,
        receipt: ShadowExperimentReceipt,
        evidence: EvidenceRecord,
    ) -> ExperimentLedgerRecord:
        if not isinstance(receipt, ShadowExperimentReceipt):
            raise TypeError("receipt must be ShadowExperimentReceipt")
        if receipt.status != "accept" or receipt.selected is None or receipt.promoted:
            raise ValueError("experiment ledger requires a verified non-promoted shadow receipt")
        if not isinstance(evidence, EvidenceRecord) or not evidence.passed:
            raise ValueError("experiment ledger requires passing evidence")
        if evidence.false_accepts or evidence.regressions:
            raise ValueError("experiment ledger requires clean evidence")
        record = ExperimentLedgerRecord(
            receipt.experiment_id,
            _canonical_json(receipt.to_state()),
            evidence,
        )
        current = self._records.get(record.experiment_id)
        if current is not None:
            if current != record:
                raise ValueError("conflicting evidence for existing semantic experiment")
            return current
        self._records[record.experiment_id] = record
        return record

    @property
    def records(self) -> tuple[ExperimentLedgerRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))

    def to_state(self) -> dict[str, object]:
        return {
            "schema_version": _LEDGER_SCHEMA_VERSION,
            "component_id": COMPONENT_ID,
            "component_version": COMPONENT_VERSION,
            "causal_basis_digest": self.causal_basis_digest,
            "records": [row.to_state() for row in self.records],
        }

    @property
    def digest(self) -> str:
        return _digest("xledger-state:", self.to_state())

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ExperimentLedger":
        if int(state.get("schema_version", -1)) != _LEDGER_SCHEMA_VERSION:
            raise ValueError("unsupported experiment ledger schema version")
        if str(state.get("component_id", "")) != COMPONENT_ID:
            raise ValueError("experiment ledger component id mismatch")
        if str(state.get("component_version", "")) != COMPONENT_VERSION:
            raise ValueError("experiment ledger component version mismatch")
        result = cls(str(state["causal_basis_digest"]))
        raw_records = state.get("records", ())
        if not isinstance(raw_records, Sequence) or isinstance(raw_records, (str, bytes)):
            raise TypeError("experiment ledger records must be a sequence")
        for raw in raw_records:
            if not isinstance(raw, Mapping):
                raise TypeError("experiment ledger record state must be a mapping")
            record = ExperimentLedgerRecord.from_state(raw)
            if not record.evidence.passed:
                raise ValueError("restored experiment ledger requires passing evidence")
            if record.evidence.false_accepts or record.evidence.regressions:
                raise ValueError("restored experiment ledger requires clean evidence")
            receipt = record.receipt
            if receipt.status != "accept" or receipt.selected is None or receipt.promoted:
                raise ValueError("restored experiment ledger requires verified shadow receipts")
            if record.experiment_id in result._records:
                raise ValueError("duplicate experiment record in ledger state")
            result._records[record.experiment_id] = record
        return result


__all__ = (
    "ExperimentProbe",
    "ExperimentHypothesis",
    "VersionSpace",
    "ProbeSelectionReceipt",
    "ExperimentRound",
    "ShadowExperimentReceipt",
    "select_informative_probe",
    "run_shadow_experiment",
    "ExperimentLedgerRecord",
    "ExperimentLedger",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
