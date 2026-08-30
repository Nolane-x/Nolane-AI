from __future__ import annotations

from typing import Any

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.software_engineering import EngineeringPhase
from nolane.external_core.software_engineering_policy import (
    EngineeringChangeManifest,
    EngineeringGateReceipt,
    GovernedEngineeringGate,
)


PARENT_PROTOCOL_ID = "external.software_engineering.policy"
PROTOCOL_ID = "external.software_engineering.historical_authorization_gate"
PROTOCOL_VERSION = "0.1.0"


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


class HistoricalAuthorizationEngineeringGate(GovernedEngineeringGate):
    """Policy gate that treats claim binding as historical mutation proof.

    Active claims are required at the pre-apply mutation boundary. After the
    patch has been applied, the immutable claim snapshot proves that mutation
    was authorized at that time; a normal lease release does not retroactively
    invalidate the engineering candidate. Technical freshness remains governed
    by source, patch and evidence lineage.
    """

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
            if not self.claim_bindings.historically_covers_patch(binding.binding_id, patch):
                reasons.append("historical_claim_scope_does_not_cover_patch")

        if not all(hasattr(patch, name) for name in (
            "producer_agent_id", "task_id", "touched_files", "touched_symbols"
        )):
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


__all__ = ("HistoricalAuthorizationEngineeringGate",)
