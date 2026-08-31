from __future__ import annotations

from typing import Any

from nolane.external_core._software_engineering_control_v09 import (
    CANONICAL_WRITE_AUTHORITY,
    COMPONENT_ID,
    COMPONENT_VERSION,
    EngineeringWorkRecord,
    SoftwareEngineeringControlPlane as _SoftwareEngineeringControlPlaneV09,
)
from nolane.external_core.coding_claims import CodeClaimLedger
from nolane.external_core.software_engineering_property_gate import (
    EngineeringPropertyBoundClosureReceipt,
)


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


class SoftwareEngineeringControlPlane(_SoftwareEngineeringControlPlaneV09):
    """Hardened public F v0.9 control boundary.

    The frozen v0.9 implementation owns the compatible state/API shape. This
    public wrapper closes two authority/restore gaps without rewriting that
    shape: terminal property binding must start from a canonical legacy closure,
    and restored terminal receipts must reproduce their semantic lineage across
    the canonical legacy closure ledger and the property gate.
    """

    def __init__(self, *, claims: CodeClaimLedger, **kwargs: Any) -> None:
        super().__init__(claims=claims, **kwargs)
        self._validate_property_terminal_lineage()

    def _validate_property_terminal_lineage(self) -> None:
        for terminal in self.property_gate.terminal_closures():
            try:
                base = self.closure.get(terminal.base_closure_id)
            except KeyError as exc:
                raise ValueError(
                    "property-bound terminal closure requires canonical base engineering closure"
                ) from exc

            gate = self.property_gate.get_gate_receipt(
                terminal.property_gate_receipt_id
            )
            if terminal.base_closure_digest != base.digest:
                raise ValueError(
                    "property-bound terminal base closure digest lineage mismatch"
                )
            if (
                terminal.property_gate_digest != gate.digest
                or terminal.patch_ref != gate.patch_ref
                or terminal.patch_digest != gate.patch_digest
                or terminal.source_revision != gate.source_revision
            ):
                raise ValueError(
                    "property-bound terminal closure gate lineage mismatch"
                )

            reasons: list[str] = []
            if not base.ready:
                reasons.append("base_engineering_closure_not_ready")
            if (
                base.patch_ref != gate.patch_ref
                or base.patch_digest != gate.patch_digest
                or base.source_revision != gate.source_revision
            ):
                reasons.append("base_property_revision_mismatch")
            if not gate.ready:
                reasons.append("property_gate_not_ready")
            if getattr(base, "authority", None) != "candidate_only":
                reasons.append("base_closure_authority_not_candidate_only")

            normalized = tuple(sorted(set(reasons)))
            if terminal.reasons != normalized or terminal.ready != (not normalized):
                raise ValueError(
                    "property-bound terminal closure semantic lineage mismatch"
                )

    def bind_property_terminal_closure(
        self,
        *,
        base_closure: Any,
        property_gate_receipt_id: str,
    ) -> EngineeringPropertyBoundClosureReceipt:
        base_id = _text(
            getattr(base_closure, "receipt_id", ""),
            field="base engineering closure id",
        )
        try:
            canonical = self.closure.get(base_id)
        except KeyError as exc:
            raise PermissionError(
                "property terminal closure requires canonical legacy engineering closure"
            ) from exc

        provided_digest = _text(
            getattr(base_closure, "digest", ""),
            field="base engineering closure digest",
        )
        if canonical.digest != provided_digest:
            raise ValueError(
                "property terminal base closure digest lineage mismatch"
            )

        row = self.property_gate.bind_terminal_closure(
            base_closure=canonical,
            property_gate_receipt_id=property_gate_receipt_id,
        )
        self._validate_property_terminal_lineage()
        return row


__all__ = (
    "CANONICAL_WRITE_AUTHORITY",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "EngineeringWorkRecord",
    "SoftwareEngineeringControlPlane",
)
