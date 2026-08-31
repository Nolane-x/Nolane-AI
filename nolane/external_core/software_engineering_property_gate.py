from __future__ import annotations

from typing import Any, Mapping

from nolane.external_core._software_engineering_property_gate_v01 import (
    PROPERTY_GATE_VERSION,
    EngineeringPropertyBoundClosureReceipt,
    EngineeringPropertyGateBinding,
    EngineeringPropertyGateReceipt,
    EngineeringPropertyRequirement,
    EngineeringPropertyRequirementManifest,
    SoftwareEngineeringPropertyGate as _SoftwareEngineeringPropertyGateV01,
)
from nolane.external_core.software_engineering_property_evidence import (
    EngineeringPropertyEvidenceLedger,
)


class SoftwareEngineeringPropertyGate(_SoftwareEngineeringPropertyGateV01):
    """Hardened v0.1 property gate with semantic restore verification.

    The frozen v0.1 implementation defines the compatible state shape. This
    public wrapper proves that restored receipts still encode the complete
    required property set and that stored live closures are reproducible from
    the historical witness set plus the current canonical evidence ledger.
    """

    def _validate_restored_semantics(self) -> None:
        for row in self.gate_receipts():
            manifest = self.get_manifest(row.manifest_id)
            required_keys = {requirement.key for requirement in manifest.requirements}
            binding_keys = {binding.requirement_key for binding in row.bindings}

            for binding in row.bindings:
                obligation = self.property_evidence.get_obligation(binding.obligation_id)
                obligation_key = (
                    obligation.claim_id,
                    obligation.claim_class.value,
                    obligation.property_ref,
                )
                if binding.requirement_key != obligation_key:
                    raise ValueError(
                        "property gate binding semantic requirement/obligation lineage mismatch"
                    )
                if (
                    obligation.subject_ref != manifest.patch_ref
                    or obligation.subject_digest != manifest.patch_digest
                    or obligation.source_revision != manifest.source_revision
                ):
                    raise ValueError("property gate obligation patch/revision lineage mismatch")

                historical = self.property_evidence.get_receipt(
                    binding.historical_closure_id
                )
                if (
                    historical.obligation_id != obligation.obligation_id
                    or historical.obligation_digest != obligation.digest
                ):
                    raise ValueError(
                        "property gate historical closure/obligation lineage mismatch"
                    )

                live = self.property_evidence.assess(
                    obligation.obligation_id,
                    witness_ids=historical.witness_ids,
                )
                if (
                    live.receipt_id != binding.live_closure_id
                    or live.digest != binding.live_closure_digest
                    or live.ready != binding.currently_closed
                ):
                    raise ValueError(
                        "property gate live closure is not reproducible from current evidence"
                    )

            expected_ready = (
                not row.reasons
                and binding_keys == required_keys
                and len(row.bindings) == len(manifest.requirements)
                and all(binding.currently_closed for binding in row.bindings)
            )
            if row.ready != expected_ready:
                raise ValueError(
                    "property gate ready state violates complete required binding coverage"
                )

        for terminal in self.terminal_closures():
            gate = self.get_gate_receipt(terminal.property_gate_receipt_id)
            if terminal.ready and not gate.ready:
                raise ValueError(
                    "ready property-bound terminal closure requires a ready property gate"
                )

    @classmethod
    def from_state(
        cls,
        *,
        property_evidence: EngineeringPropertyEvidenceLedger,
        state: Mapping[str, Any],
    ) -> "SoftwareEngineeringPropertyGate":
        gate = super().from_state(
            property_evidence=property_evidence,
            state=state,
        )
        gate._validate_restored_semantics()
        return gate


__all__ = (
    "PROPERTY_GATE_VERSION",
    "EngineeringPropertyRequirement",
    "EngineeringPropertyRequirementManifest",
    "EngineeringPropertyGateBinding",
    "EngineeringPropertyGateReceipt",
    "EngineeringPropertyBoundClosureReceipt",
    "SoftwareEngineeringPropertyGate",
)
