from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding_claims import CodeClaimLedger
from nolane.external_core.software_engineering import EngineeringEvidenceKind, EngineeringEvidenceLedger


COMPONENT_ID = "external.coding.patches"
COMPONENT_VERSION = "0.0.2"
MIGRATED_FROM = "cogcoder.organization.coding_patches"


class CodingPatchStatus(str, Enum):
    DRAFT = "draft"
    EVIDENCE_READY = "evidence_ready"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


def _refs(values: tuple[Any, ...]) -> tuple[str, ...]:
    return tuple(sorted({_text(value, field="reference") for value in values}))


def _path(value: str) -> str:
    text = str(value).replace("\\", "/").strip()
    if not text:
        raise ValueError("patch file path must be non-empty")
    normalized = str(PurePosixPath(text))
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized.startswith("/") or normalized == ".." or normalized.startswith("../"):
        raise ValueError("patch file path must be repository-relative")
    return normalized


def _symbol(value: str) -> str:
    return _text(value, field="patch symbol")


@dataclass(frozen=True, slots=True)
class ToolInvocationReceipt:
    receipt_id: str
    agent_id: str
    task_id: str
    tool_id: str
    input_artifact_refs: tuple[str, ...]
    output_artifact_refs: tuple[str, ...]
    success: bool
    evidence_refs: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "tool_id": self.tool_id,
            "input_artifact_refs": list(self.input_artifact_refs),
            "output_artifact_refs": list(self.output_artifact_refs),
            "success": self.success,
            "evidence_refs": list(self.evidence_refs),
        }

    def to_state(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ToolInvocationReceipt":
        row = cls(
            receipt_id=str(state["receipt_id"]),
            agent_id=str(state["agent_id"]),
            task_id=str(state["task_id"]),
            tool_id=str(state["tool_id"]),
            input_artifact_refs=tuple(str(x) for x in state.get("input_artifact_refs", ())),
            output_artifact_refs=tuple(str(x) for x in state.get("output_artifact_refs", ())),
            success=bool(state["success"]),
            evidence_refs=tuple(str(x) for x in state.get("evidence_refs", ())),
            digest=str(state["digest"]),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != "tool-" + expected[:20]:
            raise ValueError("tool invocation receipt digest/id mismatch")
        return row


@dataclass(frozen=True, slots=True)
class PatchProvenanceEnvelope:
    provenance_id: str
    producer_agent_id: str
    task_id: str
    work_id: str
    base_plan_version: int
    base_architecture_version: int
    touched_files: tuple[str, ...]
    touched_symbols: tuple[str, ...]
    patch_artifact_id: str
    patch_artifact_digest: str
    base_source_revision: str
    operation_ref: str
    compile_evidence_refs: tuple[str, ...]
    test_evidence_refs: tuple[str, ...]
    static_evidence_refs: tuple[str, ...]
    known_risks: tuple[str, ...]
    plan_gap_event_refs: tuple[str, ...]
    architecture_concern_event_refs: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "producer_agent_id": self.producer_agent_id,
            "task_id": self.task_id,
            "work_id": self.work_id,
            "base_plan_version": self.base_plan_version,
            "base_architecture_version": self.base_architecture_version,
            "touched_files": list(self.touched_files),
            "touched_symbols": list(self.touched_symbols),
            "patch_artifact_id": self.patch_artifact_id,
            "patch_artifact_digest": self.patch_artifact_digest,
            "base_source_revision": self.base_source_revision,
            "operation_ref": self.operation_ref,
            "compile_evidence_refs": list(self.compile_evidence_refs),
            "test_evidence_refs": list(self.test_evidence_refs),
            "static_evidence_refs": list(self.static_evidence_refs),
            "known_risks": list(self.known_risks),
            "plan_gap_event_refs": list(self.plan_gap_event_refs),
            "architecture_concern_event_refs": list(self.architecture_concern_event_refs),
        }

    def to_state(self) -> dict[str, Any]:
        return {"provenance_id": self.provenance_id, **self.payload(), "digest": self.digest}

    @classmethod
    def build(
        cls,
        *,
        producer_agent_id: str,
        task_id: str,
        work_id: str,
        base_plan_version: int,
        base_architecture_version: int,
        touched_files: tuple[str, ...],
        touched_symbols: tuple[str, ...],
        patch_artifact_id: str,
        patch_artifact_digest: str,
        base_source_revision: str,
        operation_ref: str,
        compile_evidence_refs: tuple[str, ...],
        test_evidence_refs: tuple[str, ...],
        static_evidence_refs: tuple[str, ...],
        known_risks: tuple[str, ...],
        plan_gap_event_refs: tuple[str, ...],
        architecture_concern_event_refs: tuple[str, ...],
    ) -> "PatchProvenanceEnvelope":
        plan_version = int(base_plan_version)
        architecture_version = int(base_architecture_version)
        if plan_version < 0 or architecture_version < 0:
            raise ValueError("patch base versions must be non-negative")
        payload = {
            "producer_agent_id": _text(producer_agent_id, field="producer agent"),
            "task_id": _text(task_id, field="task id"),
            "work_id": _text(work_id, field="work id"),
            "base_plan_version": plan_version,
            "base_architecture_version": architecture_version,
            "touched_files": list(touched_files),
            "touched_symbols": list(touched_symbols),
            "patch_artifact_id": _text(patch_artifact_id, field="patch artifact id"),
            "patch_artifact_digest": _text(patch_artifact_digest, field="patch artifact digest"),
            "base_source_revision": _text(base_source_revision, field="base source revision"),
            "operation_ref": _text(operation_ref, field="operation ref"),
            "compile_evidence_refs": list(compile_evidence_refs),
            "test_evidence_refs": list(test_evidence_refs),
            "static_evidence_refs": list(static_evidence_refs),
            "known_risks": list(known_risks),
            "plan_gap_event_refs": list(plan_gap_event_refs),
            "architecture_concern_event_refs": list(architecture_concern_event_refs),
        }
        digest = canonical_digest(payload)
        return cls(
            provenance_id="patch-prov-" + digest[:20],
            producer_agent_id=payload["producer_agent_id"],
            task_id=payload["task_id"],
            work_id=payload["work_id"],
            base_plan_version=plan_version,
            base_architecture_version=architecture_version,
            touched_files=tuple(payload["touched_files"]),
            touched_symbols=tuple(payload["touched_symbols"]),
            patch_artifact_id=payload["patch_artifact_id"],
            patch_artifact_digest=payload["patch_artifact_digest"],
            base_source_revision=payload["base_source_revision"],
            operation_ref=payload["operation_ref"],
            compile_evidence_refs=tuple(payload["compile_evidence_refs"]),
            test_evidence_refs=tuple(payload["test_evidence_refs"]),
            static_evidence_refs=tuple(payload["static_evidence_refs"]),
            known_risks=tuple(payload["known_risks"]),
            plan_gap_event_refs=tuple(payload["plan_gap_event_refs"]),
            architecture_concern_event_refs=tuple(payload["architecture_concern_event_refs"]),
            digest=digest,
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "PatchProvenanceEnvelope":
        row = cls.build(
            producer_agent_id=state["producer_agent_id"],
            task_id=state["task_id"],
            work_id=state["work_id"],
            base_plan_version=state["base_plan_version"],
            base_architecture_version=state["base_architecture_version"],
            touched_files=tuple(sorted({_path(x) for x in state.get("touched_files", ())})),
            touched_symbols=tuple(sorted({_symbol(x) for x in state.get("touched_symbols", ())})),
            patch_artifact_id=state["patch_artifact_id"],
            patch_artifact_digest=state["patch_artifact_digest"],
            base_source_revision=state["base_source_revision"],
            operation_ref=state["operation_ref"],
            compile_evidence_refs=_refs(tuple(state.get("compile_evidence_refs", ()))) if state.get("compile_evidence_refs") else (),
            test_evidence_refs=_refs(tuple(state.get("test_evidence_refs", ()))) if state.get("test_evidence_refs") else (),
            static_evidence_refs=_refs(tuple(state.get("static_evidence_refs", ()))) if state.get("static_evidence_refs") else (),
            known_risks=_refs(tuple(state.get("known_risks", ()))) if state.get("known_risks") else (),
            plan_gap_event_refs=_refs(tuple(state.get("plan_gap_event_refs", ()))) if state.get("plan_gap_event_refs") else (),
            architecture_concern_event_refs=_refs(tuple(state.get("architecture_concern_event_refs", ()))) if state.get("architecture_concern_event_refs") else (),
        )
        if row.digest != str(state["digest"]) or row.provenance_id != str(state["provenance_id"]):
            raise ValueError("patch provenance digest/id mismatch")
        return row


@dataclass(frozen=True, slots=True)
class PatchTransitionReceipt:
    receipt_id: str
    patch_id: str
    provenance_id: str
    provenance_digest: str
    sequence: int
    predecessor_receipt_id: str
    predecessor_digest: str
    from_status: str
    to_status: CodingPatchStatus
    evidence_attestation_ids: tuple[str, ...]
    evidence_attestation_digests: tuple[str, ...]
    authority: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "patch_id": self.patch_id,
            "provenance_id": self.provenance_id,
            "provenance_digest": self.provenance_digest,
            "sequence": self.sequence,
            "predecessor_receipt_id": self.predecessor_receipt_id,
            "predecessor_digest": self.predecessor_digest,
            "from_status": self.from_status,
            "to_status": self.to_status.value,
            "evidence_attestation_ids": list(self.evidence_attestation_ids),
            "evidence_attestation_digests": list(self.evidence_attestation_digests),
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self.payload(), "digest": self.digest}

    @classmethod
    def build(
        cls,
        *,
        patch_id: str,
        provenance: PatchProvenanceEnvelope,
        sequence: int,
        predecessor: "PatchTransitionReceipt | None",
        from_status: str,
        to_status: CodingPatchStatus,
        evidence_attestation_ids: tuple[str, ...] = (),
        evidence_attestation_digests: tuple[str, ...] = (),
    ) -> "PatchTransitionReceipt":
        ids = tuple(evidence_attestation_ids)
        digests = tuple(evidence_attestation_digests)
        if len(ids) != len(digests):
            raise ValueError("transition evidence ids/digests must align")
        if tuple(sorted(set(ids))) != ids:
            raise ValueError("transition evidence ids must be canonical and unique")
        desired = CodingPatchStatus(to_status)
        if desired is CodingPatchStatus.VERIFIED and not ids:
            raise ValueError("verified transition requires canonical evidence")
        payload = {
            "patch_id": _text(patch_id, field="patch id"),
            "provenance_id": provenance.provenance_id,
            "provenance_digest": provenance.digest,
            "sequence": int(sequence),
            "predecessor_receipt_id": predecessor.receipt_id if predecessor else "",
            "predecessor_digest": predecessor.digest if predecessor else "",
            "from_status": str(from_status),
            "to_status": desired.value,
            "evidence_attestation_ids": list(ids),
            "evidence_attestation_digests": list(digests),
            "authority": "patch_transition_only",
        }
        if payload["sequence"] < 1:
            raise ValueError("transition sequence must be positive")
        digest = canonical_digest(payload)
        return cls(
            receipt_id="patch-transition-" + digest[:20],
            patch_id=payload["patch_id"],
            provenance_id=payload["provenance_id"],
            provenance_digest=payload["provenance_digest"],
            sequence=payload["sequence"],
            predecessor_receipt_id=payload["predecessor_receipt_id"],
            predecessor_digest=payload["predecessor_digest"],
            from_status=payload["from_status"],
            to_status=desired,
            evidence_attestation_ids=ids,
            evidence_attestation_digests=digests,
            authority="patch_transition_only",
            digest=digest,
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "PatchTransitionReceipt":
        row = cls(
            receipt_id=str(state["receipt_id"]),
            patch_id=str(state["patch_id"]),
            provenance_id=str(state["provenance_id"]),
            provenance_digest=str(state["provenance_digest"]),
            sequence=int(state["sequence"]),
            predecessor_receipt_id=str(state.get("predecessor_receipt_id", "")),
            predecessor_digest=str(state.get("predecessor_digest", "")),
            from_status=str(state.get("from_status", "")),
            to_status=CodingPatchStatus(str(state["to_status"])),
            evidence_attestation_ids=tuple(str(x) for x in state.get("evidence_attestation_ids", ())),
            evidence_attestation_digests=tuple(str(x) for x in state.get("evidence_attestation_digests", ())),
            authority=str(state["authority"]),
            digest=str(state["digest"]),
        )
        if row.authority != "patch_transition_only":
            raise ValueError("patch transition authority mismatch")
        if len(row.evidence_attestation_ids) != len(row.evidence_attestation_digests):
            raise ValueError("transition evidence ids/digests must align")
        if tuple(sorted(set(row.evidence_attestation_ids))) != row.evidence_attestation_ids:
            raise ValueError("transition evidence ids must be canonical and unique")
        if row.to_status is CodingPatchStatus.VERIFIED and not row.evidence_attestation_ids:
            raise ValueError("verified transition requires canonical evidence")
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != "patch-transition-" + expected[:20]:
            raise ValueError("patch transition digest/id mismatch")
        return row


@dataclass(frozen=True, slots=True)
class CodingPatchCandidate:
    # v0.0.1 positional ABI is intentionally preserved through `status`.
    patch_id: str
    producer_agent_id: str
    task_id: str
    work_id: str
    base_plan_version: int
    base_architecture_version: int
    touched_files: tuple[str, ...]
    touched_symbols: tuple[str, ...]
    patch_artifact_id: str
    compile_evidence_refs: tuple[str, ...] = ()
    test_evidence_refs: tuple[str, ...] = ()
    static_evidence_refs: tuple[str, ...] = ()
    known_risks: tuple[str, ...] = ()
    plan_gap_event_refs: tuple[str, ...] = ()
    architecture_concern_event_refs: tuple[str, ...] = ()
    status: CodingPatchStatus = CodingPatchStatus.DRAFT
    patch_artifact_digest: str = ""
    base_source_revision: str = ""
    operation_ref: str = ""
    provenance_id: str = ""

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (self.patch_id, self.producer_agent_id, self.task_id, self.work_id, self.patch_artifact_id)):
            raise ValueError("patch identity/producer/task/work/artifact must be explicit")
        if self.base_plan_version < 0 or self.base_architecture_version < 0:
            raise ValueError("patch base versions must be non-negative")
        if not self.touched_files and not self.touched_symbols:
            raise ValueError("patch must declare touched source scope")
        provenance_fields = (self.patch_artifact_digest, self.base_source_revision, self.operation_ref, self.provenance_id)
        if any(provenance_fields) and not all(provenance_fields):
            raise ValueError("patch provenance fields must be complete")

    def to_state(self) -> dict[str, Any]:
        return {
            "patch_id": self.patch_id,
            "producer_agent_id": self.producer_agent_id,
            "task_id": self.task_id,
            "work_id": self.work_id,
            "base_plan_version": self.base_plan_version,
            "base_architecture_version": self.base_architecture_version,
            "touched_files": list(self.touched_files),
            "touched_symbols": list(self.touched_symbols),
            "patch_artifact_id": self.patch_artifact_id,
            "compile_evidence_refs": list(self.compile_evidence_refs),
            "test_evidence_refs": list(self.test_evidence_refs),
            "static_evidence_refs": list(self.static_evidence_refs),
            "known_risks": list(self.known_risks),
            "plan_gap_event_refs": list(self.plan_gap_event_refs),
            "architecture_concern_event_refs": list(self.architecture_concern_event_refs),
            "status": self.status.value,
            "patch_artifact_digest": self.patch_artifact_digest,
            "base_source_revision": self.base_source_revision,
            "operation_ref": self.operation_ref,
            "provenance_id": self.provenance_id,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CodingPatchCandidate":
        return cls(
            patch_id=str(state["patch_id"]),
            producer_agent_id=str(state["producer_agent_id"]),
            task_id=str(state["task_id"]),
            work_id=str(state["work_id"]),
            base_plan_version=int(state["base_plan_version"]),
            base_architecture_version=int(state["base_architecture_version"]),
            touched_files=tuple(sorted({_path(x) for x in state.get("touched_files", ())})),
            touched_symbols=tuple(sorted({_symbol(x) for x in state.get("touched_symbols", ())})),
            patch_artifact_id=str(state["patch_artifact_id"]),
            compile_evidence_refs=_refs(tuple(state.get("compile_evidence_refs", ()))) if state.get("compile_evidence_refs") else (),
            test_evidence_refs=_refs(tuple(state.get("test_evidence_refs", ()))) if state.get("test_evidence_refs") else (),
            static_evidence_refs=_refs(tuple(state.get("static_evidence_refs", ()))) if state.get("static_evidence_refs") else (),
            known_risks=_refs(tuple(state.get("known_risks", ()))) if state.get("known_risks") else (),
            plan_gap_event_refs=_refs(tuple(state.get("plan_gap_event_refs", ()))) if state.get("plan_gap_event_refs") else (),
            architecture_concern_event_refs=_refs(tuple(state.get("architecture_concern_event_refs", ()))) if state.get("architecture_concern_event_refs") else (),
            status=CodingPatchStatus(str(state.get("status", CodingPatchStatus.DRAFT.value))),
            patch_artifact_digest=str(state.get("patch_artifact_digest", "")),
            base_source_revision=str(state.get("base_source_revision", "")),
            operation_ref=str(state.get("operation_ref", "")),
            provenance_id=str(state.get("provenance_id", "")),
        )


class CodingPatchLedger:
    """Coding patch audit ledger with v0.0.2 provenance-bound transition authority.

    `VERIFIED` is a historical engineering transition, never release/deploy authority.
    Current verification is recomputed from canonical live evidence; legacy v0.0.1
    rows remain readable but cannot manufacture current verification authority.
    """

    def __init__(self, claims: CodeClaimLedger, engineering_evidence: EngineeringEvidenceLedger | None = None) -> None:
        self.claims = claims
        self.engineering_evidence = engineering_evidence
        self._patches: dict[str, CodingPatchCandidate] = {}
        self._tool_receipts: dict[str, ToolInvocationReceipt] = {}
        self._provenance: dict[str, PatchProvenanceEnvelope] = {}
        self._operation_index: dict[str, str] = {}
        self._transitions: dict[str, list[PatchTransitionReceipt]] = {}
        self._patch_counter = 0

    def patches(self) -> tuple[CodingPatchCandidate, ...]:
        return tuple(self._patches[key] for key in sorted(self._patches))

    def get_patch(self, patch_id: str) -> CodingPatchCandidate:
        try:
            return self._patches[str(patch_id)]
        except KeyError as exc:
            raise KeyError(f"unknown coding patch: {patch_id}") from exc

    def get_provenance(self, provenance_id: str) -> PatchProvenanceEnvelope:
        try:
            return self._provenance[str(provenance_id)]
        except KeyError as exc:
            raise KeyError(f"unknown patch provenance: {provenance_id}") from exc

    def transitions(self, patch_id: str) -> tuple[PatchTransitionReceipt, ...]:
        self.get_patch(patch_id)
        return tuple(self._transitions.get(str(patch_id), ()))

    def latest_transition(self, patch_id: str) -> PatchTransitionReceipt:
        rows = self.transitions(patch_id)
        if not rows:
            raise KeyError(f"patch has no transition receipt: {patch_id}")
        return rows[-1]

    @staticmethod
    def _normalized_registration(
        *,
        touched_files: tuple[str, ...],
        touched_symbols: tuple[str, ...],
        compile_evidence_refs: tuple[str, ...],
        test_evidence_refs: tuple[str, ...],
        static_evidence_refs: tuple[str, ...],
        known_risks: tuple[str, ...],
        plan_gap_event_refs: tuple[str, ...],
        architecture_concern_event_refs: tuple[str, ...],
    ) -> tuple[tuple[str, ...], ...]:
        return (
            tuple(sorted({_path(x) for x in touched_files})),
            tuple(sorted({_symbol(x) for x in touched_symbols})),
            _refs(tuple(compile_evidence_refs)) if compile_evidence_refs else (),
            _refs(tuple(test_evidence_refs)) if test_evidence_refs else (),
            _refs(tuple(static_evidence_refs)) if static_evidence_refs else (),
            _refs(tuple(known_risks)) if known_risks else (),
            _refs(tuple(plan_gap_event_refs)) if plan_gap_event_refs else (),
            _refs(tuple(architecture_concern_event_refs)) if architecture_concern_event_refs else (),
        )

    def register_patch(
        self,
        *,
        producer_agent_id: str,
        task_id: str,
        work_id: str,
        base_plan_version: int,
        base_architecture_version: int,
        touched_files: tuple[str, ...] = (),
        touched_symbols: tuple[str, ...] = (),
        patch_artifact_id: str,
        patch_artifact_digest: str = "",
        base_source_revision: str = "",
        operation_ref: str = "",
        compile_evidence_refs: tuple[str, ...] = (),
        test_evidence_refs: tuple[str, ...] = (),
        static_evidence_refs: tuple[str, ...] = (),
        known_risks: tuple[str, ...] = (),
        plan_gap_event_refs: tuple[str, ...] = (),
        architecture_concern_event_refs: tuple[str, ...] = (),
    ) -> CodingPatchCandidate:
        (
            files,
            symbols,
            compile_refs,
            test_refs,
            static_refs,
            risks,
            plan_gaps,
            architecture_concerns,
        ) = self._normalized_registration(
            touched_files=touched_files,
            touched_symbols=touched_symbols,
            compile_evidence_refs=compile_evidence_refs,
            test_evidence_refs=test_evidence_refs,
            static_evidence_refs=static_evidence_refs,
            known_risks=known_risks,
            plan_gap_event_refs=plan_gap_event_refs,
            architecture_concern_event_refs=architecture_concern_event_refs,
        )
        status = CodingPatchStatus.EVIDENCE_READY if compile_refs and test_refs else CodingPatchStatus.DRAFT
        provenance_inputs = (
            str(patch_artifact_digest).strip(),
            str(base_source_revision).strip(),
            str(operation_ref).strip(),
        )
        if any(provenance_inputs) and not all(provenance_inputs):
            raise ValueError("artifact digest, base source revision and operation ref must be supplied together")

        provenance: PatchProvenanceEnvelope | None = None
        if all(provenance_inputs):
            provenance = PatchProvenanceEnvelope.build(
                producer_agent_id=producer_agent_id,
                task_id=task_id,
                work_id=work_id,
                base_plan_version=base_plan_version,
                base_architecture_version=base_architecture_version,
                touched_files=files,
                touched_symbols=symbols,
                patch_artifact_id=patch_artifact_id,
                patch_artifact_digest=patch_artifact_digest,
                base_source_revision=base_source_revision,
                operation_ref=operation_ref,
                compile_evidence_refs=compile_refs,
                test_evidence_refs=test_refs,
                static_evidence_refs=static_refs,
                known_risks=risks,
                plan_gap_event_refs=plan_gaps,
                architecture_concern_event_refs=architecture_concerns,
            )
            existing_provenance_id = self._operation_index.get(provenance.operation_ref)
            if existing_provenance_id is not None:
                existing = self.get_provenance(existing_provenance_id)
                if existing != provenance:
                    raise ValueError("operation ref cannot be rebound to different patch provenance")
                matches = [patch for patch in self._patches.values() if patch.provenance_id == existing.provenance_id]
                if len(matches) != 1:
                    raise ValueError("operation ref must resolve to exactly one canonical patch")
                return matches[0]

        self._patch_counter += 1
        row = CodingPatchCandidate(
            patch_id=f"patch-{self._patch_counter:08d}",
            producer_agent_id=str(producer_agent_id),
            task_id=str(task_id),
            work_id=str(work_id),
            base_plan_version=int(base_plan_version),
            base_architecture_version=int(base_architecture_version),
            touched_files=files,
            touched_symbols=symbols,
            patch_artifact_id=str(patch_artifact_id),
            compile_evidence_refs=compile_refs,
            test_evidence_refs=test_refs,
            static_evidence_refs=static_refs,
            known_risks=risks,
            plan_gap_event_refs=plan_gaps,
            architecture_concern_event_refs=architecture_concerns,
            status=status,
            patch_artifact_digest=provenance.patch_artifact_digest if provenance else "",
            base_source_revision=provenance.base_source_revision if provenance else "",
            operation_ref=provenance.operation_ref if provenance else "",
            provenance_id=provenance.provenance_id if provenance else "",
        )
        self._patches[row.patch_id] = row
        if provenance is not None:
            self._provenance[provenance.provenance_id] = provenance
            self._operation_index[provenance.operation_ref] = provenance.provenance_id
            self._record_transition(row.patch_id, status, genesis=True)
        return row

    def claim_coverage(self, patch_id: str) -> bool:
        row = self.get_patch(patch_id)
        return self.claims.covers(
            agent_id=row.producer_agent_id,
            task_id=row.task_id,
            file_paths=row.touched_files,
            symbol_ids=row.touched_symbols,
        )

    def _record_transition(
        self,
        patch_id: str,
        to_status: CodingPatchStatus,
        *,
        genesis: bool = False,
        evidence_attestation_ids: tuple[str, ...] = (),
        evidence_attestation_digests: tuple[str, ...] = (),
    ) -> PatchTransitionReceipt:
        patch = self.get_patch(patch_id)
        if not patch.provenance_id:
            raise PermissionError("content-addressed transitions require patch provenance")
        provenance = self.get_provenance(patch.provenance_id)
        history = self._transitions.setdefault(patch.patch_id, [])
        predecessor = history[-1] if history else None
        if genesis != (predecessor is None):
            raise ValueError("patch transition genesis/frontier mismatch")
        receipt = PatchTransitionReceipt.build(
            patch_id=patch.patch_id,
            provenance=provenance,
            sequence=len(history) + 1,
            predecessor=predecessor,
            from_status="" if genesis else patch.status.value,
            to_status=to_status,
            evidence_attestation_ids=evidence_attestation_ids,
            evidence_attestation_digests=evidence_attestation_digests,
        )
        history.append(receipt)
        return receipt

    def set_status(self, patch_id: str, status: CodingPatchStatus) -> CodingPatchCandidate:
        desired = CodingPatchStatus(status)
        if desired is CodingPatchStatus.VERIFIED:
            raise PermissionError("verified status requires canonical verification evidence and verify_patch()")
        old = self.get_patch(patch_id)
        if old.status in {CodingPatchStatus.REJECTED, CodingPatchStatus.SUPERSEDED}:
            if desired is old.status:
                return old
            raise PermissionError("terminal patch status cannot transition")
        if old.provenance_id:
            self._record_transition(old.patch_id, desired)
        row = replace(old, status=desired)
        self._patches[row.patch_id] = row
        return row

    def _verification_evidence(self, patch: CodingPatchCandidate, attestation_ids: tuple[str, ...]):
        if self.engineering_evidence is None:
            raise PermissionError("verified transition requires canonical engineering evidence ledger")
        if not patch.provenance_id:
            raise PermissionError("verified transition requires content-bound patch provenance")
        provenance = self.get_provenance(patch.provenance_id)
        ids = _refs(tuple(attestation_ids)) if attestation_ids else ()
        if not ids:
            raise PermissionError("verified transition requires compile and test evidence")
        rows = []
        for identity in ids:
            row = self.engineering_evidence.get(identity)
            if not self.engineering_evidence.is_valid(
                identity,
                subject_ref=provenance.patch_artifact_id,
                subject_digest=provenance.patch_artifact_digest,
                source_revision=provenance.base_source_revision,
            ):
                raise PermissionError("verification evidence is not live for exact patch provenance")
            rows.append(row)
        kinds = {row.kind for row in rows}
        if EngineeringEvidenceKind.COMPILE not in kinds or EngineeringEvidenceKind.TEST not in kinds:
            raise PermissionError("verified transition requires canonical compile and test evidence")
        return tuple(rows)

    def verify_patch(self, patch_id: str, *, evidence_attestation_ids: tuple[str, ...]) -> CodingPatchCandidate:
        old = self.get_patch(patch_id)
        if old.status in {CodingPatchStatus.REJECTED, CodingPatchStatus.SUPERSEDED}:
            raise PermissionError("terminal patch status cannot be verified")
        evidence = self._verification_evidence(old, evidence_attestation_ids)
        by_id = {row.attestation_id: row for row in evidence}
        ids = tuple(sorted(by_id))
        digests = tuple(by_id[identity].digest for identity in ids)
        self._record_transition(
            old.patch_id,
            CodingPatchStatus.VERIFIED,
            evidence_attestation_ids=ids,
            evidence_attestation_digests=digests,
        )
        row = replace(old, status=CodingPatchStatus.VERIFIED)
        self._patches[row.patch_id] = row
        return row

    def is_currently_verified(
        self,
        patch_id: str,
        *,
        current_artifact_digest: str | None = None,
        current_source_revision: str | None = None,
    ) -> bool:
        patch = self.get_patch(patch_id)
        if patch.status is not CodingPatchStatus.VERIFIED or not patch.provenance_id or self.engineering_evidence is None:
            return False
        if current_artifact_digest is not None and str(current_artifact_digest) != patch.patch_artifact_digest:
            return False
        if current_source_revision is not None and str(current_source_revision) != patch.base_source_revision:
            return False
        try:
            receipt = self.latest_transition(patch.patch_id)
        except KeyError:
            return False
        if receipt.to_status is not CodingPatchStatus.VERIFIED or not receipt.evidence_attestation_ids:
            return False
        try:
            rows = self._verification_evidence(patch, receipt.evidence_attestation_ids)
        except (KeyError, PermissionError, ValueError):
            return False
        digests = {row.attestation_id: row.digest for row in rows}
        return all(
            digests.get(identity) == digest
            for identity, digest in zip(receipt.evidence_attestation_ids, receipt.evidence_attestation_digests)
        )

    def record_tool_invocation(
        self,
        *,
        agent_id: str,
        task_id: str,
        tool_id: str,
        input_artifact_refs: tuple[str, ...] = (),
        output_artifact_refs: tuple[str, ...] = (),
        success: bool,
        evidence_refs: tuple[str, ...] = (),
    ) -> ToolInvocationReceipt:
        agent = str(agent_id).strip()
        task = str(task_id).strip()
        tool = str(tool_id).strip()
        if not agent or not task or not tool:
            raise ValueError("tool invocation requires agent/task/tool")
        payload = {
            "agent_id": agent,
            "task_id": task,
            "tool_id": tool,
            "input_artifact_refs": [str(x) for x in input_artifact_refs],
            "output_artifact_refs": [str(x) for x in output_artifact_refs],
            "success": bool(success),
            "evidence_refs": [str(x) for x in evidence_refs],
        }
        digest = canonical_digest(payload)
        row = ToolInvocationReceipt(
            receipt_id="tool-" + digest[:20],
            agent_id=agent,
            task_id=task,
            tool_id=tool,
            input_artifact_refs=tuple(payload["input_artifact_refs"]),
            output_artifact_refs=tuple(payload["output_artifact_refs"]),
            success=bool(success),
            evidence_refs=tuple(payload["evidence_refs"]),
            digest=digest,
        )
        existing = self._tool_receipts.get(row.receipt_id)
        if existing is not None and existing != row:
            raise ValueError("tool receipt id collision")
        self._tool_receipts[row.receipt_id] = row
        return row

    def get_tool_receipt(self, receipt_id: str) -> ToolInvocationReceipt:
        try:
            return self._tool_receipts[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f"unknown tool receipt: {receipt_id}") from exc

    def tool_receipts(self) -> tuple[ToolInvocationReceipt, ...]:
        return tuple(self._tool_receipts[key] for key in sorted(self._tool_receipts))

    def to_state(self) -> dict[str, Any]:
        transitions = [row for patch_id in sorted(self._transitions) for row in self._transitions[patch_id]]
        return {
            "component_version": COMPONENT_VERSION,
            "patch_counter": self._patch_counter,
            "patches": [row.to_state() for row in self.patches()],
            "provenance": [self._provenance[key].to_state() for key in sorted(self._provenance)],
            "transitions": [row.to_state() for row in transitions],
            "tool_receipts": [row.to_state() for row in self.tool_receipts()],
        }

    @staticmethod
    def _candidate_matches_provenance(row: CodingPatchCandidate, provenance: PatchProvenanceEnvelope) -> bool:
        return (
            row.producer_agent_id == provenance.producer_agent_id
            and row.task_id == provenance.task_id
            and row.work_id == provenance.work_id
            and row.base_plan_version == provenance.base_plan_version
            and row.base_architecture_version == provenance.base_architecture_version
            and row.touched_files == provenance.touched_files
            and row.touched_symbols == provenance.touched_symbols
            and row.patch_artifact_id == provenance.patch_artifact_id
            and row.patch_artifact_digest == provenance.patch_artifact_digest
            and row.base_source_revision == provenance.base_source_revision
            and row.operation_ref == provenance.operation_ref
            and row.provenance_id == provenance.provenance_id
            and row.compile_evidence_refs == provenance.compile_evidence_refs
            and row.test_evidence_refs == provenance.test_evidence_refs
            and row.static_evidence_refs == provenance.static_evidence_refs
            and row.known_risks == provenance.known_risks
            and row.plan_gap_event_refs == provenance.plan_gap_event_refs
            and row.architecture_concern_event_refs == provenance.architecture_concern_event_refs
        )

    @classmethod
    def from_state(
        cls,
        *,
        claims: CodeClaimLedger,
        state: Mapping[str, Any],
        engineering_evidence: EngineeringEvidenceLedger | None = None,
    ) -> "CodingPatchLedger":
        version = str(state.get("component_version", "0.0.1"))
        if version not in {"0.0.1", COMPONENT_VERSION}:
            raise ValueError("unsupported coding patch snapshot version")
        ledger = cls(claims, engineering_evidence=engineering_evidence)

        for value in state.get("provenance", ()):
            provenance = PatchProvenanceEnvelope.from_state(value)
            if provenance.provenance_id in ledger._provenance:
                raise ValueError("duplicate patch provenance id in snapshot")
            existing = ledger._operation_index.get(provenance.operation_ref)
            if existing is not None and existing != provenance.provenance_id:
                raise ValueError("operation ref cannot be rebound in snapshot")
            ledger._provenance[provenance.provenance_id] = provenance
            ledger._operation_index[provenance.operation_ref] = provenance.provenance_id

        provenance_owners: dict[str, str] = {}
        for value in state.get("patches", ()):
            row = CodingPatchCandidate.from_state(value)
            if row.patch_id in ledger._patches:
                raise ValueError("duplicate patch id in snapshot")
            if row.provenance_id:
                try:
                    provenance = ledger.get_provenance(row.provenance_id)
                except KeyError as exc:
                    raise ValueError("patch provenance is missing from snapshot") from exc
                if not cls._candidate_matches_provenance(row, provenance):
                    raise ValueError("patch candidate/provenance binding mismatch")
                if row.provenance_id in provenance_owners:
                    raise ValueError("patch provenance cannot be rebound to multiple patches")
                provenance_owners[row.provenance_id] = row.patch_id
            ledger._patches[row.patch_id] = row

        if set(ledger._provenance) != set(provenance_owners):
            raise ValueError("patch provenance must have exactly one canonical patch owner")

        grouped: dict[str, list[PatchTransitionReceipt]] = {}
        seen_transition_ids: set[str] = set()
        for value in state.get("transitions", ()):
            receipt = PatchTransitionReceipt.from_state(value)
            if receipt.receipt_id in seen_transition_ids:
                raise ValueError("duplicate patch transition receipt")
            seen_transition_ids.add(receipt.receipt_id)
            if receipt.patch_id not in ledger._patches:
                raise ValueError("patch transition references unknown patch")
            patch = ledger._patches[receipt.patch_id]
            if not patch.provenance_id or receipt.provenance_id != patch.provenance_id:
                raise ValueError("patch transition provenance binding mismatch")
            provenance = ledger._provenance.get(patch.provenance_id)
            if provenance is None or provenance.digest != receipt.provenance_digest:
                raise ValueError("patch transition provenance binding mismatch")
            grouped.setdefault(receipt.patch_id, []).append(receipt)

        for patch_id, history in grouped.items():
            history.sort(key=lambda row: row.sequence)
            previous: PatchTransitionReceipt | None = None
            for expected_sequence, receipt in enumerate(history, 1):
                if receipt.sequence != expected_sequence:
                    raise ValueError("patch transition sequence is non-canonical")
                if previous is None:
                    if receipt.predecessor_receipt_id or receipt.predecessor_digest or receipt.from_status:
                        raise ValueError("patch transition genesis lineage mismatch")
                elif (
                    receipt.predecessor_receipt_id != previous.receipt_id
                    or receipt.predecessor_digest != previous.digest
                    or receipt.from_status != previous.to_status.value
                ):
                    raise ValueError("patch transition predecessor lineage mismatch")
                previous = receipt
            patch = ledger._patches[patch_id]
            if previous is not None and patch.status is not previous.to_status:
                raise ValueError("patch status does not match transition frontier")
            ledger._transitions[patch_id] = history

        for patch in ledger._patches.values():
            if patch.provenance_id and patch.patch_id not in ledger._transitions:
                raise ValueError("provenance-bound patch requires transition history")
            if patch.provenance_id and patch.status is CodingPatchStatus.VERIFIED:
                latest = ledger.latest_transition(patch.patch_id)
                if latest.to_status is not CodingPatchStatus.VERIFIED or not latest.evidence_attestation_ids:
                    raise ValueError("verified patch requires verified transition evidence")
                if engineering_evidence is not None:
                    try:
                        rows = ledger._verification_evidence(patch, latest.evidence_attestation_ids)
                    except (KeyError, PermissionError) as exc:
                        raise ValueError("verified transition is not supported by canonical live evidence") from exc
                    digests = {row.attestation_id: row.digest for row in rows}
                    if any(
                        digests.get(identity) != digest
                        for identity, digest in zip(latest.evidence_attestation_ids, latest.evidence_attestation_digests)
                    ):
                        raise ValueError("verified transition evidence digest mismatch")

        for value in state.get("tool_receipts", ()):
            row = ToolInvocationReceipt.from_state(value)
            existing = ledger._tool_receipts.get(row.receipt_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate tool receipt id in snapshot")
            ledger._tool_receipts[row.receipt_id] = row

        ledger._patch_counter = int(state.get("patch_counter", len(ledger._patches)))
        expected_max = 0
        for patch_id in ledger._patches:
            try:
                expected_max = max(expected_max, int(patch_id.rsplit("-", 1)[1]))
            except Exception as exc:
                raise ValueError("non-canonical patch id") from exc
        if ledger._patch_counter < expected_max:
            raise ValueError("patch counter is behind patch history")
        if version == COMPONENT_VERSION and ledger._patch_counter != expected_max:
            raise ValueError("patch counter frontier inflation is forbidden")
        return ledger


__all__ = (
    "CodingPatchStatus",
    "ToolInvocationReceipt",
    "PatchProvenanceEnvelope",
    "PatchTransitionReceipt",
    "CodingPatchCandidate",
    "CodingPatchLedger",
)
