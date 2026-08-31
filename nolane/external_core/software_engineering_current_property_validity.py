from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.software_engineering_property_gate import (
    EngineeringPropertyGateReceipt,
    SoftwareEngineeringPropertyGate,
)
from nolane.external_core.software_engineering_validity import (
    EngineeringCurrentValidityReceipt,
    EngineeringValidityEngine,
)


COMPONENT_ID = "external.software_engineering.current_property_validity"
COMPONENT_VERSION = "0.1.0"


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


def _refs(values: Sequence[Any]) -> tuple[str, ...]:
    return tuple(sorted({_text(value, field="reference") for value in values}))


@dataclass(frozen=True, slots=True)
class EngineeringCurrentPropertyBoundReceipt:
    """Current truth view over one historical legacy + semantic-property candidate.

    This receipt never rewrites either historical closure.  It binds their
    immutable identities to live revalidation receipts so a previously green
    candidate can become non-current when evidence, source revision, or patch
    state drifts.  Positive authority remains candidate-only.
    """

    receipt_id: str
    base_closure_id: str
    base_closure_digest: str
    historical_property_gate_receipt_id: str
    historical_property_gate_digest: str
    property_manifest_id: str
    property_manifest_digest: str
    current_validity_receipt_id: str
    current_validity_digest: str
    live_property_gate_receipt_id: str
    live_property_gate_digest: str
    patch_ref: str
    patch_digest: str
    current_source_revision: str
    current: bool
    reasons: tuple[str, ...]
    authority: str
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.receipt_id, "current property-bound receipt id"),
            (self.base_closure_id, "base engineering closure id"),
            (self.base_closure_digest, "base engineering closure digest"),
            (
                self.historical_property_gate_receipt_id,
                "historical property gate receipt id",
            ),
            (self.historical_property_gate_digest, "historical property gate digest"),
            (self.property_manifest_id, "property manifest id"),
            (self.property_manifest_digest, "property manifest digest"),
            (self.current_validity_receipt_id, "current legacy validity receipt id"),
            (self.current_validity_digest, "current legacy validity digest"),
            (self.live_property_gate_receipt_id, "live property gate receipt id"),
            (self.live_property_gate_digest, "live property gate digest"),
            (self.patch_ref, "patch ref"),
            (self.patch_digest, "patch digest"),
            (self.current_source_revision, "current source revision"),
            (self.digest, "current property-bound digest"),
        ):
            _text(value, field=field)
        if self.authority != "candidate_only":
            raise ValueError("current property validity cannot hold promotion authority")
        if self.current and self.reasons:
            raise ValueError("current property-bound candidate cannot contain blocking reasons")

    def payload(self) -> dict[str, Any]:
        return {
            "base_closure_id": self.base_closure_id,
            "base_closure_digest": self.base_closure_digest,
            "historical_property_gate_receipt_id": self.historical_property_gate_receipt_id,
            "historical_property_gate_digest": self.historical_property_gate_digest,
            "property_manifest_id": self.property_manifest_id,
            "property_manifest_digest": self.property_manifest_digest,
            "current_validity_receipt_id": self.current_validity_receipt_id,
            "current_validity_digest": self.current_validity_digest,
            "live_property_gate_receipt_id": self.live_property_gate_receipt_id,
            "live_property_gate_digest": self.live_property_gate_digest,
            "patch_ref": self.patch_ref,
            "patch_digest": self.patch_digest,
            "current_source_revision": self.current_source_revision,
            "current": self.current,
            "reasons": list(self.reasons),
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringCurrentPropertyBoundReceipt":
        row = cls(
            receipt_id=_text(state["receipt_id"], field="current property-bound receipt id"),
            base_closure_id=_text(state["base_closure_id"], field="base engineering closure id"),
            base_closure_digest=_text(
                state["base_closure_digest"], field="base engineering closure digest"
            ),
            historical_property_gate_receipt_id=_text(
                state["historical_property_gate_receipt_id"],
                field="historical property gate receipt id",
            ),
            historical_property_gate_digest=_text(
                state["historical_property_gate_digest"],
                field="historical property gate digest",
            ),
            property_manifest_id=_text(state["property_manifest_id"], field="property manifest id"),
            property_manifest_digest=_text(
                state["property_manifest_digest"], field="property manifest digest"
            ),
            current_validity_receipt_id=_text(
                state["current_validity_receipt_id"], field="current legacy validity receipt id"
            ),
            current_validity_digest=_text(
                state["current_validity_digest"], field="current legacy validity digest"
            ),
            live_property_gate_receipt_id=_text(
                state["live_property_gate_receipt_id"], field="live property gate receipt id"
            ),
            live_property_gate_digest=_text(
                state["live_property_gate_digest"], field="live property gate digest"
            ),
            patch_ref=_text(state["patch_ref"], field="patch ref"),
            patch_digest=_text(state["patch_digest"], field="patch digest"),
            current_source_revision=_text(
                state["current_source_revision"], field="current source revision"
            ),
            current=bool(state["current"]),
            reasons=_refs(tuple(state.get("reasons", ()))),
            authority=_text(state["authority"], field="current property validity authority"),
            digest=_text(state["digest"], field="current property-bound digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != f"eng-current-property-{expected[:20]}":
            raise ValueError("current property validity receipt digest/id mismatch")
        return row


class SoftwareEngineeringCurrentPropertyValidity:
    """Live truth-maintenance above immutable F engineering/property receipts.

    The legacy `EngineeringClosureReceipt` and historical property gate are
    audit facts.  They are not mutated when their evidence later becomes stale.
    This layer instead revalidates both truth lines and emits a new current view.
    It owns no mutation, release, deployment, or promotion authority.
    """

    def __init__(
        self,
        *,
        validity: EngineeringValidityEngine,
        property_gate: SoftwareEngineeringPropertyGate,
    ) -> None:
        if property_gate.property_evidence.evidence is not validity.evidence:
            raise ValueError(
                "current property validity requires one canonical engineering evidence ledger"
            )
        self.validity = validity
        self.property_gate = property_gate
        self._receipts: dict[str, EngineeringCurrentPropertyBoundReceipt] = {}

    def receipts(self) -> tuple[EngineeringCurrentPropertyBoundReceipt, ...]:
        return tuple(self._receipts[key] for key in sorted(self._receipts))

    def get(self, receipt_id: str) -> EngineeringCurrentPropertyBoundReceipt:
        try:
            return self._receipts[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering current property validity receipt: {receipt_id}") from exc

    @staticmethod
    def _historical_bindings(
        gate: EngineeringPropertyGateReceipt,
    ) -> tuple[tuple[str, str], ...]:
        return tuple(
            sorted(
                (
                    (binding.obligation_id, binding.historical_closure_id)
                    for binding in gate.bindings
                ),
                key=lambda row: (row[0], row[1]),
            )
        )

    def _live_property_gate(
        self,
        historical_gate: EngineeringPropertyGateReceipt,
    ) -> EngineeringPropertyGateReceipt:
        return self.property_gate.assess(
            historical_gate.manifest_id,
            property_bindings=self._historical_bindings(historical_gate),
        )

    def _base_reasons(
        self,
        *,
        base: Any,
        historical_gate: EngineeringPropertyGateReceipt,
        manifest: Any,
        current_validity: EngineeringCurrentValidityReceipt,
        live_gate: EngineeringPropertyGateReceipt,
        current_source_revision: str,
    ) -> tuple[str, ...]:
        reasons: list[str] = [
            f"legacy_current_validity:{reason}" for reason in current_validity.reasons
        ]

        if not historical_gate.ready:
            reasons.append("historical_property_gate_not_ready")
        if not live_gate.ready:
            reasons.append("property_gate_not_current")

        if (
            historical_gate.manifest_digest != manifest.digest
            or historical_gate.patch_ref != manifest.patch_ref
            or historical_gate.patch_digest != manifest.patch_digest
            or historical_gate.source_revision != manifest.source_revision
        ):
            reasons.append("historical_property_manifest_lineage_mismatch")

        if (
            historical_gate.patch_ref != base.patch_ref
            or historical_gate.patch_digest != base.patch_digest
            or historical_gate.source_revision != base.source_revision
        ):
            reasons.append("legacy_property_candidate_lineage_mismatch")

        if current_source_revision != historical_gate.source_revision:
            reasons.append("current_property_source_revision_mismatch")

        if (
            live_gate.patch_ref != historical_gate.patch_ref
            or live_gate.patch_digest != historical_gate.patch_digest
            or live_gate.source_revision != historical_gate.source_revision
            or live_gate.manifest_id != historical_gate.manifest_id
            or live_gate.manifest_digest != historical_gate.manifest_digest
        ):
            reasons.append("live_property_gate_lineage_mismatch")

        return tuple(sorted(set(reasons)))

    def assess(
        self,
        *,
        base_closure_id: str,
        property_gate_receipt_id: str,
        patch: Any,
        current_source_revision: str,
    ) -> EngineeringCurrentPropertyBoundReceipt:
        base = self.validity.closure.get(base_closure_id)
        historical_gate = self.property_gate.get_gate_receipt(property_gate_receipt_id)
        manifest = self.property_gate.get_manifest(historical_gate.manifest_id)
        source_revision = _text(current_source_revision, field="current source revision")

        current_validity = self.validity.revalidate(
            base.receipt_id,
            patch=patch,
            current_source_revision=source_revision,
        )
        live_gate = self._live_property_gate(historical_gate)

        reasons = list(
            self._base_reasons(
                base=base,
                historical_gate=historical_gate,
                manifest=manifest,
                current_validity=current_validity,
                live_gate=live_gate,
                current_source_revision=source_revision,
            )
        )

        if not hasattr(patch, "to_state"):
            reasons.append("missing_current_property_patch_state")
        else:
            current_patch_ref = str(getattr(patch, "patch_id", ""))
            current_patch_digest = canonical_digest(patch.to_state())
            if current_patch_ref != historical_gate.patch_ref:
                reasons.append("current_property_patch_identity_mismatch")
            elif current_patch_digest != historical_gate.patch_digest:
                reasons.append("current_property_patch_state_mismatch")

        normalized = tuple(sorted(set(reasons)))
        current = (
            current_validity.current
            and historical_gate.ready
            and live_gate.ready
            and not normalized
        )
        payload = {
            "base_closure_id": base.receipt_id,
            "base_closure_digest": base.digest,
            "historical_property_gate_receipt_id": historical_gate.receipt_id,
            "historical_property_gate_digest": historical_gate.digest,
            "property_manifest_id": manifest.manifest_id,
            "property_manifest_digest": manifest.digest,
            "current_validity_receipt_id": current_validity.receipt_id,
            "current_validity_digest": current_validity.digest,
            "live_property_gate_receipt_id": live_gate.receipt_id,
            "live_property_gate_digest": live_gate.digest,
            "patch_ref": base.patch_ref,
            "patch_digest": base.patch_digest,
            "current_source_revision": source_revision,
            "current": current,
            "reasons": list(normalized),
            "authority": "candidate_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringCurrentPropertyBoundReceipt(
            receipt_id=f"eng-current-property-{digest[:20]}",
            base_closure_id=base.receipt_id,
            base_closure_digest=base.digest,
            historical_property_gate_receipt_id=historical_gate.receipt_id,
            historical_property_gate_digest=historical_gate.digest,
            property_manifest_id=manifest.manifest_id,
            property_manifest_digest=manifest.digest,
            current_validity_receipt_id=current_validity.receipt_id,
            current_validity_digest=current_validity.digest,
            live_property_gate_receipt_id=live_gate.receipt_id,
            live_property_gate_digest=live_gate.digest,
            patch_ref=base.patch_ref,
            patch_digest=base.patch_digest,
            current_source_revision=source_revision,
            current=current,
            reasons=normalized,
            authority="candidate_only",
            digest=digest,
        )
        existing = self._receipts.get(row.receipt_id)
        if existing is not None and existing != row:
            raise ValueError("engineering current property validity receipt cannot be rebound")
        self._receipts[row.receipt_id] = row
        return existing or row

    def _validate_restored_semantics(
        self,
        row: EngineeringCurrentPropertyBoundReceipt,
    ) -> None:
        base = self.validity.closure.get(row.base_closure_id)
        historical_gate = self.property_gate.get_gate_receipt(
            row.historical_property_gate_receipt_id
        )
        manifest = self.property_gate.get_manifest(row.property_manifest_id)
        current_validity = self.validity.get(row.current_validity_receipt_id)
        live_gate = self._live_property_gate(historical_gate)

        if row.base_closure_digest != base.digest:
            raise ValueError("current property validity base closure lineage mismatch")
        if row.historical_property_gate_digest != historical_gate.digest:
            raise ValueError("current property validity historical property gate lineage mismatch")
        if (
            row.property_manifest_id != historical_gate.manifest_id
            or row.property_manifest_digest != manifest.digest
            or historical_gate.manifest_digest != manifest.digest
        ):
            raise ValueError("current property validity property manifest lineage mismatch")
        if row.current_validity_digest != current_validity.digest:
            raise ValueError("current property validity legacy validity lineage mismatch")
        if (
            current_validity.closure_receipt_id != base.receipt_id
            or current_validity.closure_digest != base.digest
            or current_validity.current_source_revision != row.current_source_revision
        ):
            raise ValueError("current property validity legacy current-view lineage mismatch")
        if (
            row.live_property_gate_receipt_id != live_gate.receipt_id
            or row.live_property_gate_digest != live_gate.digest
        ):
            raise ValueError("current property validity live property truth is stale")
        if row.patch_ref != base.patch_ref or row.patch_digest != base.patch_digest:
            raise ValueError("current property validity patch lineage mismatch")

        expected_reasons = self._base_reasons(
            base=base,
            historical_gate=historical_gate,
            manifest=manifest,
            current_validity=current_validity,
            live_gate=live_gate,
            current_source_revision=row.current_source_revision,
        )
        # Patch drift is represented canonically by the legacy current-validity
        # receipt.  Mirror the property-specific diagnostic if it was emitted
        # during live assessment so restore can reproduce the same truth value
        # without pretending to own or reconstruct the external patch object.
        mirrored = list(expected_reasons)
        if "patch_identity_changed" in current_validity.reasons:
            mirrored.append("current_property_patch_identity_mismatch")
        elif "patch_state_changed" in current_validity.reasons:
            mirrored.append("current_property_patch_state_mismatch")
        if "missing_current_patch_state" in current_validity.reasons:
            mirrored.append("missing_current_property_patch_state")
        expected_reasons = tuple(sorted(set(mirrored)))
        expected_current = (
            current_validity.current
            and historical_gate.ready
            and live_gate.ready
            and not expected_reasons
        )
        if row.reasons != expected_reasons or row.current != expected_current:
            raise ValueError("current property validity semantic truth mismatch")

    def to_state(self) -> dict[str, Any]:
        return {
            "component_id": COMPONENT_ID,
            "component_version": COMPONENT_VERSION,
            "receipts": [row.to_state() for row in self.receipts()],
        }

    @classmethod
    def from_state(
        cls,
        *,
        validity: EngineeringValidityEngine,
        property_gate: SoftwareEngineeringPropertyGate,
        state: Mapping[str, Any],
    ) -> "SoftwareEngineeringCurrentPropertyValidity":
        if _text(state["component_id"], field="current property validity component id") != COMPONENT_ID:
            raise ValueError("current property validity component id mismatch")
        if _text(
            state["component_version"], field="current property validity component version"
        ) != COMPONENT_VERSION:
            raise ValueError("current property validity component version mismatch")

        engine = cls(validity=validity, property_gate=property_gate)
        for value in state.get("receipts", ()):
            row = EngineeringCurrentPropertyBoundReceipt.from_state(value)
            engine._validate_restored_semantics(row)
            existing = engine._receipts.get(row.receipt_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound current property validity receipt")
            engine._receipts[row.receipt_id] = row
        return engine


__all__ = (
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "EngineeringCurrentPropertyBoundReceipt",
    "SoftwareEngineeringCurrentPropertyValidity",
)
