from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding_claims import (
    ClaimMode,
    ClaimStatus,
    CodeClaim,
    CodeClaimLedger,
)
from nolane.external_core.software_engineering import (
    EngineeringEvidenceAttestation,
    EngineeringEvidenceKind,
    EngineeringEvidenceLedger,
    EngineeringPatchTransaction,
    PatchTransactionLedger,
    SoftwareEngineeringClosureEngine,
)
from nolane.external_core.software_engineering_policy import (
    EngineeringChangeManifestLedger,
    EngineeringGateReceipt,
    EngineeringRiskClass,
    EngineeringVerificationPolicy,
    GovernedEngineeringGate,
)
from nolane.external_core.software_engineering_validity import (
    EngineeringClaimBindingLedger,
    EngineeringCurrentValidityReceipt,
    EngineeringValidityEngine,
)


COMPONENT_ID = "external.software_engineering.control"
COMPONENT_VERSION = "0.3.0"


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


def _refs(values: Sequence[Any]) -> tuple[str, ...]:
    return tuple(sorted({_text(value, field="reference") for value in values}))


def _path_under(path: str, prefix: str) -> bool:
    normalized_path = str(path).replace("\\", "/").strip()
    normalized_prefix = str(prefix).replace("\\", "/").strip().rstrip("/")
    return normalized_path == normalized_prefix or normalized_path.startswith(normalized_prefix + "/")


def _claims_cover_patch(claims: tuple[CodeClaim, ...], patch: Any) -> bool:
    required_attrs = ("producer_agent_id", "task_id", "touched_files", "touched_symbols")
    if not claims or not all(hasattr(patch, name) for name in required_attrs):
        return False
    producer = str(patch.producer_agent_id)
    task_id = str(patch.task_id)
    for claim in claims:
        if (
            claim.status is not ClaimStatus.ACTIVE
            or claim.mode is not ClaimMode.EXCLUSIVE_WRITE
            or claim.agent_id != producer
            or claim.task_id != task_id
        ):
            return False
    for raw_path in tuple(patch.touched_files):
        path = str(raw_path).replace("\\", "/").strip()
        if not any(
            path in claim.file_paths
            or any(_path_under(path, prefix) for prefix in claim.directory_prefixes)
            for claim in claims
        ):
            return False
    for raw_symbol in tuple(patch.touched_symbols):
        symbol = str(raw_symbol).strip()
        if not any(symbol in claim.symbol_ids for claim in claims):
            return False
    return True


@dataclass(frozen=True, slots=True)
class EngineeringWorkRecord:
    work_id: str
    patch_ref: str
    patch_digest: str
    source_revision: str
    manifest_id: str
    manifest_digest: str
    transaction_id: str
    claim_binding_id: str
    claim_binding_digest: str
    authority: str
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.work_id, "engineering work id"),
            (self.patch_ref, "patch ref"),
            (self.patch_digest, "patch digest"),
            (self.source_revision, "source revision"),
            (self.manifest_id, "manifest id"),
            (self.manifest_digest, "manifest digest"),
            (self.transaction_id, "transaction id"),
            (self.claim_binding_id, "claim binding id"),
            (self.claim_binding_digest, "claim binding digest"),
            (self.digest, "engineering work digest"),
        ):
            _text(value, field=field)
        if self.authority != "candidate_only":
            raise ValueError("engineering work cannot hold promotion authority")

    def payload(self) -> dict[str, Any]:
        return {
            "patch_ref": self.patch_ref,
            "patch_digest": self.patch_digest,
            "source_revision": self.source_revision,
            "manifest_id": self.manifest_id,
            "manifest_digest": self.manifest_digest,
            "transaction_id": self.transaction_id,
            "claim_binding_id": self.claim_binding_id,
            "claim_binding_digest": self.claim_binding_digest,
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"work_id": self.work_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringWorkRecord":
        row = cls(
            work_id=_text(state["work_id"], field="engineering work id"),
            patch_ref=_text(state["patch_ref"], field="patch ref"),
            patch_digest=_text(state["patch_digest"], field="patch digest"),
            source_revision=_text(state["source_revision"], field="source revision"),
            manifest_id=_text(state["manifest_id"], field="manifest id"),
            manifest_digest=_text(state["manifest_digest"], field="manifest digest"),
            transaction_id=_text(state["transaction_id"], field="transaction id"),
            claim_binding_id=_text(state["claim_binding_id"], field="claim binding id"),
            claim_binding_digest=_text(state["claim_binding_digest"], field="claim binding digest"),
            authority=_text(state["authority"], field="engineering work authority"),
            digest=_text(state["digest"], field="engineering work digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.work_id != f"eng-work-{expected[:20]}":
            raise ValueError("engineering work digest/id mismatch")
        return row


class SoftwareEngineeringControlPlane:
    """Unified governed entry point for F. Software Engineering.

    This object composes existing canonical claim authority with the new
    evidence, reversible transaction, blast-radius policy, closure and live
    validity layers. It never promotes beyond `candidate_only`.
    """

    def __init__(
        self,
        *,
        claims: CodeClaimLedger,
        evidence: EngineeringEvidenceLedger | None = None,
        transactions: PatchTransactionLedger | None = None,
        claim_bindings: EngineeringClaimBindingLedger | None = None,
        manifests: EngineeringChangeManifestLedger | None = None,
        closure: SoftwareEngineeringClosureEngine | None = None,
        policy: EngineeringVerificationPolicy | None = None,
        gate: GovernedEngineeringGate | None = None,
        validity: EngineeringValidityEngine | None = None,
        works: Mapping[str, EngineeringWorkRecord] | None = None,
    ) -> None:
        self.claims = claims
        self.evidence = evidence if evidence is not None else EngineeringEvidenceLedger()
        self.transactions = transactions if transactions is not None else PatchTransactionLedger(self.evidence)
        self.claim_bindings = (
            claim_bindings
            if claim_bindings is not None
            else EngineeringClaimBindingLedger(transactions=self.transactions, claims=self.claims)
        )
        self.manifests = manifests if manifests is not None else EngineeringChangeManifestLedger()
        self.closure = (
            closure
            if closure is not None
            else SoftwareEngineeringClosureEngine(evidence=self.evidence, transactions=self.transactions)
        )
        self.policy = policy if policy is not None else EngineeringVerificationPolicy()
        self.gate = (
            gate
            if gate is not None
            else GovernedEngineeringGate(
                evidence=self.evidence,
                transactions=self.transactions,
                closure=self.closure,
                claims=self.claims,
                claim_bindings=self.claim_bindings,
                policy=self.policy,
            )
        )
        self.validity = (
            validity
            if validity is not None
            else EngineeringValidityEngine(
                evidence=self.evidence,
                transactions=self.transactions,
                closure=self.closure,
                claims=self.claims,
                claim_bindings=self.claim_bindings,
            )
        )
        self._works = dict(works or {})

    @property
    def digest(self) -> str:
        return canonical_digest(self._state_payload())

    def works(self) -> tuple[EngineeringWorkRecord, ...]:
        return tuple(self._works[key] for key in sorted(self._works))

    def work(self, work_id: str) -> EngineeringWorkRecord:
        try:
            return self._works[str(work_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering work: {work_id}") from exc

    def begin_patch(
        self,
        *,
        patch: Any,
        source_revision: str,
        rollback_artifact_ref: str,
        claim_refs: tuple[str, ...],
        dependency_refs: tuple[str, ...] = (),
        impacted_component_refs: tuple[str, ...] = (),
        declared_risk: EngineeringRiskClass = EngineeringRiskClass.LOW,
        ui_sensitive: bool = False,
        security_sensitive: bool = False,
        performance_sensitive: bool = False,
        debug_origin: bool = False,
    ) -> EngineeringWorkRecord:
        if not hasattr(patch, "to_state"):
            raise TypeError("governed engineering work requires canonical patch state")
        patch_ref = _text(getattr(patch, "patch_id"), field="patch id")
        patch_digest = canonical_digest(patch.to_state())
        source = _text(source_revision, field="source revision")
        rollback = _text(rollback_artifact_ref, field="rollback artifact")
        refs = _refs(claim_refs)
        if not refs:
            raise ValueError("governed patch work requires bound claims")
        bound_claims = tuple(self.claims.get(claim_id) for claim_id in refs)
        if not _claims_cover_patch(bound_claims, patch):
            raise PermissionError("transaction-bound claims do not authorize patch scope/lineage")

        manifest = self.manifests.register(
            patch=patch,
            source_revision=source,
            dependency_refs=dependency_refs,
            impacted_component_refs=impacted_component_refs,
            declared_risk=declared_risk,
            ui_sensitive=ui_sensitive,
            security_sensitive=security_sensitive,
            performance_sensitive=performance_sensitive,
            debug_origin=debug_origin,
        )
        tx = self.transactions.begin(
            patch_ref=patch_ref,
            patch_digest=patch_digest,
            source_revision=source,
            rollback_artifact_ref=rollback,
        )
        tx = self.transactions.bind_claims(tx.transaction_id, claim_refs=refs)
        binding = self.claim_bindings.bind(tx.transaction_id)
        if not self.claim_bindings.covers_patch(binding.binding_id, patch):
            raise PermissionError("snapshotted transaction claims do not authorize patch")

        payload = {
            "patch_ref": patch_ref,
            "patch_digest": patch_digest,
            "source_revision": source,
            "manifest_id": manifest.manifest_id,
            "manifest_digest": manifest.digest,
            "transaction_id": tx.transaction_id,
            "claim_binding_id": binding.binding_id,
            "claim_binding_digest": binding.digest,
            "authority": "candidate_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringWorkRecord(
            work_id=f"eng-work-{digest[:20]}",
            patch_ref=patch_ref,
            patch_digest=patch_digest,
            source_revision=source,
            manifest_id=manifest.manifest_id,
            manifest_digest=manifest.digest,
            transaction_id=tx.transaction_id,
            claim_binding_id=binding.binding_id,
            claim_binding_digest=binding.digest,
            authority="candidate_only",
            digest=digest,
        )
        existing = self._works.get(row.work_id)
        if existing is not None and existing != row:
            raise ValueError("engineering work id cannot be rebound")
        self._works[row.work_id] = row
        return existing or row

    def record_evidence(
        self,
        *,
        patch: Any,
        source_revision: str,
        environment_digest: str,
        verifier_agent_id: str,
        verifier_region: str,
        kind: EngineeringEvidenceKind,
        passed: bool,
        evidence_refs: tuple[str, ...],
        dependencies: tuple[str, ...] = (),
    ) -> EngineeringEvidenceAttestation:
        if not hasattr(patch, "to_state"):
            raise TypeError("engineering evidence requires canonical patch state")
        return self.evidence.record(
            subject_ref=_text(getattr(patch, "patch_id"), field="patch id"),
            subject_digest=canonical_digest(patch.to_state()),
            producer_agent_id=_text(getattr(patch, "producer_agent_id"), field="patch producer"),
            verifier_agent_id=verifier_agent_id,
            verifier_region=verifier_region,
            kind=kind,
            passed=passed,
            evidence_refs=evidence_refs,
            source_revision=source_revision,
            environment_digest=environment_digest,
            dependencies=dependencies,
        )

    def verify_preconditions(
        self,
        transaction_id: str,
        *,
        attestation_ids: tuple[str, ...],
    ) -> EngineeringPatchTransaction:
        return self.transactions.verify_preconditions(
            transaction_id,
            attestation_ids=attestation_ids,
        )

    def mark_applied(self, transaction_id: str, *, application_ref: str) -> EngineeringPatchTransaction:
        binding = self.claim_bindings.for_transaction(transaction_id)
        if binding is None:
            raise PermissionError("patch application requires immutable claim-state binding")
        if self.claim_bindings.current_reasons(binding.binding_id):
            raise PermissionError("patch application requires unchanged active bound claims")
        return self.transactions.mark_applied(transaction_id, application_ref=application_ref)

    def observe_outcome(
        self,
        transaction_id: str,
        *,
        evidence_refs: tuple[str, ...],
    ) -> EngineeringPatchTransaction:
        return self.transactions.observe_outcome(transaction_id, evidence_refs=evidence_refs)

    def verify_postconditions(
        self,
        transaction_id: str,
        *,
        attestation_ids: tuple[str, ...],
    ) -> EngineeringPatchTransaction:
        return self.transactions.verify_postconditions(
            transaction_id,
            attestation_ids=attestation_ids,
        )

    def assess_candidate(
        self,
        *,
        work_id: str,
        patch: Any,
        coding_readiness: Any,
        current_source_revision: str,
        attestation_ids: tuple[str, ...],
        debug_resolution: Any | None = None,
        ui_readiness: Any | None = None,
    ) -> EngineeringGateReceipt:
        work = self.work(work_id)
        if not hasattr(patch, "to_state"):
            raise TypeError("candidate assessment requires canonical patch state")
        patch_digest = canonical_digest(patch.to_state())
        if str(getattr(patch, "patch_id", "")) != work.patch_ref or patch_digest != work.patch_digest:
            raise ValueError("engineering work patch lineage mismatch")
        manifest = self.manifests.get(work.manifest_id)
        if manifest.digest != work.manifest_digest:
            raise ValueError("engineering work manifest lineage mismatch")
        binding = self.claim_bindings.get(work.claim_binding_id)
        if binding.digest != work.claim_binding_digest or binding.transaction_id != work.transaction_id:
            raise ValueError("engineering work claim binding lineage mismatch")
        return self.gate.assess(
            manifest=manifest,
            patch=patch,
            coding_readiness=coding_readiness,
            transaction_id=work.transaction_id,
            current_source_revision=current_source_revision,
            attestation_ids=attestation_ids,
            debug_resolution=debug_resolution,
            ui_readiness=ui_readiness,
        )

    def revalidate(
        self,
        gate_receipt_id: str,
        *,
        patch: Any,
        current_source_revision: str,
    ) -> EngineeringCurrentValidityReceipt:
        gate = self.gate.get(gate_receipt_id)
        if gate.closure_receipt_id is None:
            raise PermissionError("engineering gate has no historical closure to revalidate")
        return self.validity.revalidate(
            gate.closure_receipt_id,
            patch=patch,
            current_source_revision=current_source_revision,
        )

    def _state_payload(self) -> dict[str, Any]:
        return {
            "component_id": COMPONENT_ID,
            "component_version": COMPONENT_VERSION,
            "works": [row.to_state() for row in self.works()],
            "evidence": self.evidence.to_state(),
            "transactions": self.transactions.to_state(),
            "claim_bindings": self.claim_bindings.to_state(),
            "manifests": self.manifests.to_state(),
            "policy": self.policy.to_state(),
            "closure": self.closure.to_state(),
            "gate": self.gate.to_state(),
            "validity": self.validity.to_state(),
        }

    def to_state(self) -> dict[str, Any]:
        payload = self._state_payload()
        return {**payload, "digest": canonical_digest(payload)}

    @classmethod
    def from_state(
        cls,
        *,
        claims: CodeClaimLedger,
        state: Mapping[str, Any],
    ) -> "SoftwareEngineeringControlPlane":
        if _text(state["component_id"], field="component id") != COMPONENT_ID:
            raise ValueError("software engineering control component id mismatch")
        if _text(state["component_version"], field="component version") != COMPONENT_VERSION:
            raise ValueError("software engineering control component version mismatch")
        supplied_digest = _text(state["digest"], field="software engineering state digest")
        payload = {key: value for key, value in state.items() if key != "digest"}
        if canonical_digest(payload) != supplied_digest:
            raise ValueError("software engineering control snapshot digest mismatch")

        evidence = EngineeringEvidenceLedger.from_state(state["evidence"])
        transactions = PatchTransactionLedger.from_state(
            evidence=evidence,
            state=state["transactions"],
        )
        claim_bindings = EngineeringClaimBindingLedger.from_state(
            transactions=transactions,
            claims=claims,
            state=state["claim_bindings"],
        )
        manifests = EngineeringChangeManifestLedger.from_state(state["manifests"])
        closure = SoftwareEngineeringClosureEngine.from_state(
            evidence=evidence,
            transactions=transactions,
            state=state["closure"],
        )
        policy = EngineeringVerificationPolicy.from_state(state["policy"])
        gate = GovernedEngineeringGate.from_state(
            evidence=evidence,
            transactions=transactions,
            closure=closure,
            claims=claims,
            claim_bindings=claim_bindings,
            policy=policy,
            manifests=manifests,
            state=state["gate"],
        )
        validity = EngineeringValidityEngine.from_state(
            evidence=evidence,
            transactions=transactions,
            closure=closure,
            claims=claims,
            claim_bindings=claim_bindings,
            state=state["validity"],
        )

        works: dict[str, EngineeringWorkRecord] = {}
        for value in state.get("works", ()):
            row = EngineeringWorkRecord.from_state(value)
            manifest = manifests.get(row.manifest_id)
            if (
                manifest.digest != row.manifest_digest
                or manifest.patch_ref != row.patch_ref
                or manifest.patch_digest != row.patch_digest
                or manifest.source_revision != row.source_revision
            ):
                raise ValueError("engineering work manifest lineage mismatch")
            tx = transactions.get(row.transaction_id)
            if (
                tx.patch_ref != row.patch_ref
                or tx.patch_digest != row.patch_digest
                or tx.source_revision != row.source_revision
            ):
                raise ValueError("engineering work transaction lineage mismatch")
            binding = claim_bindings.get(row.claim_binding_id)
            if binding.digest != row.claim_binding_digest or binding.transaction_id != row.transaction_id:
                raise ValueError("engineering work claim binding lineage mismatch")
            existing = works.get(row.work_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound engineering work")
            works[row.work_id] = row

        plane = cls(
            claims=claims,
            evidence=evidence,
            transactions=transactions,
            claim_bindings=claim_bindings,
            manifests=manifests,
            closure=closure,
            policy=policy,
            gate=gate,
            validity=validity,
            works=works,
        )
        if plane.digest != supplied_digest:
            raise ValueError("software engineering control restore is not state-identical")
        return plane


__all__ = (
    "EngineeringWorkRecord",
    "SoftwareEngineeringControlPlane",
)
