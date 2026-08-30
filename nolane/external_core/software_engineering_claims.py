from __future__ import annotations

from typing import Any, Mapping

from nolane.external_core.coding_claims import CodeClaimLedger
from nolane.external_core.software_engineering import PatchTransactionLedger
from nolane.external_core.software_engineering_validity import EngineeringClaimBindingLedger


PARENT_COMPONENT_ID = "external.coding.claims"
PROTOCOL_ID = "external.software_engineering.claim_identity_anchor"
PROTOCOL_VERSION = "0.1.0"


class AnchoredEngineeringClaimBindingLedger(EngineeringClaimBindingLedger):
    """Historical F bindings whose claim identities remain canonical-anchored.

    Claim state is allowed to change after apply (for example ACTIVE -> RELEASED),
    but the identity itself must exist in the canonical CodeClaimLedger supplied
    outside the F snapshot. Local digest recomputation cannot manufacture a new
    claim identity.
    """

    @classmethod
    def from_state(
        cls,
        *,
        transactions: PatchTransactionLedger,
        claims: CodeClaimLedger,
        state: Mapping[str, Any],
    ) -> "AnchoredEngineeringClaimBindingLedger":
        ledger = super().from_state(
            transactions=transactions,
            claims=claims,
            state=state,
        )
        for binding in ledger.bindings():
            for snapshot in binding.claim_snapshots:
                claims.get(snapshot.claim_id)
        return ledger


__all__ = ("AnchoredEngineeringClaimBindingLedger",)
