from __future__ import annotations

from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core._software_engineering_control_v10 import (
    CANONICAL_WRITE_AUTHORITY,
    COMPONENT_ID as BASE_COMPONENT_ID,
    COMPONENT_VERSION as V10_COMPONENT_VERSION,
    EngineeringWorkRecord,
    SoftwareEngineeringControlPlane as _SoftwareEngineeringControlPlaneV10,
)
from nolane.external_core.coding_claims import CodeClaimLedger
from nolane.external_core.software_engineering_current_property_validity import (
    EngineeringCurrentPropertyBoundReceipt,
    SoftwareEngineeringCurrentPropertyValidity,
)
from nolane.external_core.software_engineering_property_gate import (
    EngineeringPropertyBoundClosureReceipt,
)


COMPONENT_ID = BASE_COMPONENT_ID
COMPONENT_VERSION = "1.1.0"


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


class SoftwareEngineeringControlPlane(_SoftwareEngineeringControlPlaneV10):
    """F v1.1 public control with live candidate truth-maintenance.

    F v1.0 remains frozen in `_software_engineering_control_v10`. Historical
    engineering closures and property gates stay immutable audit facts. This
    monotonic layer adds a current-validity view that rechecks both the legacy
    engineering truth line and semantic-property truth line against canonical
    live evidence, source revision and patch state.

    No release, deployment or promotion authority is acquired. The strongest
    positive result remains `candidate_only`.
    """

    def __init__(
        self,
        *,
        claims: CodeClaimLedger,
        current_property_validity: SoftwareEngineeringCurrentPropertyValidity | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(claims=claims, **kwargs)

        if current_property_validity is None:
            self.current_property_validity = SoftwareEngineeringCurrentPropertyValidity(
                validity=self.validity,
                property_gate=self.property_gate,
            )
        elif (
            current_property_validity.validity is self.validity
            and current_property_validity.property_gate is self.property_gate
        ):
            self.current_property_validity = current_property_validity
        else:
            self.current_property_validity = SoftwareEngineeringCurrentPropertyValidity.from_state(
                validity=self.validity,
                property_gate=self.property_gate,
                state=current_property_validity.to_state(),
            )

        if self.current_property_validity.validity is not self.validity:
            raise ValueError("current property validity must share canonical legacy validity engine")
        if self.current_property_validity.property_gate is not self.property_gate:
            raise ValueError("current property validity must share canonical property gate")

    @property
    def current_property_candidate_authority(self) -> str:
        return "candidate_only"

    def assess_current_property_bound_candidate(
        self,
        *,
        base_closure_id: str,
        property_gate_receipt_id: str,
        patch: Any,
        current_source_revision: str,
    ) -> EngineeringCurrentPropertyBoundReceipt:
        return self.current_property_validity.assess(
            base_closure_id=base_closure_id,
            property_gate_receipt_id=property_gate_receipt_id,
            patch=patch,
            current_source_revision=current_source_revision,
        )

    def _state_payload(self) -> dict[str, Any]:
        payload = super()._state_payload()
        payload["component_version"] = COMPONENT_VERSION
        payload["current_property_validity"] = self.current_property_validity.to_state()
        return payload

    @classmethod
    def _from_frozen_plane(
        cls,
        *,
        claims: CodeClaimLedger,
        frozen: _SoftwareEngineeringControlPlaneV10,
        current_property_validity: SoftwareEngineeringCurrentPropertyValidity | None = None,
    ) -> "SoftwareEngineeringControlPlane":
        return cls(
            claims=claims,
            evidence=frozen.evidence,
            transactions=frozen.transactions,
            claim_bindings=frozen.claim_bindings,
            manifests=frozen.manifests,
            closure=frozen.closure,
            policy=frozen.policy,
            gate=frozen.gate,
            mutation_authority=frozen.mutation_authority,
            effects=frozen.effects,
            validity=frozen.validity,
            works={row.work_id: row for row in frozen.works()},
            effect_journal=frozen.effect_journal,
            effect_dispatch=frozen.effect_dispatch,
            property_evidence=frozen.property_evidence,
            property_gate=frozen.property_gate,
            current_property_validity=current_property_validity,
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

        if version != COMPONENT_VERSION:
            frozen = _SoftwareEngineeringControlPlaneV10.from_state(
                claims=claims,
                state=state,
            )
            return cls._from_frozen_plane(claims=claims, frozen=frozen)

        supplied_digest = _text(state["digest"], field="software engineering state digest")
        payload = {key: value for key, value in state.items() if key != "digest"}
        if canonical_digest(payload) != supplied_digest:
            raise ValueError("software engineering control snapshot digest mismatch")
        if "current_property_validity" not in state:
            raise ValueError("software engineering v1.1 snapshot requires current property validity state")

        frozen_payload = {
            key: value
            for key, value in state.items()
            if key not in {"digest", "current_property_validity"}
        }
        frozen_payload["component_version"] = V10_COMPONENT_VERSION
        frozen_state = {
            **frozen_payload,
            "digest": canonical_digest(frozen_payload),
        }
        frozen = _SoftwareEngineeringControlPlaneV10.from_state(
            claims=claims,
            state=frozen_state,
        )
        current = SoftwareEngineeringCurrentPropertyValidity.from_state(
            validity=frozen.validity,
            property_gate=frozen.property_gate,
            state=state["current_property_validity"],
        )
        plane = cls._from_frozen_plane(
            claims=claims,
            frozen=frozen,
            current_property_validity=current,
        )
        if plane.digest != supplied_digest:
            raise ValueError("software engineering control restore is not state-identical")
        return plane


__all__ = (
    "CANONICAL_WRITE_AUTHORITY",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "EngineeringWorkRecord",
    "EngineeringPropertyBoundClosureReceipt",
    "EngineeringCurrentPropertyBoundReceipt",
    "SoftwareEngineeringControlPlane",
)
