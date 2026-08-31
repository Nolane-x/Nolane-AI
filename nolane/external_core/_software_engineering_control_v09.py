from __future__ import annotations

from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core._software_engineering_control_v08 import (
    CANONICAL_WRITE_AUTHORITY,
    COMPONENT_ID as BASE_COMPONENT_ID,
    COMPONENT_VERSION as V08_COMPONENT_VERSION,
    EngineeringWorkRecord,
    SoftwareEngineeringControlPlane as _SoftwareEngineeringControlPlaneV08,
)
from nolane.external_core.coding_claims import CodeClaimLedger
from nolane.external_core.software_engineering_property_evidence import (
    EngineeringPropertyEvidenceLedger,
    EngineeringPropertyObligation,
    EngineeringPropertyWitness,
    EngineeringProofMethod,
    EngineeringWitnessRole,
)
from nolane.external_core.software_engineering_property_gate import (
    EngineeringPropertyBoundClosureReceipt,
    EngineeringPropertyGateReceipt,
    EngineeringPropertyRequirement,
    EngineeringPropertyRequirementManifest,
    SoftwareEngineeringPropertyGate,
)


COMPONENT_ID = BASE_COMPONENT_ID
COMPONENT_VERSION = "0.9.0"


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


class SoftwareEngineeringControlPlane(_SoftwareEngineeringControlPlaneV08):
    """Unified F control with semantic-property closure as first-class state.

    v0.8 remains frozen in `_software_engineering_control_v08`.  This v0.9
    layer is a monotonic extension: all historical Coding/Debug/UI/Engineering
    receipt identities retain their old semantics while new property
    obligations, oracle-bound witnesses, complete-set manifests and terminal
    property bindings share the canonical EngineeringEvidenceLedger.

    The extension does not acquire canonical component write authority and
    cannot promote/deploy/release.  Its strongest positive result remains a
    candidate-only property-bound closure.
    """

    def __init__(
        self,
        *,
        claims: CodeClaimLedger,
        property_evidence: EngineeringPropertyEvidenceLedger | None = None,
        property_gate: SoftwareEngineeringPropertyGate | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(claims=claims, **kwargs)

        if property_evidence is None:
            self.property_evidence = EngineeringPropertyEvidenceLedger(evidence=self.evidence)
        elif property_evidence.evidence is self.evidence:
            self.property_evidence = property_evidence
        else:
            self.property_evidence = EngineeringPropertyEvidenceLedger.from_state(
                evidence=self.evidence,
                state=property_evidence.to_state(),
            )

        if property_gate is None:
            self.property_gate = SoftwareEngineeringPropertyGate(
                property_evidence=self.property_evidence,
            )
        elif property_gate.property_evidence is self.property_evidence:
            self.property_gate = property_gate
        else:
            self.property_gate = SoftwareEngineeringPropertyGate.from_state(
                property_evidence=self.property_evidence,
                state=property_gate.to_state(),
            )

        if self.property_evidence.evidence is not self.evidence:
            raise ValueError("property evidence must share canonical engineering evidence ledger")
        if self.property_gate.property_evidence is not self.property_evidence:
            raise ValueError("property gate must share canonical property evidence ledger")

    @property
    def property_candidate_authority(self) -> str:
        return "candidate_only"

    def register_property_manifest(
        self,
        *,
        work_id: str,
        source_authority_ref: str,
        requirements: tuple[EngineeringPropertyRequirement, ...],
    ) -> EngineeringPropertyRequirementManifest:
        work = self.work(work_id)
        return self.property_gate.register_manifest(
            patch_ref=work.patch_ref,
            patch_digest=work.patch_digest,
            source_revision=work.source_revision,
            source_authority_ref=source_authority_ref,
            requirements=requirements,
        )

    def register_property_obligation(
        self,
        *,
        work_id: str,
        requirement: EngineeringPropertyRequirement,
        min_independent_sources: int | None = None,
    ) -> EngineeringPropertyObligation:
        work = self.work(work_id)
        return self.property_evidence.register_obligation(
            claim_id=requirement.claim_id,
            claim_class=requirement.claim_class,
            property_ref=requirement.property_ref,
            subject_ref=work.patch_ref,
            subject_digest=work.patch_digest,
            source_revision=work.source_revision,
            min_independent_sources=min_independent_sources,
        )

    def record_property_witness(
        self,
        *,
        obligation_id: str,
        attestation_id: str,
        method: EngineeringProofMethod,
        role: EngineeringWitnessRole,
        measured_property_ref: str,
        oracle_ref: str,
        source_family: str,
        baseline_revision: str | None = None,
        falsifier_ref: str | None = None,
        adversarial: bool = False,
    ) -> EngineeringPropertyWitness:
        return self.property_evidence.record_witness(
            obligation_id=obligation_id,
            attestation_id=attestation_id,
            method=method,
            role=role,
            measured_property_ref=measured_property_ref,
            oracle_ref=oracle_ref,
            source_family=source_family,
            baseline_revision=baseline_revision,
            falsifier_ref=falsifier_ref,
            adversarial=adversarial,
        )

    def assess_property_gate(
        self,
        manifest_id: str,
        *,
        property_bindings: tuple[tuple[str, str], ...],
    ) -> EngineeringPropertyGateReceipt:
        return self.property_gate.assess(
            manifest_id,
            property_bindings=property_bindings,
        )

    def bind_property_terminal_closure(
        self,
        *,
        base_closure: Any,
        property_gate_receipt_id: str,
    ) -> EngineeringPropertyBoundClosureReceipt:
        return self.property_gate.bind_terminal_closure(
            base_closure=base_closure,
            property_gate_receipt_id=property_gate_receipt_id,
        )

    def assess_property_bound_candidate(
        self,
        *,
        legacy_gate_receipt_id: str,
        property_manifest_id: str,
        property_bindings: tuple[tuple[str, str], ...],
    ) -> EngineeringPropertyBoundClosureReceipt:
        """Bind live semantic properties to one already-governed F candidate.

        The legacy governed gate remains historically verifiable, but it cannot
        be silently upgraded into a v1 property-bound result.  A clean legacy
        gate with a concrete closure is required; then every manifest property
        is re-evaluated against current evidence before a new candidate-only
        terminal receipt is minted.
        """
        legacy_gate = self.gate.get(legacy_gate_receipt_id)
        if not legacy_gate.ready or legacy_gate.closure_receipt_id is None:
            raise PermissionError(
                "property-bound candidate requires a ready legacy governed engineering closure"
            )
        base_closure = self.closure.get(legacy_gate.closure_receipt_id)
        if base_closure.digest != legacy_gate.closure_digest:
            raise ValueError("legacy gate closure digest lineage mismatch")
        property_gate = self.assess_property_gate(
            property_manifest_id,
            property_bindings=property_bindings,
        )
        return self.bind_property_terminal_closure(
            base_closure=base_closure,
            property_gate_receipt_id=property_gate.receipt_id,
        )

    def _state_payload(self) -> dict[str, Any]:
        payload = super()._state_payload()
        payload["component_version"] = COMPONENT_VERSION
        payload["property_evidence"] = self.property_evidence.to_state()
        payload["property_gate"] = self.property_gate.to_state()
        return payload

    @classmethod
    def _lift_v08(
        cls,
        *,
        claims: CodeClaimLedger,
        state: Mapping[str, Any],
    ) -> "SoftwareEngineeringControlPlane":
        legacy = _SoftwareEngineeringControlPlaneV08.from_state(claims=claims, state=state)
        return cls(
            claims=claims,
            evidence=legacy.evidence,
            transactions=legacy.transactions,
            claim_bindings=legacy.claim_bindings,
            manifests=legacy.manifests,
            closure=legacy.closure,
            policy=legacy.policy,
            gate=legacy.gate,
            mutation_authority=legacy.mutation_authority,
            effects=legacy.effects,
            validity=legacy.validity,
            works={row.work_id: row for row in legacy.works()},
            effect_journal=legacy.effect_journal,
            effect_dispatch=legacy.effect_dispatch,
        )

    @classmethod
    def from_state(
        cls,
        *,
        claims: CodeClaimLedger,
        state: Mapping[str, Any],
    ) -> "SoftwareEngineeringControlPlane":
        if _text(state["component_id"], field="component id") != COMPONENT_ID:
            raise ValueError("software engineering control component id mismatch")
        version = _text(state["component_version"], field="component version")
        if version == V08_COMPONENT_VERSION:
            return cls._lift_v08(claims=claims, state=state)
        if version != COMPONENT_VERSION:
            raise ValueError("software engineering control component version mismatch")

        supplied_digest = _text(state["digest"], field="software engineering state digest")
        payload = {key: value for key, value in state.items() if key != "digest"}
        if canonical_digest(payload) != supplied_digest:
            raise ValueError("software engineering control snapshot digest mismatch")
        if "property_evidence" not in state or "property_gate" not in state:
            raise ValueError("software engineering v0.9 snapshot requires property protocol state")

        base_payload = {
            key: value
            for key, value in state.items()
            if key not in {"digest", "property_evidence", "property_gate"}
        }
        base_payload["component_version"] = V08_COMPONENT_VERSION
        base_state = {**base_payload, "digest": canonical_digest(base_payload)}
        base = _SoftwareEngineeringControlPlaneV08.from_state(
            claims=claims,
            state=base_state,
        )
        property_evidence = EngineeringPropertyEvidenceLedger.from_state(
            evidence=base.evidence,
            state=state["property_evidence"],
        )
        property_gate = SoftwareEngineeringPropertyGate.from_state(
            property_evidence=property_evidence,
            state=state["property_gate"],
        )
        plane = cls(
            claims=claims,
            evidence=base.evidence,
            transactions=base.transactions,
            claim_bindings=base.claim_bindings,
            manifests=base.manifests,
            closure=base.closure,
            policy=base.policy,
            gate=base.gate,
            mutation_authority=base.mutation_authority,
            effects=base.effects,
            validity=base.validity,
            works={row.work_id: row for row in base.works()},
            effect_journal=base.effect_journal,
            effect_dispatch=base.effect_dispatch,
            property_evidence=property_evidence,
            property_gate=property_gate,
        )
        if plane.digest != supplied_digest:
            raise ValueError("software engineering control restore is not state-identical")
        return plane


__all__ = (
    "CANONICAL_WRITE_AUTHORITY",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "EngineeringWorkRecord",
    "SoftwareEngineeringControlPlane",
)
