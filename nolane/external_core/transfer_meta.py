from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.assurance import AssuranceControlPlane, PromotionAssuranceReceipt
from nolane.external_core.causal import CausalProgramLedger
from nolane.external_core.reasoning_invention import TransferIntent
from nolane.external_core.transfer_trials import (
    DestinationTrialMatrix,
    DestinationTrialResult,
    NegativeTransferRegimeRecord,
    TransferTrialEnvelope,
)
from nolane.memory.experience import (
    AttributionRecord,
    ExperienceLedger,
    ExperienceOutcome,
    ExperienceRecord,
)


COMPONENT_ID = "external.transfer_meta"
COMPONENT_VERSION = "0.0.2"
MIGRATED_FROM = "cogcoder R2.69 autonomous transfer/meta-learning lineage"
_SCHEMA_VERSION = "transfer-meta-v2"
_LEGACY_SCHEMA_VERSION = "transfer-meta-v1"


def _nonempty(value: object, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _normalize_json(value: Any, *, path: str = "metadata") -> Any:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} numbers must be finite")
        return value
    if isinstance(value, Mapping):
        rows: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            if not isinstance(raw_key, str) or not raw_key.strip():
                raise ValueError(f"{path} keys must be non-empty strings")
            key = raw_key.strip()
            if key in rows:
                raise ValueError(f"{path} keys must be unique after normalization")
            rows[key] = _normalize_json(raw_value, path=f"{path}.{key}")
        return {key: rows[key] for key in sorted(rows)}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize_json(row, path=f"{path}[]") for row in value]
    raise TypeError(f"{path} must contain only finite JSON-compatible values")


def _canonical_json(value: Any) -> str:
    normalized = _normalize_json(value)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _json_object(text: str, *, name: str) -> dict[str, Any]:
    try:
        value = json.loads(str(text))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be canonical JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    canonical = _canonical_json(value)
    if canonical != str(text):
        raise ValueError(f"{name} JSON is not canonical")
    return value


def _clean_external_attribution(experience: ExperienceRecord, attribution: AttributionRecord) -> None:
    if attribution.experience_id != experience.experience_id:
        raise ValueError("attribution targets a different experience")
    evidence = attribution.evidence
    clean = evidence.passed and evidence.false_accepts == 0 and evidence.regressions == 0
    if not attribution.positive or not clean:
        raise ValueError("portable experience requires clean positive attribution")
    if attribution.verifier_agent_id == experience.agent_id:
        raise ValueError("portable experience requires verifier external to producer")
    if evidence.verifier_agent_id != attribution.verifier_agent_id:
        raise ValueError("attribution verifier does not match evidence verifier")


def _causal_row_digest(ledger: CausalProgramLedger, program_id: str) -> str:
    if not isinstance(ledger, CausalProgramLedger):
        raise TypeError("causal_ledger must be native CausalProgramLedger")
    wanted = _nonempty(program_id, "causal_program_id")
    state = ledger.to_state()
    for raw in state.get("programs", ()):
        if not isinstance(raw, Mapping):
            continue
        program = raw.get("program")
        if isinstance(program, Mapping) and str(program.get("program_id")) == wanted:
            return canonical_digest(dict(raw))
    raise KeyError(f"unknown accepted causal program: {wanted}")


@dataclass(frozen=True, slots=True)
class PortableExperience:
    source_domain: str
    learning_layer: str
    lesson: str
    causal_program_id: str | None
    portable_id: str

    def __post_init__(self) -> None:
        source_domain = _nonempty(self.source_domain, "source_domain")
        learning_layer = _nonempty(self.learning_layer, "learning_layer")
        lesson = _nonempty(self.lesson, "lesson")
        causal_program_id = None if self.causal_program_id is None else _nonempty(self.causal_program_id, "causal_program_id")
        payload = {
            "source_domain": source_domain,
            "learning_layer": learning_layer,
            "lesson": lesson,
            "causal_program_id": causal_program_id,
        }
        expected = f"portable:{canonical_digest(payload)}"
        if str(self.portable_id) != expected:
            raise ValueError("portable experience identity mismatch")
        object.__setattr__(self, "source_domain", source_domain)
        object.__setattr__(self, "learning_layer", learning_layer)
        object.__setattr__(self, "lesson", lesson)
        object.__setattr__(self, "causal_program_id", causal_program_id)
        object.__setattr__(self, "portable_id", expected)

    @classmethod
    def create(cls, *, source_domain: str, learning_layer: str, lesson: str, causal_program_id: str | None = None) -> "PortableExperience":
        payload = {
            "source_domain": _nonempty(source_domain, "source_domain"),
            "learning_layer": _nonempty(learning_layer, "learning_layer"),
            "lesson": _nonempty(lesson, "lesson"),
            "causal_program_id": None if causal_program_id is None else _nonempty(causal_program_id, "causal_program_id"),
        }
        return cls(portable_id=f"portable:{canonical_digest(payload)}", **payload)

    def semantic_state(self) -> dict[str, Any]:
        return {
            "source_domain": self.source_domain,
            "learning_layer": self.learning_layer,
            "lesson": self.lesson,
            "causal_program_id": self.causal_program_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {"portable_id": self.portable_id, **self.semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "PortableExperience":
        row = cls(
            source_domain=str(state["source_domain"]),
            learning_layer=str(state["learning_layer"]),
            lesson=str(state["lesson"]),
            causal_program_id=None if state.get("causal_program_id") is None else str(state["causal_program_id"]),
            portable_id=str(state["portable_id"]),
        )
        if row.to_state() != dict(state):
            raise ValueError("non-canonical portable experience state")
        return row


@dataclass(frozen=True, slots=True)
class PortableExperienceSourceReceipt:
    portable_id: str
    source_experience_id: str
    attribution_id: str
    source_experience_digest: str
    source_attribution_digest: str
    source_evidence_digest: str
    causal_row_digest: str | None
    source_authority_digest: str
    receipt_id: str

    def __post_init__(self) -> None:
        values = {
            "portable_id": _nonempty(self.portable_id, "portable_id"),
            "source_experience_id": _nonempty(self.source_experience_id, "source_experience_id"),
            "attribution_id": _nonempty(self.attribution_id, "attribution_id"),
            "source_experience_digest": _nonempty(self.source_experience_digest, "source_experience_digest"),
            "source_attribution_digest": _nonempty(self.source_attribution_digest, "source_attribution_digest"),
            "source_evidence_digest": _nonempty(self.source_evidence_digest, "source_evidence_digest"),
            "causal_row_digest": None if self.causal_row_digest is None else _nonempty(self.causal_row_digest, "causal_row_digest"),
        }
        expected_authority = f"transfer-source:{canonical_digest(values)}"
        if str(self.source_authority_digest) != expected_authority:
            raise ValueError("portable source authority digest mismatch")
        receipt_payload = {**values, "source_authority_digest": expected_authority}
        expected_receipt = f"transfer-source-receipt:{canonical_digest(receipt_payload)}"
        if str(self.receipt_id) != expected_receipt:
            raise ValueError("portable source receipt identity mismatch")
        for key, value in values.items():
            object.__setattr__(self, key, value)
        object.__setattr__(self, "source_authority_digest", expected_authority)
        object.__setattr__(self, "receipt_id", expected_receipt)

    @classmethod
    def create(cls, *, portable_id: str, source_experience_id: str, attribution_id: str, source_experience_digest: str, source_attribution_digest: str, source_evidence_digest: str, causal_row_digest: str | None) -> "PortableExperienceSourceReceipt":
        values = {
            "portable_id": _nonempty(portable_id, "portable_id"),
            "source_experience_id": _nonempty(source_experience_id, "source_experience_id"),
            "attribution_id": _nonempty(attribution_id, "attribution_id"),
            "source_experience_digest": _nonempty(source_experience_digest, "source_experience_digest"),
            "source_attribution_digest": _nonempty(source_attribution_digest, "source_attribution_digest"),
            "source_evidence_digest": _nonempty(source_evidence_digest, "source_evidence_digest"),
            "causal_row_digest": None if causal_row_digest is None else _nonempty(causal_row_digest, "causal_row_digest"),
        }
        authority = f"transfer-source:{canonical_digest(values)}"
        receipt_payload = {**values, "source_authority_digest": authority}
        return cls(**values, source_authority_digest=authority, receipt_id=f"transfer-source-receipt:{canonical_digest(receipt_payload)}")

    def to_state(self) -> dict[str, Any]:
        return {
            "portable_id": self.portable_id,
            "source_experience_id": self.source_experience_id,
            "attribution_id": self.attribution_id,
            "source_experience_digest": self.source_experience_digest,
            "source_attribution_digest": self.source_attribution_digest,
            "source_evidence_digest": self.source_evidence_digest,
            "causal_row_digest": self.causal_row_digest,
            "source_authority_digest": self.source_authority_digest,
            "receipt_id": self.receipt_id,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "PortableExperienceSourceReceipt":
        row = cls(
            portable_id=str(state["portable_id"]),
            source_experience_id=str(state["source_experience_id"]),
            attribution_id=str(state["attribution_id"]),
            source_experience_digest=str(state["source_experience_digest"]),
            source_attribution_digest=str(state["source_attribution_digest"]),
            source_evidence_digest=str(state["source_evidence_digest"]),
            causal_row_digest=None if state.get("causal_row_digest") is None else str(state["causal_row_digest"]),
            source_authority_digest=str(state["source_authority_digest"]),
            receipt_id=str(state["receipt_id"]),
        )
        if row.to_state() != dict(state):
            raise ValueError("non-canonical portable source receipt state")
        return row


@dataclass(frozen=True, slots=True)
class TransferAdaptation:
    portable_id: str
    source_domain: str
    target_domain: str
    metadata_json: str
    transfer_id: str

    def __post_init__(self) -> None:
        portable_id = _nonempty(self.portable_id, "portable_id")
        source_domain = _nonempty(self.source_domain, "source_domain")
        target_domain = _nonempty(self.target_domain, "target_domain")
        if source_domain == target_domain:
            raise ValueError("transfer target domain must differ from source domain")
        metadata = _json_object(self.metadata_json, name="transfer metadata")
        semantic = {"portable_id": portable_id, "source_domain": source_domain, "target_domain": target_domain, "metadata": metadata}
        expected = f"transfer:{canonical_digest(semantic)}"
        if str(self.transfer_id) != expected:
            raise ValueError("transfer adaptation identity mismatch")
        object.__setattr__(self, "portable_id", portable_id)
        object.__setattr__(self, "source_domain", source_domain)
        object.__setattr__(self, "target_domain", target_domain)
        object.__setattr__(self, "metadata_json", _canonical_json(metadata))
        object.__setattr__(self, "transfer_id", expected)

    @classmethod
    def create(cls, portable: PortableExperience, *, target_domain: str, metadata: Mapping[str, Any]) -> "TransferAdaptation":
        if not isinstance(portable, PortableExperience):
            raise TypeError("portable must be PortableExperience")
        normalized = _normalize_json(metadata)
        if not isinstance(normalized, dict):
            raise TypeError("transfer metadata must be a mapping")
        source_domain = portable.source_domain
        target = _nonempty(target_domain, "target_domain")
        semantic = {"portable_id": portable.portable_id, "source_domain": source_domain, "target_domain": target, "metadata": normalized}
        return cls(
            portable_id=portable.portable_id,
            source_domain=source_domain,
            target_domain=target,
            metadata_json=_canonical_json(normalized),
            transfer_id=f"transfer:{canonical_digest(semantic)}",
        )

    def metadata(self) -> dict[str, Any]:
        return _json_object(self.metadata_json, name="transfer metadata")

    def to_state(self) -> dict[str, Any]:
        return {"transfer_id": self.transfer_id, "portable_id": self.portable_id, "source_domain": self.source_domain, "target_domain": self.target_domain, "metadata": self.metadata()}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TransferAdaptation":
        metadata = state.get("metadata")
        if not isinstance(metadata, Mapping):
            raise ValueError("transfer adaptation metadata state is required")
        row = cls(
            portable_id=str(state["portable_id"]),
            source_domain=str(state["source_domain"]),
            target_domain=str(state["target_domain"]),
            metadata_json=_canonical_json(metadata),
            transfer_id=str(state["transfer_id"]),
        )
        if row.to_state() != dict(state):
            raise ValueError("non-canonical transfer adaptation state")
        return row


class TransferState(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    QUARANTINED = "quarantined"


@dataclass(frozen=True, slots=True)
class TransferRecord:
    adaptation: TransferAdaptation
    source_receipt_id: str
    state: TransferState
    acceptance_evidence_ids: tuple[str, ...] = ()
    assurance_receipt_id: str | None = None
    quarantine_reason: str | None = None
    transfer_intent_id: str | None = None
    trial_envelope_id: str | None = None
    trial_matrix_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.adaptation, TransferAdaptation):
            raise TypeError("adaptation must be TransferAdaptation")
        source_receipt_id = _nonempty(self.source_receipt_id, "source_receipt_id")
        state = TransferState(self.state)
        evidence = tuple(_nonempty(row, "acceptance evidence id") for row in self.acceptance_evidence_ids)
        if len(evidence) != len(set(evidence)):
            raise ValueError("acceptance evidence ids must be unique")
        assurance_id = None if self.assurance_receipt_id is None else _nonempty(self.assurance_receipt_id, "assurance_receipt_id")
        reason = None if self.quarantine_reason is None else _nonempty(self.quarantine_reason, "quarantine_reason")
        intent_id = None if self.transfer_intent_id is None else _nonempty(self.transfer_intent_id, "transfer_intent_id")
        envelope_id = None if self.trial_envelope_id is None else _nonempty(self.trial_envelope_id, "trial_envelope_id")
        matrix_id = None if self.trial_matrix_id is None else _nonempty(self.trial_matrix_id, "trial_matrix_id")
        if bool(intent_id) != bool(envelope_id):
            raise ValueError("governed transfer requires intent and trial envelope together")
        if state is TransferState.PROPOSED:
            if evidence or assurance_id or reason:
                raise ValueError("proposed transfer cannot carry acceptance or quarantine authority")
        elif state is TransferState.ACCEPTED:
            if not evidence or not assurance_id:
                raise ValueError("accepted transfer requires evidence and assurance receipt")
            if reason:
                raise ValueError("accepted transfer cannot carry quarantine reason")
            if intent_id is not None and matrix_id is None:
                raise ValueError("governed accepted transfer requires destination trial matrix")
        else:
            if not reason:
                raise ValueError("quarantined transfer requires reason")
            if bool(evidence) != bool(assurance_id):
                raise ValueError("quarantined transfer acceptance provenance must be complete or absent")
        object.__setattr__(self, "source_receipt_id", source_receipt_id)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "acceptance_evidence_ids", evidence)
        object.__setattr__(self, "assurance_receipt_id", assurance_id)
        object.__setattr__(self, "quarantine_reason", reason)
        object.__setattr__(self, "transfer_intent_id", intent_id)
        object.__setattr__(self, "trial_envelope_id", envelope_id)
        object.__setattr__(self, "trial_matrix_id", matrix_id)

    def to_state(self) -> dict[str, Any]:
        return {
            "adaptation": self.adaptation.to_state(),
            "source_receipt_id": self.source_receipt_id,
            "state": self.state.value,
            "acceptance_evidence_ids": list(self.acceptance_evidence_ids),
            "assurance_receipt_id": self.assurance_receipt_id,
            "quarantine_reason": self.quarantine_reason,
            "transfer_intent_id": self.transfer_intent_id,
            "trial_envelope_id": self.trial_envelope_id,
            "trial_matrix_id": self.trial_matrix_id,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TransferRecord":
        adaptation = state.get("adaptation")
        if not isinstance(adaptation, Mapping):
            raise ValueError("transfer record adaptation state is required")
        row = cls(
            adaptation=TransferAdaptation.from_state(adaptation),
            source_receipt_id=str(state["source_receipt_id"]),
            state=TransferState(str(state["state"])),
            acceptance_evidence_ids=tuple(str(x) for x in state.get("acceptance_evidence_ids", ())),
            assurance_receipt_id=None if state.get("assurance_receipt_id") is None else str(state["assurance_receipt_id"]),
            quarantine_reason=None if state.get("quarantine_reason") is None else str(state["quarantine_reason"]),
            transfer_intent_id=None if state.get("transfer_intent_id") is None else str(state["transfer_intent_id"]),
            trial_envelope_id=None if state.get("trial_envelope_id") is None else str(state["trial_envelope_id"]),
            trial_matrix_id=None if state.get("trial_matrix_id") is None else str(state["trial_matrix_id"]),
        )
        canonical = row.to_state()
        if set(state) == set(canonical) and canonical != dict(state):
            raise ValueError("non-canonical transfer record state")
        legacy = {key: value for key, value in canonical.items() if key not in {"transfer_intent_id", "trial_envelope_id", "trial_matrix_id"}}
        if set(state) == set(legacy) and legacy != dict(state):
            raise ValueError("non-canonical legacy transfer record state")
        if set(state) not in {frozenset(canonical), frozenset(legacy)}:
            raise ValueError("non-canonical transfer record fields")
        return row


class TransferMetaGovernor:
    """Verified portable-experience transfer and destination-trial reuse authority."""

    def __init__(self, *, experience: ExperienceLedger, causal: CausalProgramLedger | None = None) -> None:
        if not isinstance(experience, ExperienceLedger):
            raise TypeError("experience must be native ExperienceLedger")
        if causal is not None and not isinstance(causal, CausalProgramLedger):
            raise TypeError("causal must be native CausalProgramLedger or None")
        self.experience = experience
        self.causal = causal
        self._portables: dict[str, PortableExperience] = {}
        self._sources: dict[str, PortableExperienceSourceReceipt] = {}
        self._source_by_portable: dict[str, str] = {}
        self._records: dict[str, TransferRecord] = {}
        self._intents: dict[str, TransferIntent] = {}
        self._trial_envelopes: dict[str, TransferTrialEnvelope] = {}
        self._trial_matrices: dict[str, DestinationTrialMatrix] = {}
        self._negative_transfers: dict[str, NegativeTransferRegimeRecord] = {}

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    def _derive_source(self, experience_id: str, attribution_id: str, *, causal_program_id: str | None) -> tuple[PortableExperience, PortableExperienceSourceReceipt]:
        source = self.experience.get(_nonempty(experience_id, "experience_id"))
        if source.outcome is not ExperienceOutcome.SUCCESS:
            raise ValueError("portable experience requires successful source experience")
        attribution = self.experience.get_attribution(_nonempty(attribution_id, "attribution_id"))
        _clean_external_attribution(source, attribution)
        causal_digest: str | None = None
        causal_id: str | None = None
        if causal_program_id is not None:
            if self.causal is None:
                raise ValueError("causal program support requires native causal ledger")
            causal_id = _nonempty(causal_program_id, "causal_program_id")
            causal_digest = _causal_row_digest(self.causal, causal_id)
        portable = PortableExperience.create(source_domain=source.domain, learning_layer=attribution.learning_layer.value, lesson=attribution.lesson, causal_program_id=causal_id)
        receipt = PortableExperienceSourceReceipt.create(
            portable_id=portable.portable_id,
            source_experience_id=source.experience_id,
            attribution_id=attribution.attribution_id,
            source_experience_digest=canonical_digest(source.to_state()),
            source_attribution_digest=canonical_digest(attribution.to_state()),
            source_evidence_digest=canonical_digest(attribution.evidence.to_state()),
            causal_row_digest=causal_digest,
        )
        return portable, receipt

    def compile_portable(self, experience_id: str, attribution_id: str, *, causal_program_id: str | None = None) -> tuple[PortableExperience, PortableExperienceSourceReceipt]:
        portable, receipt = self._derive_source(experience_id, attribution_id, causal_program_id=causal_program_id)
        existing = self._portables.get(portable.portable_id)
        existing_source_id = self._source_by_portable.get(portable.portable_id)
        if existing is not None and existing != portable:
            raise ValueError("portable experience id cannot be rebound")
        if existing_source_id is not None and existing_source_id != receipt.receipt_id:
            raise ValueError("portable experience already has different source authority")
        existing_receipt = self._sources.get(receipt.receipt_id)
        if existing_receipt is not None and existing_receipt != receipt:
            raise ValueError("portable source receipt id cannot be rebound")
        self._portables[portable.portable_id] = portable
        self._sources[receipt.receipt_id] = receipt
        self._source_by_portable[portable.portable_id] = receipt.receipt_id
        return portable, receipt

    def portable(self, portable_id: str) -> PortableExperience:
        try:
            return self._portables[str(portable_id)]
        except KeyError:
            raise KeyError(str(portable_id)) from None

    def source_receipt(self, receipt_id: str) -> PortableExperienceSourceReceipt:
        try:
            return self._sources[str(receipt_id)]
        except KeyError:
            raise KeyError(str(receipt_id)) from None

    def propose(
        self,
        portable_id: str,
        *,
        target_domain: str | None = None,
        intent: TransferIntent | None = None,
        metadata: Mapping[str, Any],
    ) -> TransferRecord:
        portable = self.portable(portable_id)
        source_receipt_id = self._source_by_portable[portable.portable_id]
        envelope: TransferTrialEnvelope | None = None
        if intent is not None:
            if not isinstance(intent, TransferIntent):
                raise TypeError("intent must be TransferIntent")
            if intent.source_domain != portable.source_domain:
                raise ValueError("transfer intent source domain does not match portable experience")
            if source_receipt_id not in intent.source_receipt_ids:
                raise ValueError("transfer intent does not bind the portable source receipt")
            if target_domain is not None and str(target_domain) != intent.target_domain:
                raise ValueError("explicit target domain conflicts with transfer intent")
            target = intent.target_domain
        else:
            if target_domain is None:
                raise TypeError("target_domain or intent is required")
            target = _nonempty(target_domain, "target_domain")
        adaptation = TransferAdaptation.create(portable, target_domain=target, metadata=dict(metadata))
        if adaptation.transfer_id in self._records:
            raise ValueError("duplicate transfer adaptation identity")
        if intent is not None:
            envelope = TransferTrialEnvelope.create(intent, adaptation)
            existing_intent = self._intents.get(intent.transfer_intent_id)
            if existing_intent is not None and existing_intent != intent:
                raise ValueError("transfer intent identity cannot be rebound")
            self._intents[intent.transfer_intent_id] = intent
            self._trial_envelopes[envelope.envelope_id] = envelope
        row = TransferRecord(
            adaptation=adaptation,
            source_receipt_id=source_receipt_id,
            state=TransferState.PROPOSED,
            transfer_intent_id=None if intent is None else intent.transfer_intent_id,
            trial_envelope_id=None if envelope is None else envelope.envelope_id,
        )
        self._records[adaptation.transfer_id] = row
        return row

    def record(self, transfer_id: str) -> TransferRecord:
        try:
            return self._records[str(transfer_id)]
        except KeyError:
            raise KeyError(str(transfer_id)) from None

    def record_destination_trials(self, transfer_id: str, *, results: Sequence[DestinationTrialResult]) -> DestinationTrialMatrix:
        record = self.record(transfer_id)
        if record.state is not TransferState.PROPOSED:
            raise ValueError("destination trials can be recorded only for proposed transfer")
        if record.trial_envelope_id is None:
            raise ValueError("destination trial matrix requires a TransferIntent-governed proposal")
        envelope = self._trial_envelopes.get(record.trial_envelope_id)
        if envelope is None:
            raise ValueError("destination trial envelope is missing")
        matrix = DestinationTrialMatrix.create(envelope, tuple(results))
        existing = self._trial_matrices.get(matrix.matrix_id)
        if existing is not None and existing != matrix:
            raise ValueError("destination trial matrix identity cannot be rebound")
        if record.trial_matrix_id is not None and record.trial_matrix_id != matrix.matrix_id:
            raise ValueError("transfer already has a different destination trial matrix")
        self._trial_matrices[matrix.matrix_id] = matrix
        self._records[record.adaptation.transfer_id] = replace(record, trial_matrix_id=matrix.matrix_id)
        return matrix

    def _validated_assurance(self, record: TransferRecord, *, assurance: AssuranceControlPlane, receipt: PromotionAssuranceReceipt, evidence_ids: tuple[str, ...]) -> PromotionAssuranceReceipt:
        if not isinstance(assurance, AssuranceControlPlane):
            raise TypeError("assurance must be native AssuranceControlPlane")
        if not isinstance(receipt, PromotionAssuranceReceipt):
            raise TypeError("receipt must be native PromotionAssuranceReceipt")
        validated = PromotionAssuranceReceipt.from_state(receipt.to_state())
        persisted = assurance.promotion_receipt(validated.receipt_id)
        if not isinstance(persisted, PromotionAssuranceReceipt):
            raise TypeError("persisted assurance receipt must be native PromotionAssuranceReceipt")
        persisted_validated = PromotionAssuranceReceipt.from_state(persisted.to_state())
        if persisted_validated != validated:
            raise ValueError("transfer requires exact persisted assurance receipt")
        if not validated.authorized:
            raise ValueError("transfer assurance receipt is not authorized")
        if validated.subject_id != record.adaptation.transfer_id:
            raise ValueError("transfer assurance receipt subject mismatch")
        evidence = tuple(_nonempty(row, "acceptance evidence id") for row in evidence_ids)
        if not evidence or len(evidence) != len(set(evidence)):
            raise ValueError("transfer acceptance requires unique evidence ids")
        if validated.evidence_ids != evidence:
            raise ValueError("transfer assurance receipt evidence mismatch")
        source = self.source_receipt(record.source_receipt_id)
        if validated.predecessor_version != source.source_authority_digest:
            raise ValueError("transfer assurance source authority mismatch")
        return validated

    def accept(
        self,
        transfer_id: str,
        *,
        assurance: AssuranceControlPlane,
        receipt: PromotionAssuranceReceipt,
        evidence_ids: tuple[str, ...],
        trial_matrix_id: str | None = None,
    ) -> TransferRecord:
        record = self.record(transfer_id)
        if record.state is TransferState.QUARANTINED:
            raise ValueError("quarantined transfer cannot be accepted")
        if record.state is not TransferState.PROPOSED:
            raise ValueError("only proposed transfer can be accepted")
        if record.transfer_intent_id is not None:
            if record.trial_matrix_id is None:
                raise ValueError("governed transfer requires destination trial matrix")
            requested_matrix = _nonempty(trial_matrix_id, "trial_matrix_id") if trial_matrix_id is not None else None
            if requested_matrix != record.trial_matrix_id:
                raise ValueError("trial matrix does not match governed transfer")
            matrix = self._trial_matrices.get(record.trial_matrix_id)
            if matrix is None:
                raise ValueError("destination trial matrix is missing")
            if not matrix.passed:
                raise ValueError("destination trial matrix did not pass")
            expected_evidence = (matrix.matrix_id, *matrix.evidence_ids)
            if tuple(evidence_ids) != expected_evidence:
                raise ValueError("governed transfer evidence must bind exact destination trial matrix")
        elif trial_matrix_id is not None:
            raise ValueError("legacy transfer has no destination trial matrix authority")
        validated = self._validated_assurance(record, assurance=assurance, receipt=receipt, evidence_ids=evidence_ids)
        updated = replace(record, state=TransferState.ACCEPTED, acceptance_evidence_ids=validated.evidence_ids, assurance_receipt_id=validated.receipt_id)
        self._records[record.adaptation.transfer_id] = updated
        return updated

    def quarantine(self, transfer_id: str, *, reason: str) -> TransferRecord:
        record = self.record(transfer_id)
        if record.state is TransferState.QUARANTINED:
            raise ValueError("transfer is already quarantined")
        updated = replace(record, state=TransferState.QUARANTINED, quarantine_reason=_nonempty(reason, "quarantine reason"))
        self._records[record.adaptation.transfer_id] = updated
        return updated

    def report_negative_transfer(
        self,
        transfer_id: str,
        *,
        reason: str,
        target_regime_id: str | None = None,
        evidence_ids: tuple[str, ...] = (),
    ) -> TransferRecord | NegativeTransferRegimeRecord:
        record = self.record(transfer_id)
        if record.state is not TransferState.ACCEPTED:
            raise ValueError("negative-transfer revocation requires accepted transfer")
        if target_regime_id is None:
            if evidence_ids:
                raise ValueError("negative-transfer evidence requires target regime id")
            return self.quarantine(transfer_id, reason=reason)
        negative = NegativeTransferRegimeRecord(
            transfer_id=record.adaptation.transfer_id,
            target_domain=record.adaptation.target_domain,
            target_regime_id=target_regime_id,
            evidence_ids=evidence_ids,
            reason=reason,
        )
        existing = self._negative_transfers.get(negative.record_id)
        if existing is not None and existing != negative:
            raise ValueError("negative transfer regime record identity cannot be rebound")
        self._negative_transfers[negative.record_id] = negative
        self.quarantine(transfer_id, reason=reason)
        return negative

    def negative_transfer_records(self, *, target_domain: str | None = None, target_regime_id: str | None = None) -> tuple[NegativeTransferRegimeRecord, ...]:
        domain = None if target_domain is None else _nonempty(target_domain, "target_domain")
        regime = None if target_regime_id is None else _nonempty(target_regime_id, "target_regime_id")
        return tuple(
            row
            for row in sorted(self._negative_transfers.values(), key=lambda item: item.record_id)
            if (domain is None or row.target_domain == domain)
            and (regime is None or row.target_regime_id == regime)
        )

    def reusable_ids(self, *, target_domain: str | None = None) -> tuple[str, ...]:
        domain = None if target_domain is None else _nonempty(target_domain, "target_domain")
        return tuple(key for key in sorted(self._records) if self._records[key].state is TransferState.ACCEPTED and (domain is None or self._records[key].adaptation.target_domain == domain))

    def resolve(self, transfer_id: str) -> tuple[PortableExperience, TransferAdaptation]:
        record = self.record(transfer_id)
        if record.state is not TransferState.ACCEPTED:
            raise PermissionError("transfer is not accepted for reuse")
        return self.portable(record.adaptation.portable_id), record.adaptation

    def to_state(self) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "component_id": COMPONENT_ID,
            "component_version": COMPONENT_VERSION,
            "portables": [self._portables[key].to_state() for key in sorted(self._portables)],
            "sources": [self._sources[key].to_state() for key in sorted(self._sources)],
            "records": [self._records[key].to_state() for key in sorted(self._records)],
            "intents": [self._intents[key].to_state() for key in sorted(self._intents)],
            "trial_envelopes": [self._trial_envelopes[key].to_state() for key in sorted(self._trial_envelopes)],
            "trial_matrices": [self._trial_matrices[key].to_state() for key in sorted(self._trial_matrices)],
            "negative_transfers": [self._negative_transfers[key].to_state() for key in sorted(self._negative_transfers)],
        }

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, Any],
        *,
        experience: ExperienceLedger,
        causal: CausalProgramLedger | None = None,
        assurance: AssuranceControlPlane | None = None,
    ) -> "TransferMetaGovernor":
        schema = str(state.get("schema_version"))
        if schema not in {_SCHEMA_VERSION, _LEGACY_SCHEMA_VERSION}:
            raise ValueError("transfer/meta schema version mismatch")
        if str(state.get("component_id")) != COMPONENT_ID:
            raise ValueError("transfer/meta component id mismatch")
        version = str(state.get("component_version"))
        if schema == _SCHEMA_VERSION and version != COMPONENT_VERSION:
            raise ValueError("transfer/meta component version mismatch")
        if schema == _LEGACY_SCHEMA_VERSION and version not in {"0.0.1", COMPONENT_VERSION}:
            raise ValueError("transfer/meta component version mismatch")
        result = cls(experience=experience, causal=causal)
        portable_states = state.get("portables", ())
        source_states = state.get("sources", ())
        record_states = state.get("records", ())
        if not all(isinstance(rows, Sequence) and not isinstance(rows, (str, bytes, bytearray)) for rows in (portable_states, source_states, record_states)):
            raise TypeError("transfer/meta state collections must be sequences")

        serialized_portables: dict[str, PortableExperience] = {}
        for raw in portable_states:
            if not isinstance(raw, Mapping):
                raise TypeError("portable state rows must be mappings")
            portable = PortableExperience.from_state(raw)
            if portable.portable_id in serialized_portables:
                raise ValueError("duplicate portable experience identity in state")
            serialized_portables[portable.portable_id] = portable

        for raw in source_states:
            if not isinstance(raw, Mapping):
                raise TypeError("portable source state rows must be mappings")
            serialized_receipt = PortableExperienceSourceReceipt.from_state(raw)
            portable = serialized_portables.get(serialized_receipt.portable_id)
            if portable is None:
                raise ValueError("portable source receipt references missing portable experience")
            expected_portable, expected_receipt = result._derive_source(serialized_receipt.source_experience_id, serialized_receipt.attribution_id, causal_program_id=portable.causal_program_id)
            if expected_portable != portable or expected_receipt != serialized_receipt:
                raise ValueError("portable source authority does not match native source state")
            if expected_portable.portable_id in result._source_by_portable:
                raise ValueError("duplicate portable source authority in state")
            result._portables[expected_portable.portable_id] = expected_portable
            result._sources[expected_receipt.receipt_id] = expected_receipt
            result._source_by_portable[expected_portable.portable_id] = expected_receipt.receipt_id
        if set(serialized_portables) != set(result._portables):
            raise ValueError("portable experience is missing source authority")

        if schema == _SCHEMA_VERSION:
            for raw in state.get("intents", ()):
                if not isinstance(raw, Mapping):
                    raise TypeError("transfer intent state rows must be mappings")
                intent = TransferIntent.from_state(raw)
                if intent.transfer_intent_id in result._intents:
                    raise ValueError("duplicate transfer intent identity in state")
                result._intents[intent.transfer_intent_id] = intent
            for raw in state.get("trial_envelopes", ()):
                if not isinstance(raw, Mapping):
                    raise TypeError("trial envelope state rows must be mappings")
                envelope = TransferTrialEnvelope.from_state(raw)
                if envelope.envelope_id in result._trial_envelopes:
                    raise ValueError("duplicate trial envelope identity in state")
                result._trial_envelopes[envelope.envelope_id] = envelope
            for raw in state.get("trial_matrices", ()):
                if not isinstance(raw, Mapping):
                    raise TypeError("trial matrix state rows must be mappings")
                matrix = DestinationTrialMatrix.from_state(raw)
                if matrix.matrix_id in result._trial_matrices:
                    raise ValueError("duplicate trial matrix identity in state")
                result._trial_matrices[matrix.matrix_id] = matrix
            for raw in state.get("negative_transfers", ()):
                if not isinstance(raw, Mapping):
                    raise TypeError("negative transfer state rows must be mappings")
                negative = NegativeTransferRegimeRecord.from_state(raw)
                if negative.record_id in result._negative_transfers:
                    raise ValueError("duplicate negative transfer identity in state")
                result._negative_transfers[negative.record_id] = negative

        for raw in record_states:
            if not isinstance(raw, Mapping):
                raise TypeError("transfer record state rows must be mappings")
            record = TransferRecord.from_state(raw)
            transfer_id = record.adaptation.transfer_id
            if transfer_id in result._records:
                raise ValueError("duplicate transfer record identity in state")
            portable = result.portable(record.adaptation.portable_id)
            if record.adaptation.source_domain != portable.source_domain:
                raise ValueError("transfer adaptation source domain mismatch")
            expected_source = result._source_by_portable[portable.portable_id]
            if record.source_receipt_id != expected_source:
                raise ValueError("transfer record source receipt mismatch")
            if record.transfer_intent_id is not None:
                intent = result._intents.get(record.transfer_intent_id)
                envelope = result._trial_envelopes.get(str(record.trial_envelope_id))
                if intent is None or envelope is None:
                    raise ValueError("governed transfer state is missing intent or trial envelope")
                if envelope.transfer_intent_id != intent.transfer_intent_id or envelope.transfer_id != transfer_id:
                    raise ValueError("governed transfer intent/envelope binding mismatch")
                if record.trial_matrix_id is not None:
                    matrix = result._trial_matrices.get(record.trial_matrix_id)
                    if matrix is None or matrix.envelope_id != envelope.envelope_id or matrix.transfer_id != transfer_id:
                        raise ValueError("governed transfer trial matrix binding mismatch")
            result._records[transfer_id] = record

        for negative in result._negative_transfers.values():
            record = result._records.get(negative.transfer_id)
            if record is None or record.adaptation.target_domain != negative.target_domain:
                raise ValueError("negative transfer record does not bind a canonical transfer")
            if record.state is not TransferState.QUARANTINED:
                raise ValueError("negative transfer record requires quarantined transfer")

        for record in result._records.values():
            if record.assurance_receipt_id is not None:
                if assurance is None:
                    raise ValueError("accepted transfer restore requires native Assurance authority")
                if not isinstance(assurance, AssuranceControlPlane):
                    raise TypeError("assurance must be native AssuranceControlPlane")
                try:
                    receipt = assurance.promotion_receipt(record.assurance_receipt_id)
                except KeyError as exc:
                    raise ValueError("accepted transfer restore requires persisted assurance receipt") from exc
                result._validated_assurance(record, assurance=assurance, receipt=receipt, evidence_ids=record.acceptance_evidence_ids)

        if schema == _SCHEMA_VERSION:
            if result.to_state() != dict(state):
                raise ValueError("non-canonical transfer/meta state")
        return result


__all__ = (
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
    "PortableExperience",
    "PortableExperienceSourceReceipt",
    "TransferAdaptation",
    "TransferState",
    "TransferRecord",
    "TransferMetaGovernor",
)
