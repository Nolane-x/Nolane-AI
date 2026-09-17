from __future__ import annotations

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.data_operations import MigrationReadinessReceipt


@pytest.mark.parametrize("alias", ["false", 1])
def test_migration_readiness_restore_requires_exact_boolean_ready(alias: object) -> None:
    payload = {
        "receipt_id": "migration-ready-r238",
        "migration_id": "migration-r238",
        "ready": True,
        "reasons": [],
    }
    receipt = MigrationReadinessReceipt(
        receipt_id=payload["receipt_id"],
        migration_id=payload["migration_id"],
        ready=True,
        reasons=(),
        digest=canonical_digest(payload),
    )
    state = receipt.to_state()
    state["ready"] = alias

    with pytest.raises(
        ValueError,
        match="migration readiness ready must be an exact boolean",
    ):
        MigrationReadinessReceipt.from_state(state)
