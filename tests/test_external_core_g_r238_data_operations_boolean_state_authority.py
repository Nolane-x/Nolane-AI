from __future__ import annotations

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.data_operations import (
    ConsistencyExercise,
    MigrationPlan,
    MigrationReadinessReceipt,
)


def _migration_plan_state() -> dict[str, object]:
    payload = {
        "migration_id": "migration-r238",
        "producer_agent_id": "data-storage-migration.agent-r238",
        "from_schema_version": "1",
        "to_schema_version": "2",
        "forward_artifact_id": "forward-r238",
        "rollback_artifact_id": "rollback-r238",
        "compatibility_evidence_refs": ["compat-r238"],
        "validation_evidence_refs": ["validation-r238"],
        "online": True,
        "idempotent": True,
    }
    return {**payload, "digest": canonical_digest(payload)}


@pytest.mark.parametrize("field", ["online", "idempotent"])
def test_migration_plan_restore_requires_exact_boolean_fields(field: str) -> None:
    state = _migration_plan_state()
    state[field] = "false"

    with pytest.raises(ValueError, match=f"migration {field} must be an exact boolean"):
        MigrationPlan.from_state(state)


def test_migration_readiness_restore_requires_exact_boolean_ready() -> None:
    payload = {
        "receipt_id": "migration-ready-r238",
        "migration_id": "migration-r238",
        "ready": True,
        "reasons": [],
    }
    state = {**payload, "digest": canonical_digest(payload)}
    state["ready"] = "false"

    with pytest.raises(ValueError, match="migration readiness ready must be an exact boolean"):
        MigrationReadinessReceipt.from_state(state)


def test_consistency_exercise_restore_requires_exact_boolean_consistent() -> None:
    payload = {
        "exercise_id": "consistency-r238",
        "producer_agent_id": "data-storage-migration.agent-r238",
        "source_version": "1",
        "cache_version": "1",
        "operation_sequence": ["read", "write"],
        "observed_result": "ok",
        "expected_result": "ok",
        "evidence_refs": ["evidence-r238"],
        "consistent": True,
    }
    state = {**payload, "digest": canonical_digest(payload)}
    state["consistent"] = "false"

    with pytest.raises(ValueError, match="consistency exercise consistent must be an exact boolean"):
        ConsistencyExercise.from_state(state)
