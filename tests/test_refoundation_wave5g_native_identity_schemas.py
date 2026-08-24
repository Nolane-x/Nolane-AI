from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from cogcoder.refoundation.inventory import GitSnapshotInventory
from cogcoder.refoundation.manifests import FIRST_GENERATION_SNAPSHOT


ROOT = Path(__file__).resolve().parents[1]
TARGET_NAMES = {
    "PHYSICAL_PARAMETER_CEILING",
    "AgentRank",
    "AgentStatus",
    "ParameterAccounting",
    "AgentIdentity",
}


def _valid_identity():
    from cogcoder.organization.types import AgentIdentity, AgentRank, ParameterAccounting

    return AgentIdentity(
        agent_id="coding.backend.01",
        name="Coding Backend 01",
        region="coding-implementation",
        role="backend specialist",
        rank=AgentRank.SPECIALIST,
        neural_version="r2.3",
        parameter_accounting=ParameterAccounting(
            shared_physical_parameters=70_000_000,
            local_physical_parameters=10_000_000,
        ),
        region_chief_id="coding.chief",
        direct_work_capable=False,
        learning_capable=True,
        cognitive_capabilities=("reasoning", "coding"),
        memory_namespace="agent/coding.backend.01/memory",
        skill_namespace="agent/coding.backend.01/skills",
    )


def test_wave5g_historical_identity_schema_behavior_is_exact_before_cutover() -> None:
    from cogcoder.organization.types import (
        PHYSICAL_PARAMETER_CEILING,
        AgentIdentity,
        AgentRank,
        AgentStatus,
        ParameterAccounting,
    )

    assert PHYSICAL_PARAMETER_CEILING == 100_000_000
    assert tuple(row.value for row in AgentRank) == (
        "central",
        "chief",
        "senior_specialist",
        "specialist",
    )
    assert tuple(row.value for row in AgentStatus) == (
        "sleeping",
        "waking",
        "active",
        "waiting",
        "blocked",
        "checkpointing",
        "paused",
        "quarantined",
    )

    accounting = ParameterAccounting(70_000_000, 10_000_000)
    assert accounting.total_physical_parameters == 80_000_000
    assert accounting.to_state() == {
        "shared_physical_parameters": 70_000_000,
        "local_physical_parameters": 10_000_000,
        "total_physical_parameters": 80_000_000,
    }
    assert ParameterAccounting.from_state(accounting.to_state()) == accounting

    with pytest.raises(TypeError, match="parameter counts must be integers"):
        ParameterAccounting(True, 1)
    with pytest.raises(ValueError, match="parameter counts must be non-negative"):
        ParameterAccounting(-1, 0)
    with pytest.raises(ValueError, match="below 100,000,000"):
        ParameterAccounting(90_000_000, 10_000_000)

    identity = _valid_identity()
    assert identity.status is AgentStatus.SLEEPING
    assert identity.current_task is None
    assert identity.specialization_version == "specialization-0.1"
    assert identity.authority_scope == ("task",)
    assert identity.self_model_version == "self-model-0.1"
    assert AgentIdentity.from_state(identity.to_state()) == identity


def test_wave5g_historical_identity_validation_rules_are_preserved() -> None:
    from cogcoder.organization.types import AgentIdentity, AgentRank, ParameterAccounting

    accounting = ParameterAccounting(10, 20)
    common = dict(
        name="Identity",
        region="region",
        role="role",
        neural_version="r2.3",
        parameter_accounting=accounting,
        learning_capable=True,
        cognitive_capabilities=("reasoning",),
        memory_namespace="memory",
        skill_namespace="skills",
    )

    with pytest.raises(ValueError, match="agent_id must be non-empty"):
        AgentIdentity(
            agent_id="",
            rank=AgentRank.SPECIALIST,
            region_chief_id="chief",
            direct_work_capable=False,
            **common,
        )
    with pytest.raises(ValueError, match="cognitive capability floor"):
        AgentIdentity(
            agent_id="specialist",
            rank=AgentRank.SPECIALIST,
            region_chief_id="chief",
            direct_work_capable=False,
            cognitive_capabilities=(),
            **{key: value for key, value in common.items() if key != "cognitive_capabilities"},
        )
    with pytest.raises(ValueError, match="learning capable"):
        AgentIdentity(
            agent_id="specialist",
            rank=AgentRank.SPECIALIST,
            region_chief_id="chief",
            direct_work_capable=False,
            learning_capable=False,
            **{key: value for key, value in common.items() if key != "learning_capable"},
        )
    with pytest.raises(ValueError, match="direct workers"):
        AgentIdentity(
            agent_id="central",
            rank=AgentRank.CENTRAL,
            region_chief_id=None,
            direct_work_capable=False,
            **common,
        )
    with pytest.raises(ValueError, match="Central cannot have a regional chief"):
        AgentIdentity(
            agent_id="central",
            rank=AgentRank.CENTRAL,
            region_chief_id="chief",
            direct_work_capable=True,
            **common,
        )
    with pytest.raises(ValueError, match="Regional Chief must identify itself"):
        AgentIdentity(
            agent_id="chief",
            rank=AgentRank.CHIEF,
            region_chief_id="other",
            direct_work_capable=True,
            **common,
        )


def test_wave5g_schemas_identity_is_canonical_native_and_versioned() -> None:
    ledger = build_component_implementation_ledger()
    row = ledger["schemas.identity"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.schemas.identity"
    assert row.canonical_write_authority is True
    assert row.component_version == "0.0.1"
    assert row.legacy_sources == ("cogcoder/organization/types.py",)
    assert str(component_version("schemas.identity")) == "0.0.1"


def test_wave5g_canonical_identity_module_owns_all_five_primitives() -> None:
    canonical = importlib.import_module("nolane.schemas.identity")

    assert canonical.COMPONENT_ID == "schemas.identity"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.types"
    assert canonical.PHYSICAL_PARAMETER_CEILING == 100_000_000
    for name in ("AgentRank", "AgentStatus", "ParameterAccounting", "AgentIdentity"):
        assert getattr(canonical, name).__module__ == "nolane.schemas.identity"


def test_wave5g_historical_types_bridge_preserves_exact_identity_objects() -> None:
    legacy = importlib.import_module("cogcoder.organization.types")
    canonical = importlib.import_module("nolane.schemas.identity")

    assert legacy.PHYSICAL_PARAMETER_CEILING == canonical.PHYSICAL_PARAMETER_CEILING
    assert legacy.AgentRank is canonical.AgentRank
    assert legacy.AgentStatus is canonical.AgentStatus
    assert legacy.ParameterAccounting is canonical.ParameterAccounting
    assert legacy.AgentIdentity is canonical.AgentIdentity


def test_wave5g_active_code_has_no_identity_schema_reverse_imports() -> None:
    offenders: list[str] = []
    for source_root in (ROOT / "nolane", ROOT / "cogcoder" / "refoundation"):
        for path in sorted(source_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                if node.module != "cogcoder.organization.types":
                    continue
                moved = TARGET_NAMES.intersection(alias.name for alias in node.names)
                if moved:
                    offenders.append(
                        f"{path.relative_to(ROOT).as_posix()}:{node.lineno}:{','.join(sorted(moved))}"
                    )
    assert offenders == [], "active identity-schema reverse imports remain: " + "; ".join(offenders)


def test_wave5g_mixed_types_source_retains_non_identity_schemas_without_false_destination() -> None:
    from cogcoder.organization import types as legacy_types

    assert (ROOT / "cogcoder" / "organization" / "types.py").exists()
    assert hasattr(legacy_types, "SkillScope")
    assert hasattr(legacy_types, "EventKind")
    assert hasattr(legacy_types, "CognitiveEvent")
    assert hasattr(legacy_types, "ContextCapsule")

    census = GitSnapshotInventory.capture(ROOT, FIRST_GENERATION_SNAPSHOT).to_census()
    assert census.get("cogcoder/organization/types.py").canonical_destination is None


def test_wave5g_debt_reduces_only_identity_schema_legacy_internal_record() -> None:
    ledger = build_component_implementation_ledger()
    counts: dict[str, int] = {}
    non_native = []
    for row in ledger.values():
        if row.status is ImplementationStatus.CANONICAL_NATIVE:
            continue
        non_native.append(row)
        counts[row.status.value] = counts.get(row.status.value, 0) + 1

    # Wave 5G established an upper bound, not a permanent debt snapshot.
    # Later accepted native cutovers may monotonically reduce any debt class.
    assert len(non_native) <= 38
    assert counts.get("compatibility_facade", 0) <= 28
    assert counts.get("frozen_asset", 0) <= 1
    assert counts.get("historical_only", 0) <= 7
    assert counts.get("legacy_internal", 0) <= 2
    assert ledger["schemas.identity"].status is ImplementationStatus.CANONICAL_NATIVE
