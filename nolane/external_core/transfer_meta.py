from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.assurance import AssuranceControlPlane, PromotionAssuranceReceipt
from nolane.external_core.causal import CausalProgramLedger
from nolane.memory.experience import (
    AttributionRecord,
    ExperienceLedger,
    ExperienceOutcome,
    ExperienceRecord,
)


COMPONENT_ID = "external.transfer_meta"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder R2.69 autonomous transfer/meta-learning lineage"
_SCHEMA_VERSION = "transfer-meta-v1"


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
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


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


def _clean_external_attribution(
    experience: ExperienceRecord,
    attribution: AttributionRecord,
) -> None:
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
    for raw in state.get("programs", ()):  # canonical ledger already validates evidence on registration
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
        causal_program_id = (
            None if self.causal_program_id is None else _nonempty(self.causal_program_id, "causal_program_id")
        )
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
    def create(
        cls,
        *,
        source_domain: str,
        learning_layer: str,
        lesson: str,
        causal_program_id: str | None = None,
    ) -> "PortableExperience":
        payload = {
            "source_domain": _nonempty(source_domain, "source_domain"),
            "learning_layer": _nonempty(learning_layer, "learning_layer"),
            "lesson": _nonempty(lesson, "lesson"),
            "causal_program_id": (
                None if causal_program_id is None else _nonempty(causal_program_id, "causal_program_id")
            ),
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
        object.__setattr__(self, "portable_id", values["portable_id"])
        object.__setattr__(self, "source_experience_id", values["source_experience_id"])
        object.__setattr__(self, "attribution_id", values["attribution_id"])
        object.__setattr__(self, "source_experience_digest", values["source_experience_digest"])
        object.__setattr__(self, "source_attribution_digest", values["source_attribution_digest"])
        object.__setattr__(self, "source_evidence_digest", values["source_evidence_digest"])
        object.__setattr__(self, "causal_row_digest", values["causal_row_digest"])
        object.__setattr__(self, "source_authority_digest", expected_authority)
        object.__setattr__(self, "receipt_id", expected_receipt)

    @classmethod
    def create(
        cls,
        *,
        portable_id: str,
        source_experience_id: str,
        attribution_id: str,
        source_experience_digest: str,
        source_attribution_digest: str,
        source_evidence_digest: str,
        causal_row_digest: str | None,
    ) -> "PortableExperienceSourceReceipt":
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
        return cls(
            **values,
            source_authority_digest=authority,
            receipt_id=f"transfer-source-receipt:{canonical_digest(receipt_payload)}",
        )

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
        semantic = {
            "portable_id": portable_id,
            "source_domain": source_domain,
            "target_domain": target_domain,
            "metadata": metadata,
        }
        expected = f"transfer:{canonical_digest(semantic)}"
        if str(self.transfer_id) != expected:
            raise ValueError("transfer adaptation identity mismatch")
        object.__setattr__(self, "portable_id", portable_id)
        object.__setattr__(self, "source_domain", source_domain)
        object.__setattr__(self, "target_domain", target_domain)
        object.__setattr__(self, "metadata_json", _canonical_json(metadata))
        object.__setattr__(self, "transfer_id", expected)

    @classmethod
    def create(
        cls,
        portable: PortableExperience,
        *,
        target_domain: str,
        metadata: Mapping[str, Any],
    ) -> "TransferAdaptation":
        if not isinstance(portable, PortableExperience):
            raise TypeError("portable must be PortableExperience")
        normalized = _normalize_json(metadata)
        if not isinstance(normalized, dict):
            raise TypeError("transfer metadata must be a mapping")
        source_domain = portable.source_domain
        target = _nonempty(target_domain, "target_domain")
        semantic = {
            "portable_id": portable.portable_id,
            "source_domain": source_domain,
            "target_domain": target,
            "metadata": normalized,
        }
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
        return {
            "transfer_id": self.transfer_id,
            "portable_id": self.portable_id,
            "source_domain": self.source_domain,
            "target_domain": self.target_domain,
            "metadata": self.metadata(),
        }

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
        if state is TransferState.PROPOSED:
            if evidence or assurance_id or reason:
                raise ValueError("proposed transfer cannot carry acceptance or quarantine authority")
        elif state is TransferState.ACCEPTED:
            if not evidence or not assurance_id:
                raise ValueError("accepted transfer requires evidence and assurance receipt")
            if reason:
                raise ValueError("accepted transfer cannot carry quarantine reason")
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

    def to_state(self) -> dict[str, Any]:
        return {
            "adaptation": self.adaptation.to_state(),
            "source_receipt_id": self.source_receipt_id,
            "state": self.state.value,
            "acceptance_evidence_ids": list(self.acceptance_evidence_ids),
            "assurance_receipt_id": self.assurance_receipt_id,
            "quarantine_reason": self.quarantine_reason,
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
        )
        if row.to_state() != dict(state):
            raise ValueError("non-canonical transfer record state")
        return row


class TransferMetaGovernor:
    """Verified portable-experience transfer and reuse authority.

    Learning/search policy is intentionally outside this boundary. The governor
    only derives portable source authority from native Experience/Causal state,
    creates deterministic domain adaptations, gates reuse through persisted
    native Assurance receipts, and revokes visibility after negative transfer.
    """

    def __init__(
        self,
        *,
        experience: ExperienceLedger,
        causal: CausalProgramLedger | None = None,
    ) -> None:
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

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    def _derive_source(
        self,
        experience_id: str,
        attribution_id: str,
        *,
        causal_program_id: str | None,
    ) -> tuple[PortableExperience, PortableExperienceSourceReceipt]:
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
        portable = PortableExperience.create(
            source_domain=source.domain,
            learning_layer=attribution.learning_layer.value,
            lesson=attribution.lesson,
            causal_program_id=causal_id,
        )
        source_experience_digest = canonical_digest(source.to_state())
        source_attribution_digest = canonical_digest(attribution.to_state())
        source_evidence_digest = canonical_digest(attribution.evidence.to_state())
        receipt = PortableExperienceSourceReceipt.create(
            portable_id=portable.portable_id,
            source_experience_id=source.experience_id,
            attribution_id=attribution.attribution_id,
            source_experience_digest=source_experience_digest,
            source_attribution_digest=source_attribution_digest,
            source_evidence_digest=source_evidence_digest,
            causal_row_digest=causal_digest,
        )
        return portable, receipt

    def compile_portable(
        self,
        experience_id: str,
        attribution_id: str,
        *,
        causal_program_id: str | None = None,
    ) -> tuple[PortableExperience, PortableExperienceSourceReceipt]:
        portable, receipt = self._derive_source(
            experience_id,
            attribution_id,
            causal_program_id=causal_program_id,
        )
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
        target_domain: str,
        metadata: Mapping[str, Any],
    ) -> TransferRecord:
        portable = self.portable(portable_id)
        adaptation = TransferAdaptation.create(
            portable,
            target_domain=target_domain,
            metadata=dict(metadata),
        )
        if adaptation.transfer_id in self._records:
            raise ValueError("duplicate transfer adaptation identity")
        source_receipt_id = self._source_by_portable[portable.portable_id]
        row = TransferRecord(
            adaptation=adaptation,
            source_receipt_id=source_receipt_id,
            state=TransferState.PROPOSED,
        )
        self._records[adaptation.transfer_id] = row
        return row

    def record(self, transfer_id: str) -> TransferRecord:
        try:
            return self._records[str(transfer_id)]
        except KeyError:
            raise KeyError(str(transfer_id)) from None

    def _validated_assurance(
        self,
        record: TransferRecord,
        *,
        assurance: AssuranceControlPlane,
        receipt: PromotionAssuranceReceipt,
        evidence_ids: tuple[str, ...],
    ) -> PromotionAssuranceReceipt:
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
    ) -> TransferRecord:
        record = self.record(transfer_id)
        if record.state is TransferState.QUARANTINED:
            raise ValueError("quarantined transfer cannot be accepted")
        if record.state is not TransferState.PROPOSED:
            raise ValueError("only proposed transfer can be accepted")
        validated = self._validated_assurance(
            record,
            assurance=assurance,
            receipt=receipt,
            evidence_ids=evidence_ids,
        )
        updated = replace(
            record,
            state=TransferState.ACCEPTED,
            acceptance_evidence_ids=validated.evidence_ids,
            assurance_receipt_id=validated.receipt_id,
        )
        self._records[record.adaptation.transfer_id] = updated
        return updated

    def quarantine(self, transfer_id: str, *, reason: str) -> TransferRecord:
        record = self.record(transfer_id)
        if record.state is TransferState.QUARANTINED:
            raise ValueError("transfer is already quarantined")
        updated = replace(
            record,
            state=TransferState.QUARANTINED,
            quarantine_reason=_nonempty(reason, "quarantine reason"),
        )
        self._records[record.adaptation.transfer_id] = updated
        return updated

    def report_negative_transfer(self, transfer_id: str, *, reason: str) -> TransferRecord:
        record = self.record(transfer_id)
        if record.state is not TransferState.ACCEPTED:
            raise ValueError("negative-transfer revocation requires accepted transfer")
        return self.quarantine(transfer_id, reason=reason)

    def reusable_ids(self, *, target_domain: str | None = None) -> tuple[str, ...]:
        domain = None if target_domain is None else _nonempty(target_domain, "target_domain")
        return tuple(
            key
            for key in sorted(self._records)
            if self._records[key].state is TransferState.ACCEPTED
            and (domain is None or self._records[key].adaptation.target_domain == domain)
        )

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
        if str(state.get("schema_version")) != _SCHEMA_VERSION:
            raise ValueError("transfer/meta schema version mismatch")
        if str(state.get("component_id")) != COMPONENT_ID:
            raise ValueError("transfer/meta component id mismatch")
        if str(state.get("component_version")) != COMPONENT_VERSION:
            raise ValueError("transfer/meta component version mismatch")
        result = cls(experience=experience, causal=causal)
        portable_states = state.get("portables", ())
        source_states = state.get("sources", ())
        record_states = state.get("records", ())
        if not all(
            isinstance(rows, Sequence) and not isinstance(rows, (str, bytes, bytearray))
            for rows in (portable_states, source_states, record_states)
        ):
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
            expected_portable, expected_receipt = result._derive_source(
                serialized_receipt.source_experience_id,
                serialized_receipt.attribution_id,
                causal_program_id=portable.causal_program_id,
            )
            if expected_portable != portable or expected_receipt != serialized_receipt:
                raise ValueError("portable source authority does not match native source state")
            if expected_portable.portable_id in result._source_by_portable:
                raise ValueError("duplicate portable source authority in state")
            result._portables[expected_portable.portable_id] = expected_portable
            result._sources[expected_receipt.receipt_id] = expected_receipt
            result._source_by_portable[expected_portable.portable_id] = expected_receipt.receipt_id

        if set(serialized_portables) != set(result._portables):
            raise ValueError("portable experience is missing source authority")

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
            result._records[transfer_id] = record

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
                result._validated_assurance(
                    record,
                    assurance=assurance,
                    receipt=receipt,
                    evidence_ids=record.acceptance_evidence_ids,
                )

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
