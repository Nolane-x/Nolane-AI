from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding_claims import CodeClaimLedger
from nolane.external_core.software_engineering import (
    EngineeringEvidenceKind,
    EngineeringEvidenceLedger,
    EngineeringPhase,
    PatchTransactionLedger,
    SoftwareEngineeringClosureEngine,
)
from nolane.external_core.software_engineering_validity import EngineeringClaimBindingLedger


COMPONENT_ID = "external.software_engineering.policy"
COMPONENT_VERSION = "0.2.0"


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


def _refs(values: Sequence[Any]) -> tuple[str, ...]:
    return tuple(sorted({_text(value, field="reference") for value in values}))


class EngineeringRiskClass(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


_RISK_RANK = {
    EngineeringRiskClass.LOW: 0,
    EngineeringRiskClass.MODERATE: 1,
    EngineeringRiskClass.HIGH: 2,
    EngineeringRiskClass.CRITICAL: 3,
}


def _max_risk(*values: EngineeringRiskClass) -> EngineeringRiskClass:
    return max((EngineeringRiskClass(value) for value in values), key=_RISK_RANK.__getitem__)


def _surface_text(patch: Any) -> str:
    parts = [
        *(str(value).lower() for value in getattr(patch, "touched_files", ())),
        *(str(value).lower() for value in getattr(patch, "touched_symbols", ())),
    ]
    return " ".join(parts)


def _contains_any(text: str, values: tuple[str, ...]) -> bool:
    return any(value in text for value in values)


@dataclass(frozen=True, slots=True)
class EngineeringChangeManifest:
    manifest_id: str
    patch_ref: str
    patch_digest: str
    source_revision: str
    touched_files: tuple[str, ...]
    touched_symbols: tuple[str, ...]
    dependency_refs: tuple[str, ...]
    impacted_component_refs: tuple[str, ...]
    risk: EngineeringRiskClass
    ui_sensitive: bool
    security_sensitive: bool
    performance_sensitive: bool
    debug_origin: bool
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "patch_ref": self.patch_ref,
            "patch_digest": self.patch_digest,
            "source_revision": self.source_revision,
            "touched_files": list(self.touched_files),
            "touched_symbols": list(self.touched_symbols),
            "dependency_refs": list(self.dependency_refs),
            "impacted_component_refs": list(self.impacted_component_refs),
            "risk": self.risk.value,
            "ui_sensitive": self.ui_sensitive,
            "security_sensitive": self.security_sensitive,
            "performance_sensitive": self.performance_sensitive,
            "debug_origin": self.debug_origin,
        }

    def to_state(self) -> dict[str, Any]:
        return {"manifest_id": self.manifest_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringChangeManifest":
        row = cls(
            manifest_id=_text(state["manifest_id"], field="manifest id"),
            patch_ref=_text(state["patch_ref"], field="patch ref"),
            patch_digest=_text(state["patch_digest"], field="patch digest"),
            source_revision=_text(state["source_revision"], field="source revision"),
            touched_files=_refs(tuple(state.get("touched_files", ()))),
            touched_symbols=_refs(tuple(state.get("touched_symbols", ()))),
            dependency_refs=_refs(tuple(state.get("dependency_refs", ()))),
            impacted_component_refs=_refs(tuple(state.get("impacted_component_refs", ()))),
            risk=EngineeringRiskClass(str(state["risk"])),
            ui_sensitive=bool(state["ui_sensitive"]),
            security_sensitive=bool(state["security_sensitive"]),
            performance_sensitive=bool(state["performance_sensitive"]),
            debug_origin=bool(state["debug_origin"]),
            digest=_text(state["digest"], field="manifest digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.manifest_id != f"eng-manifest-{expected[:20]}":
            raise ValueError("engineering manifest digest/id mismatch")
        return row


class EngineeringChangeManifestLedger:
    """Content-addressed blast-radius and risk manifests for coding patches."""

    def __init__(self) -> None:
        self._manifests: dict[str, EngineeringChangeManifest] = {}

    def manifests(self) -> tuple[EngineeringChangeManifest, ...]:
        return tuple(self._manifests[key] for key in sorted(self._manifests))

    def get(self, manifest_id: str) -> EngineeringChangeManifest:
        try:
            return self._manifests[str(manifest_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering change manifest: {manifest_id}") from exc

    @staticmethod
    def _inferred_risk(
        *,
        patch: Any,
        ui_sensitive: bool,
        security_sensitive: bool,
        performance_sensitive: bool,
        debug_origin: bool,
    ) -> EngineeringRiskClass:
        scope_size = len(tuple(getattr(patch, "touched_files", ()))) + len(tuple(getattr(patch, "touched_symbols", ())))
        risk = EngineeringRiskClass.LOW
        if scope_size >= 3 or ui_sensitive or performance_sensitive or debug_origin:
            risk = EngineeringRiskClass.MODERATE
        if scope_size >= 8 or security_sensitive:
            risk = EngineeringRiskClass.HIGH
        return risk

    def register(
        self,
        *,
        patch: Any,
        source_revision: str,
        dependency_refs: tuple[str, ...] = (),
        impacted_component_refs: tuple[str, ...] = (),
        declared_risk: EngineeringRiskClass = EngineeringRiskClass.LOW,
        ui_sensitive: bool = False,
        security_sensitive: bool = False,
        performance_sensitive: bool = False,
        debug_origin: bool = False,
    ) -> EngineeringChangeManifest:
        if not hasattr(patch, "to_state"):
            raise TypeError("engineering manifest requires canonical patch state")
        patch_ref = _text(getattr(patch, "patch_id"), field="patch id")
        patch_digest = canonical_digest(patch.to_state())
        touched_files = _refs(tuple(getattr(patch, "touched_files", ())))
        touched_symbols = _refs(tuple(getattr(patch, "touched_symbols", ())))
        if not touched_files and not touched_symbols:
            raise ValueError("engineering manifest requires touched source scope")

        surface = _surface_text(patch)
        inferred_ui = _contains_any(
            surface,
            (
                ".tsx", ".jsx", ".css", ".scss", ".html", ".vue", ".svelte",
                "frontend", "ui/", "view", "component", "screen", "layout",
            ),
        )
        inferred_security = _contains_any(
            surface,
            (
                "auth", "security", "permission", "authorize", "crypto", "token",
                "secret", "identity", "credential", "access_control", "accesscontrol",
            ),
        )
        inferred_performance = _contains_any(
            surface,
            (
                "performance", "benchmark", "latency", "throughput", "scheduler",
                "cache", "concurrency", "hot_path", "hotpath",
            ),
        )
        ui_flag = bool(ui_sensitive or inferred_ui)
        security_flag = bool(security_sensitive or inferred_security)
        performance_flag = bool(performance_sensitive or inferred_performance)
        debug_flag = bool(debug_origin)
        risk = _max_risk(
            EngineeringRiskClass(declared_risk),
            self._inferred_risk(
                patch=patch,
                ui_sensitive=ui_flag,
                security_sensitive=security_flag,
                performance_sensitive=performance_flag,
                debug_origin=debug_flag,
            ),
        )

        payload = {
            "patch_ref": patch_ref,
            "patch_digest": patch_digest,
            "source_revision": _text(source_revision, field="source revision"),
            "touched_files": list(touched_files),
            "touched_symbols": list(touched_symbols),
            "dependency_refs": list(_refs(dependency_refs)),
            "impacted_component_refs": list(_refs(impacted_component_refs)),
            "risk": risk.value,
            "ui_sensitive": ui_flag,
            "security_sensitive": security_flag,
            "performance_sensitive": performance_flag,
            "debug_origin": debug_flag,
        }
        digest = canonical_digest(payload)
        row = EngineeringChangeManifest(
            manifest_id=f"eng-manifest-{digest[:20]}",
            patch_ref=patch_ref,
            patch_digest=patch_digest,
            source_revision=payload["source_revision"],
            touched_files=touched_files,
            touched_symbols=touched_symbols,
            dependency_refs=tuple(payload["dependency_refs"]),
            impacted_component_refs=tuple(payload["impacted_component_refs"]),
            risk=risk,
            ui_sensitive=ui_flag,
            security_sensitive=security_flag,
            performance_sensitive=performance_flag,
            debug_origin=debug_flag,
            digest=digest,
        )
        existing = self._manifests.get(row.manifest_id)
        if existing is not None and existing != row:
            raise ValueError("engineering manifest id cannot be rebound")
        self._manifests[row.manifest_id] = row
        return existing or row

    def to_state(self) -> dict[str, Any]:
        return {"manifests": [row.to_state() for row in self.manifests()]}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringChangeManifestLedger":
        ledger = cls()
        for value in state.get("manifests", ()):
            row = EngineeringChangeManifest.from_state(value)
            existing = ledger._manifests.get(row.manifest_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound engineering manifest")
            ledger._manifests[row.manifest_id] = row
        return ledger


@dataclass(frozen=True, slots=True)
class EngineeringVerificationRequirements:
    requirement_id: str
    policy_id: str
    policy_digest: str
    manifest_id: str
    manifest_digest: str
    attestation_kinds: tuple[EngineeringEvidenceKind, ...]
    require_debug: bool
    require_ui: bool
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_digest": self.policy_digest,
            "manifest_id": self.manifest_id,
            "manifest_digest": self.manifest_digest,
            "attestation_kinds": [kind.value for kind in self.attestation_kinds],
            "require_debug": self.require_debug,
            "require_ui": self.require_ui,
        }


class EngineeringVerificationPolicy:
    """Deterministically derives minimum verification from patch risk/surfaces."""

    def __init__(self) -> None:
        self.policy_id = "engineering-verification-policy-v1"
        self.policy_digest = canonical_digest({
            "policy_id": self.policy_id,
            "base": ["compile", "test", "static"],
            "ui": ["visual", "responsive", "accessibility", "interaction"],
            "security": ["security"],
            "performance": ["performance"],
            "debug": ["reproduction", "root_cause"],
            "high_or_critical": ["review"],
        })

    def requirements(self, manifest: EngineeringChangeManifest) -> EngineeringVerificationRequirements:
        kinds = {
            EngineeringEvidenceKind.COMPILE,
            EngineeringEvidenceKind.TEST,
            EngineeringEvidenceKind.STATIC,
        }
        if manifest.ui_sensitive:
            kinds.update({
                EngineeringEvidenceKind.VISUAL,
                EngineeringEvidenceKind.RESPONSIVE,
                EngineeringEvidenceKind.ACCESSIBILITY,
                EngineeringEvidenceKind.INTERACTION,
            })
        if manifest.security_sensitive:
            kinds.add(EngineeringEvidenceKind.SECURITY)
        if manifest.performance_sensitive:
            kinds.add(EngineeringEvidenceKind.PERFORMANCE)
        if manifest.debug_origin:
            kinds.update({EngineeringEvidenceKind.REPRODUCTION, EngineeringEvidenceKind.ROOT_CAUSE})
        if _RISK_RANK[manifest.risk] >= _RISK_RANK[EngineeringRiskClass.HIGH]:
            kinds.add(EngineeringEvidenceKind.REVIEW)
        ordered = tuple(sorted(kinds, key=lambda kind: kind.value))
        payload = {
            "policy_id": self.policy_id,
            "policy_digest": self.policy_digest,
            "manifest_id": manifest.manifest_id,
            "manifest_digest": manifest.digest,
            "attestation_kinds": [kind.value for kind in ordered],
            "require_debug": manifest.debug_origin,
            "require_ui": manifest.ui_sensitive,
        }
        digest = canonical_digest(payload)
        return EngineeringVerificationRequirements(
            requirement_id=f"eng-requirements-{digest[:20]}",
            policy_id=self.policy_id,
            policy_digest=self.policy_digest,
            manifest_id=manifest.manifest_id,
            manifest_digest=manifest.digest,
            attestation_kinds=ordered,
            require_debug=manifest.debug_origin,
            require_ui=manifest.ui_sensitive,
            digest=digest,
        )


@dataclass(frozen=True, slots=True)
class EngineeringGateReceipt:
    receipt_id: str
    manifest_id: str
    manifest_digest: str
    requirement_id: str
    requirement_digest: str
    claim_binding_id: str | None
    claim_binding_digest: str | None
    closure_receipt_id: str | None
    closure_digest: str | None
    required_attestation_kinds: tuple[str, ...]
    require_debug: bool
    require_ui: bool
    ready: bool
    reasons: tuple[str, ...]
    authority: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "manifest_digest": self.manifest_digest,
            "requirement_id": self.requirement_id,
            "requirement_digest": self.requirement_digest,
            "claim_binding_id": self.claim_binding_id,
            "claim_binding_digest": self.claim_binding_digest,
            "closure_receipt_id": self.closure_receipt_id,
            "closure_digest": self.closure_digest,
            "required_attestation_kinds": list(self.required_attestation_kinds),
            "require_debug": self.require_debug,
            "require_ui": self.require_ui,
            "ready": self.ready,
            "reasons": list(self.reasons),
            "authority": self.authority,
        }


class GovernedEngineeringGate:
    """Canonical v0.2 entry gate for policy-derived engineering closure.

    The caller cannot provide or weaken the required evidence family. Required
    evidence is derived from the content-addressed change manifest and policy.
    """

    def __init__(
        self,
        *,
        evidence: EngineeringEvidenceLedger,
        transactions: PatchTransactionLedger,
        closure: SoftwareEngineeringClosureEngine,
        claims: CodeClaimLedger,
        claim_bindings: EngineeringClaimBindingLedger,
        policy: EngineeringVerificationPolicy,
    ) -> None:
        self.evidence = evidence
        self.transactions = transactions
        self.closure = closure
        self.claims = claims
        self.claim_bindings = claim_bindings
        self.policy = policy
        self._receipts: dict[str, EngineeringGateReceipt] = {}

    def receipts(self) -> tuple[EngineeringGateReceipt, ...]:
        return tuple(self._receipts[key] for key in sorted(self._receipts))

    def get(self, receipt_id: str) -> EngineeringGateReceipt:
        try:
            return self._receipts[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering gate receipt: {receipt_id}") from exc

    def assess(
        self,
        *,
        manifest: EngineeringChangeManifest,
        patch: Any,
        coding_readiness: Any,
        transaction_id: str,
        current_source_revision: str,
        attestation_ids: tuple[str, ...],
        debug_resolution: Any | None = None,
        ui_readiness: Any | None = None,
    ) -> EngineeringGateReceipt:
        tx = self.transactions.get(transaction_id)
        requirements = self.policy.requirements(manifest)
        current_source = _text(current_source_revision, field="current source revision")
        reasons: list[str] = []

        if not hasattr(patch, "to_state"):
            reasons.append("missing_canonical_patch_state")
            patch_digest = "unavailable"
        else:
            patch_digest = canonical_digest(patch.to_state())
        patch_ref = str(getattr(patch, "patch_id", ""))
        if patch_ref != manifest.patch_ref or patch_digest != manifest.patch_digest:
            reasons.append("manifest_patch_lineage_mismatch")
        if current_source != manifest.source_revision or tx.source_revision != manifest.source_revision:
            reasons.append("manifest_source_revision_mismatch")
        if tx.patch_ref != manifest.patch_ref or tx.patch_digest != manifest.patch_digest:
            reasons.append("manifest_transaction_lineage_mismatch")
        if tx.phase is not EngineeringPhase.POSTCONDITIONS_VERIFIED:
            reasons.append("transaction_not_ready_for_governed_closure")

        binding = self.claim_bindings.for_transaction(tx.transaction_id)
        binding_id: str | None = None
        binding_digest: str | None = None
        if binding is None:
            reasons.append("missing_claim_state_binding")
        else:
            binding_id = binding.binding_id
            binding_digest = binding.digest
            reasons.extend(self.claim_bindings.current_reasons(binding.binding_id))

        if all(hasattr(patch, name) for name in (
            "producer_agent_id", "task_id", "touched_files", "touched_symbols"
        )):
            if not self.claims.covers(
                agent_id=str(patch.producer_agent_id),
                task_id=str(patch.task_id),
                file_paths=tuple(patch.touched_files),
                symbol_ids=tuple(patch.touched_symbols),
            ):
                reasons.append("claim_scope_does_not_cover_patch")
        else:
            reasons.append("patch_scope_unavailable")

        closure_receipt_id: str | None = None
        closure_digest: str | None = None
        inner = None
        if not reasons:
            inner = self.closure.assess(
                patch=patch,
                coding_readiness=coding_readiness,
                transaction_id=tx.transaction_id,
                current_source_revision=current_source,
                required_attestation_kinds=requirements.attestation_kinds,
                attestation_ids=attestation_ids,
                require_debug=requirements.require_debug,
                debug_resolution=debug_resolution,
                require_ui=requirements.require_ui,
                ui_readiness=ui_readiness,
            )
            closure_receipt_id = inner.receipt_id
            closure_digest = inner.digest
            if not inner.ready:
                reasons.extend(inner.reasons)

        normalized_reasons = tuple(sorted(set(reasons)))
        ready = inner is not None and inner.ready and not normalized_reasons
        required_values = tuple(sorted(kind.value for kind in requirements.attestation_kinds))
        payload = {
            "manifest_id": manifest.manifest_id,
            "manifest_digest": manifest.digest,
            "requirement_id": requirements.requirement_id,
            "requirement_digest": requirements.digest,
            "claim_binding_id": binding_id,
            "claim_binding_digest": binding_digest,
            "closure_receipt_id": closure_receipt_id,
            "closure_digest": closure_digest,
            "required_attestation_kinds": list(required_values),
            "require_debug": requirements.require_debug,
            "require_ui": requirements.require_ui,
            "ready": ready,
            "reasons": list(normalized_reasons),
            "authority": "candidate_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringGateReceipt(
            receipt_id=f"eng-gate-{digest[:20]}",
            manifest_id=manifest.manifest_id,
            manifest_digest=manifest.digest,
            requirement_id=requirements.requirement_id,
            requirement_digest=requirements.digest,
            claim_binding_id=binding_id,
            claim_binding_digest=binding_digest,
            closure_receipt_id=closure_receipt_id,
            closure_digest=closure_digest,
            required_attestation_kinds=required_values,
            require_debug=requirements.require_debug,
            require_ui=requirements.require_ui,
            ready=ready,
            reasons=normalized_reasons,
            authority="candidate_only",
            digest=digest,
        )
        existing = self._receipts.get(row.receipt_id)
        if existing is not None and existing != row:
            raise ValueError("engineering gate receipt cannot be rebound")
        self._receipts[row.receipt_id] = row
        return existing or row


__all__ = (
    "EngineeringRiskClass",
    "EngineeringChangeManifest",
    "EngineeringChangeManifestLedger",
    "EngineeringVerificationRequirements",
    "EngineeringVerificationPolicy",
    "EngineeringGateReceipt",
    "GovernedEngineeringGate",
)
