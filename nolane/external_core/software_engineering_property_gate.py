from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.software_engineering_property_evidence import (
    EngineeringClaimClass,
    EngineeringPropertyEvidenceLedger,
)


PROPERTY_GATE_VERSION = "0.1.0"


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


def _refs(values: Sequence[Any]) -> tuple[str, ...]:
    return tuple(sorted({_text(value, field="reference") for value in values}))


@dataclass(frozen=True, slots=True)
class EngineeringPropertyRequirement:
    """One semantic engineering property projected into F verification scope."""

    claim_id: str
    claim_class: EngineeringClaimClass
    property_ref: str

    def __post_init__(self) -> None:
        _text(self.claim_id, field="property requirement claim id")
        _text(self.property_ref, field="property requirement ref")

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.claim_id, self.claim_class.value, self.property_ref)

    def to_state(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_class": self.claim_class.value,
            "property_ref": self.property_ref,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringPropertyRequirement":
        return cls(
            claim_id=_text(state["claim_id"], field="property requirement claim id"),
            claim_class=EngineeringClaimClass(str(state["claim_class"])),
            property_ref=_text(state["property_ref"], field="property requirement ref"),
        )


@dataclass(frozen=True, slots=True)
class EngineeringPropertyRequirementManifest:
    manifest_id: str
    patch_ref: str
    patch_digest: str
    source_revision: str
    source_authority_ref: str
    requirements: tuple[EngineeringPropertyRequirement, ...]
    authority: str
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.manifest_id, "property manifest id"),
            (self.patch_ref, "patch ref"),
            (self.patch_digest, "patch digest"),
            (self.source_revision, "source revision"),
            (self.source_authority_ref, "property requirement source authority"),
            (self.digest, "property manifest digest"),
        ):
            _text(value, field=field)
        if not self.requirements:
            raise ValueError("property manifest requires at least one semantic property")
        keys = tuple(row.key for row in self.requirements)
        if len(keys) != len(set(keys)):
            raise ValueError("property manifest contains duplicate semantic requirements")
        if self.authority != "requirement_projection_only":
            raise ValueError("property manifest cannot own requirement/mutation/promotion authority")

    def payload(self) -> dict[str, Any]:
        return {
            "patch_ref": self.patch_ref,
            "patch_digest": self.patch_digest,
            "source_revision": self.source_revision,
            "source_authority_ref": self.source_authority_ref,
            "requirements": [row.to_state() for row in self.requirements],
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"manifest_id": self.manifest_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringPropertyRequirementManifest":
        requirements = tuple(
            sorted(
                (EngineeringPropertyRequirement.from_state(value) for value in state.get("requirements", ())),
                key=lambda row: row.key,
            )
        )
        row = cls(
            manifest_id=_text(state["manifest_id"], field="property manifest id"),
            patch_ref=_text(state["patch_ref"], field="patch ref"),
            patch_digest=_text(state["patch_digest"], field="patch digest"),
            source_revision=_text(state["source_revision"], field="source revision"),
            source_authority_ref=_text(
                state["source_authority_ref"], field="property requirement source authority"
            ),
            requirements=requirements,
            authority=_text(state["authority"], field="property manifest authority"),
            digest=_text(state["digest"], field="property manifest digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.manifest_id != f"eng-property-manifest-{expected[:20]}":
            raise ValueError("property manifest digest/id mismatch")
        return row


@dataclass(frozen=True, slots=True)
class EngineeringPropertyGateBinding:
    claim_id: str
    claim_class: EngineeringClaimClass
    property_ref: str
    obligation_id: str
    obligation_digest: str
    historical_closure_id: str
    historical_closure_digest: str
    live_closure_id: str
    live_closure_digest: str
    currently_closed: bool

    @property
    def requirement_key(self) -> tuple[str, str, str]:
        return (self.claim_id, self.claim_class.value, self.property_ref)

    def to_state(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_class": self.claim_class.value,
            "property_ref": self.property_ref,
            "obligation_id": self.obligation_id,
            "obligation_digest": self.obligation_digest,
            "historical_closure_id": self.historical_closure_id,
            "historical_closure_digest": self.historical_closure_digest,
            "live_closure_id": self.live_closure_id,
            "live_closure_digest": self.live_closure_digest,
            "currently_closed": self.currently_closed,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringPropertyGateBinding":
        return cls(
            claim_id=_text(state["claim_id"], field="property binding claim id"),
            claim_class=EngineeringClaimClass(str(state["claim_class"])),
            property_ref=_text(state["property_ref"], field="property binding ref"),
            obligation_id=_text(state["obligation_id"], field="property obligation id"),
            obligation_digest=_text(state["obligation_digest"], field="property obligation digest"),
            historical_closure_id=_text(
                state["historical_closure_id"], field="historical property closure id"
            ),
            historical_closure_digest=_text(
                state["historical_closure_digest"], field="historical property closure digest"
            ),
            live_closure_id=_text(state["live_closure_id"], field="live property closure id"),
            live_closure_digest=_text(
                state["live_closure_digest"], field="live property closure digest"
            ),
            currently_closed=bool(state["currently_closed"]),
        )


@dataclass(frozen=True, slots=True)
class EngineeringPropertyGateReceipt:
    receipt_id: str
    manifest_id: str
    manifest_digest: str
    patch_ref: str
    patch_digest: str
    source_revision: str
    bindings: tuple[EngineeringPropertyGateBinding, ...]
    ready: bool
    reasons: tuple[str, ...]
    authority: str
    digest: str

    def __post_init__(self) -> None:
        if self.authority != "candidate_only":
            raise ValueError("property gate cannot hold release/deployment authority")
        if self.ready and self.reasons:
            raise ValueError("ready property gate cannot contain blocking reasons")
        keys = tuple(row.requirement_key for row in self.bindings)
        if len(keys) != len(set(keys)):
            raise ValueError("property gate contains duplicate requirement bindings")

    def payload(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "manifest_digest": self.manifest_digest,
            "patch_ref": self.patch_ref,
            "patch_digest": self.patch_digest,
            "source_revision": self.source_revision,
            "bindings": [row.to_state() for row in self.bindings],
            "ready": self.ready,
            "reasons": list(self.reasons),
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringPropertyGateReceipt":
        bindings = tuple(
            sorted(
                (EngineeringPropertyGateBinding.from_state(value) for value in state.get("bindings", ())),
                key=lambda row: row.requirement_key,
            )
        )
        row = cls(
            receipt_id=_text(state["receipt_id"], field="property gate receipt id"),
            manifest_id=_text(state["manifest_id"], field="property manifest id"),
            manifest_digest=_text(state["manifest_digest"], field="property manifest digest"),
            patch_ref=_text(state["patch_ref"], field="patch ref"),
            patch_digest=_text(state["patch_digest"], field="patch digest"),
            source_revision=_text(state["source_revision"], field="source revision"),
            bindings=bindings,
            ready=bool(state["ready"]),
            reasons=tuple(sorted({_text(value, field="property gate reason") for value in state.get("reasons", ())})),
            authority=_text(state["authority"], field="property gate authority"),
            digest=_text(state["digest"], field="property gate digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != f"eng-property-gate-{expected[:20]}":
            raise ValueError("property gate receipt digest/id mismatch")
        return row


@dataclass(frozen=True, slots=True)
class EngineeringPropertyBoundClosureReceipt:
    receipt_id: str
    base_closure_id: str
    base_closure_digest: str
    property_gate_receipt_id: str
    property_gate_digest: str
    patch_ref: str
    patch_digest: str
    source_revision: str
    ready: bool
    reasons: tuple[str, ...]
    authority: str
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.receipt_id, "property-bound terminal closure id"),
            (self.base_closure_id, "base engineering closure id"),
            (self.base_closure_digest, "base engineering closure digest"),
            (self.property_gate_receipt_id, "property gate receipt id"),
            (self.property_gate_digest, "property gate digest"),
            (self.patch_ref, "patch ref"),
            (self.patch_digest, "patch digest"),
            (self.source_revision, "source revision"),
            (self.digest, "property-bound terminal closure digest"),
        ):
            _text(value, field=field)
        if self.authority != "candidate_only":
            raise ValueError("property-bound closure cannot hold release/deployment authority")
        if self.ready and self.reasons:
            raise ValueError("ready property-bound closure cannot contain blocking reasons")

    def payload(self) -> dict[str, Any]:
        return {
            "base_closure_id": self.base_closure_id,
            "base_closure_digest": self.base_closure_digest,
            "property_gate_receipt_id": self.property_gate_receipt_id,
            "property_gate_digest": self.property_gate_digest,
            "patch_ref": self.patch_ref,
            "patch_digest": self.patch_digest,
            "source_revision": self.source_revision,
            "ready": self.ready,
            "reasons": list(self.reasons),
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringPropertyBoundClosureReceipt":
        row = cls(
            receipt_id=_text(state["receipt_id"], field="property-bound terminal closure id"),
            base_closure_id=_text(state["base_closure_id"], field="base engineering closure id"),
            base_closure_digest=_text(
                state["base_closure_digest"], field="base engineering closure digest"
            ),
            property_gate_receipt_id=_text(
                state["property_gate_receipt_id"], field="property gate receipt id"
            ),
            property_gate_digest=_text(state["property_gate_digest"], field="property gate digest"),
            patch_ref=_text(state["patch_ref"], field="patch ref"),
            patch_digest=_text(state["patch_digest"], field="patch digest"),
            source_revision=_text(state["source_revision"], field="source revision"),
            ready=bool(state["ready"]),
            reasons=tuple(sorted({_text(value, field="terminal closure reason") for value in state.get("reasons", ())})),
            authority=_text(state["authority"], field="property-bound closure authority"),
            digest=_text(state["digest"], field="property-bound terminal closure digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != f"eng-property-bound-{expected[:20]}":
            raise ValueError("property-bound terminal closure digest/id mismatch")
        return row


class SoftwareEngineeringPropertyGate:
    """Complete-set semantic property gate layered above historical F receipts.

    The gate is a monotonic extension. It does not rewrite CodingReadiness,
    DebugResolution, UIReadiness, or EngineeringClosure receipt identities.
    Instead it projects a complete required-property manifest, re-evaluates
    every supplied historical property closure against live evidence, and then
    binds that result to the legacy cross-surface closure. All positive output
    remains candidate-only.
    """

    def __init__(self, *, property_evidence: EngineeringPropertyEvidenceLedger) -> None:
        self.property_evidence = property_evidence
        self._manifests: dict[str, EngineeringPropertyRequirementManifest] = {}
        self._gate_receipts: dict[str, EngineeringPropertyGateReceipt] = {}
        self._terminal_closures: dict[str, EngineeringPropertyBoundClosureReceipt] = {}

    def manifests(self) -> tuple[EngineeringPropertyRequirementManifest, ...]:
        return tuple(self._manifests[key] for key in sorted(self._manifests))

    def gate_receipts(self) -> tuple[EngineeringPropertyGateReceipt, ...]:
        return tuple(self._gate_receipts[key] for key in sorted(self._gate_receipts))

    def terminal_closures(self) -> tuple[EngineeringPropertyBoundClosureReceipt, ...]:
        return tuple(self._terminal_closures[key] for key in sorted(self._terminal_closures))

    def get_manifest(self, manifest_id: str) -> EngineeringPropertyRequirementManifest:
        try:
            return self._manifests[str(manifest_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering property manifest: {manifest_id}") from exc

    def get_gate_receipt(self, receipt_id: str) -> EngineeringPropertyGateReceipt:
        try:
            return self._gate_receipts[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering property gate receipt: {receipt_id}") from exc

    def get_terminal_closure(self, receipt_id: str) -> EngineeringPropertyBoundClosureReceipt:
        try:
            return self._terminal_closures[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f"unknown property-bound terminal closure: {receipt_id}") from exc

    def register_manifest(
        self,
        *,
        patch_ref: str,
        patch_digest: str,
        source_revision: str,
        source_authority_ref: str,
        requirements: tuple[EngineeringPropertyRequirement, ...],
    ) -> EngineeringPropertyRequirementManifest:
        rows = tuple(sorted((EngineeringPropertyRequirement(row.claim_id, EngineeringClaimClass(row.claim_class), row.property_ref) for row in requirements), key=lambda row: row.key))
        if not rows:
            raise ValueError("property manifest requires at least one semantic property")
        payload = {
            "patch_ref": _text(patch_ref, field="patch ref"),
            "patch_digest": _text(patch_digest, field="patch digest"),
            "source_revision": _text(source_revision, field="source revision"),
            "source_authority_ref": _text(
                source_authority_ref, field="property requirement source authority"
            ),
            "requirements": [row.to_state() for row in rows],
            "authority": "requirement_projection_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringPropertyRequirementManifest(
            manifest_id=f"eng-property-manifest-{digest[:20]}",
            patch_ref=payload["patch_ref"],
            patch_digest=payload["patch_digest"],
            source_revision=payload["source_revision"],
            source_authority_ref=payload["source_authority_ref"],
            requirements=rows,
            authority="requirement_projection_only",
            digest=digest,
        )
        existing = self._manifests.get(row.manifest_id)
        if existing is not None and existing != row:
            raise ValueError("property manifest id cannot be rebound")
        self._manifests[row.manifest_id] = row
        return existing or row

    def assess(
        self,
        manifest_id: str,
        *,
        property_bindings: tuple[tuple[str, str], ...],
    ) -> EngineeringPropertyGateReceipt:
        manifest = self.get_manifest(manifest_id)
        required = {row.key: row for row in manifest.requirements}
        seen: set[tuple[str, str, str]] = set()
        bindings: list[EngineeringPropertyGateBinding] = []
        reasons: list[str] = []

        for obligation_id, closure_receipt_id in property_bindings:
            obligation = self.property_evidence.get_obligation(obligation_id)
            historical = self.property_evidence.get_receipt(closure_receipt_id)
            key = (obligation.claim_id, obligation.claim_class.value, obligation.property_ref)
            if key not in required:
                reasons.append(
                    "unexpected_or_mismatched_property:"
                    + ":".join(key)
                )
                continue
            if key in seen:
                reasons.append("duplicate_property_binding:" + ":".join(key))
                continue
            seen.add(key)

            if (
                obligation.subject_ref != manifest.patch_ref
                or obligation.subject_digest != manifest.patch_digest
                or obligation.source_revision != manifest.source_revision
            ):
                reasons.append("property_patch_lineage_mismatch:" + ":".join(key))
                continue
            if (
                historical.obligation_id != obligation.obligation_id
                or historical.obligation_digest != obligation.digest
            ):
                reasons.append("property_closure_obligation_mismatch:" + ":".join(key))
                continue

            live = self.property_evidence.assess(
                obligation.obligation_id,
                witness_ids=historical.witness_ids,
            )
            if not live.ready:
                reasons.append("property_not_currently_closed:" + ":".join(key))
            bindings.append(
                EngineeringPropertyGateBinding(
                    claim_id=obligation.claim_id,
                    claim_class=obligation.claim_class,
                    property_ref=obligation.property_ref,
                    obligation_id=obligation.obligation_id,
                    obligation_digest=obligation.digest,
                    historical_closure_id=historical.receipt_id,
                    historical_closure_digest=historical.digest,
                    live_closure_id=live.receipt_id,
                    live_closure_digest=live.digest,
                    currently_closed=live.ready,
                )
            )

        for key in sorted(set(required) - seen):
            reasons.append("missing_required_property:" + ":".join(key))

        bindings_tuple = tuple(sorted(bindings, key=lambda row: row.requirement_key))
        normalized = tuple(sorted(set(reasons)))
        ready = not normalized and len(bindings_tuple) == len(manifest.requirements)
        payload = {
            "manifest_id": manifest.manifest_id,
            "manifest_digest": manifest.digest,
            "patch_ref": manifest.patch_ref,
            "patch_digest": manifest.patch_digest,
            "source_revision": manifest.source_revision,
            "bindings": [row.to_state() for row in bindings_tuple],
            "ready": ready,
            "reasons": list(normalized),
            "authority": "candidate_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringPropertyGateReceipt(
            receipt_id=f"eng-property-gate-{digest[:20]}",
            manifest_id=manifest.manifest_id,
            manifest_digest=manifest.digest,
            patch_ref=manifest.patch_ref,
            patch_digest=manifest.patch_digest,
            source_revision=manifest.source_revision,
            bindings=bindings_tuple,
            ready=ready,
            reasons=normalized,
            authority="candidate_only",
            digest=digest,
        )
        existing = self._gate_receipts.get(row.receipt_id)
        if existing is not None and existing != row:
            raise ValueError("property gate receipt id cannot be rebound")
        self._gate_receipts[row.receipt_id] = row
        return existing or row

    def bind_terminal_closure(
        self,
        *,
        base_closure: Any,
        property_gate_receipt_id: str,
    ) -> EngineeringPropertyBoundClosureReceipt:
        gate = self.get_gate_receipt(property_gate_receipt_id)
        base_id = _text(getattr(base_closure, "receipt_id"), field="base engineering closure id")
        base_digest = _text(getattr(base_closure, "digest"), field="base engineering closure digest")
        base_patch_ref = _text(getattr(base_closure, "patch_ref"), field="base patch ref")
        base_patch_digest = _text(getattr(base_closure, "patch_digest"), field="base patch digest")
        base_revision = _text(getattr(base_closure, "source_revision"), field="base source revision")
        reasons: list[str] = []
        if not bool(getattr(base_closure, "ready", False)):
            reasons.append("base_engineering_closure_not_ready")
        if (
            base_patch_ref != gate.patch_ref
            or base_patch_digest != gate.patch_digest
            or base_revision != gate.source_revision
        ):
            reasons.append("base_property_revision_mismatch")
        if not gate.ready:
            reasons.append("property_gate_not_ready")
        base_authority = getattr(base_closure, "authority", None)
        if base_authority is not None and str(base_authority) != "candidate_only":
            reasons.append("base_closure_authority_not_candidate_only")

        normalized = tuple(sorted(set(reasons)))
        ready = not normalized
        payload = {
            "base_closure_id": base_id,
            "base_closure_digest": base_digest,
            "property_gate_receipt_id": gate.receipt_id,
            "property_gate_digest": gate.digest,
            "patch_ref": gate.patch_ref,
            "patch_digest": gate.patch_digest,
            "source_revision": gate.source_revision,
            "ready": ready,
            "reasons": list(normalized),
            "authority": "candidate_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringPropertyBoundClosureReceipt(
            receipt_id=f"eng-property-bound-{digest[:20]}",
            base_closure_id=base_id,
            base_closure_digest=base_digest,
            property_gate_receipt_id=gate.receipt_id,
            property_gate_digest=gate.digest,
            patch_ref=gate.patch_ref,
            patch_digest=gate.patch_digest,
            source_revision=gate.source_revision,
            ready=ready,
            reasons=normalized,
            authority="candidate_only",
            digest=digest,
        )
        existing = self._terminal_closures.get(row.receipt_id)
        if existing is not None and existing != row:
            raise ValueError("property-bound terminal closure id cannot be rebound")
        self._terminal_closures[row.receipt_id] = row
        return existing or row

    def to_state(self) -> dict[str, Any]:
        return {
            "version": PROPERTY_GATE_VERSION,
            "manifests": [row.to_state() for row in self.manifests()],
            "gate_receipts": [row.to_state() for row in self.gate_receipts()],
            "terminal_closures": [row.to_state() for row in self.terminal_closures()],
        }

    @classmethod
    def from_state(
        cls,
        *,
        property_evidence: EngineeringPropertyEvidenceLedger,
        state: Mapping[str, Any],
    ) -> "SoftwareEngineeringPropertyGate":
        version = str(state.get("version", PROPERTY_GATE_VERSION))
        if version != PROPERTY_GATE_VERSION:
            raise ValueError("unsupported engineering property gate snapshot version")
        gate = cls(property_evidence=property_evidence)

        for value in state.get("manifests", ()):
            row = EngineeringPropertyRequirementManifest.from_state(value)
            existing = gate._manifests.get(row.manifest_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound property manifest")
            gate._manifests[row.manifest_id] = row

        for value in state.get("gate_receipts", ()):
            row = EngineeringPropertyGateReceipt.from_state(value)
            manifest = gate.get_manifest(row.manifest_id)
            if (
                row.manifest_digest != manifest.digest
                or row.patch_ref != manifest.patch_ref
                or row.patch_digest != manifest.patch_digest
                or row.source_revision != manifest.source_revision
            ):
                raise ValueError("property gate manifest lineage mismatch")
            requirement_keys = {requirement.key for requirement in manifest.requirements}
            for binding in row.bindings:
                if binding.requirement_key not in requirement_keys:
                    raise ValueError("property gate contains binding outside manifest")
                obligation = property_evidence.get_obligation(binding.obligation_id)
                historical = property_evidence.get_receipt(binding.historical_closure_id)
                live = property_evidence.get_receipt(binding.live_closure_id)
                if obligation.digest != binding.obligation_digest:
                    raise ValueError("property gate obligation digest mismatch")
                if historical.digest != binding.historical_closure_digest:
                    raise ValueError("property gate historical closure digest mismatch")
                if live.digest != binding.live_closure_digest or live.ready != binding.currently_closed:
                    raise ValueError("property gate live closure lineage mismatch")
            existing = gate._gate_receipts.get(row.receipt_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound property gate receipt")
            gate._gate_receipts[row.receipt_id] = row

        for value in state.get("terminal_closures", ()):
            row = EngineeringPropertyBoundClosureReceipt.from_state(value)
            property_gate = gate.get_gate_receipt(row.property_gate_receipt_id)
            if (
                row.property_gate_digest != property_gate.digest
                or row.patch_ref != property_gate.patch_ref
                or row.patch_digest != property_gate.patch_digest
                or row.source_revision != property_gate.source_revision
            ):
                raise ValueError("property-bound terminal closure gate lineage mismatch")
            existing = gate._terminal_closures.get(row.receipt_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound property-bound terminal closure")
            gate._terminal_closures[row.receipt_id] = row
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
