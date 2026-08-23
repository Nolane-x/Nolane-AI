from __future__ import annotations

import pytest

from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.refoundation.composition import build_wave1_composition_lock
from cogcoder.refoundation.manifests import (
    FIRST_GENERATION_SNAPSHOT,
    build_bootstrap_agent_manifests,
    build_component_manifests,
)
from cogcoder.refoundation.migration import LegacyDisposition, LegacyPathRecord, ReviewDepth
from cogcoder.refoundation.versioning import ComponentVersion


PINNED_SNAPSHOT = "1a8f333f72dd02abacf1a1bd6e2288c1025521de"


def _legacy_by_id():
    return {row.agent_id: row for row in build_first_generation_blueprint()}


def _manifest_by_id():
    return {row.agent_id: row for row in build_bootstrap_agent_manifests()}


def test_refoundation_is_pinned_to_execution_bridge_snapshot() -> None:
    assert FIRST_GENERATION_SNAPSHOT == PINNED_SNAPSHOT


def test_exactly_67_permanent_agent_manifests() -> None:
    manifests = build_bootstrap_agent_manifests()
    assert len(manifests) == 67
    assert len({row.agent_id for row in manifests}) == 67
    assert all(row.permanent for row in manifests)


def test_permanent_rank_cardinality_is_preserved() -> None:
    manifests = build_bootstrap_agent_manifests()
    counts: dict[str, int] = {}
    for row in manifests:
        counts[row.rank] = counts.get(row.rank, 0) + 1

    assert counts == {
        "central": 1,
        "chief": 15,
        "senior_specialist": 20,
        "specialist": 31,
    }


def test_bootstrap_manifests_preserve_every_legacy_identity_contract() -> None:
    legacy = _legacy_by_id()
    manifests = _manifest_by_id()
    assert set(manifests) == set(legacy)

    for agent_id, old in legacy.items():
        new = manifests[agent_id]
        assert new.name == old.name
        assert new.region == old.region
        assert new.role == old.role
        assert new.rank == old.rank.value
        assert new.neural_version == old.neural_version
        assert new.memory_namespace == old.memory_namespace
        assert new.skill_namespace == old.skill_namespace
        assert new.direct_work_capable == old.direct_work_capable
        assert new.learning_capable == old.learning_capable
        assert new.cognitive_capabilities == old.cognitive_capabilities
        assert new.external_core_bindings == old.external_core_bindings
        assert new.tool_permissions == old.tool_permissions
        assert new.parameter_accounting == old.parameter_accounting.to_state()


def test_no_foundry_ephemeral_identity_enters_permanent_manifest_set() -> None:
    ids = {row.agent_id for row in build_bootstrap_agent_manifests()}
    assert all("ephemeral" not in agent_id for agent_id in ids)
    assert all("foundry" not in agent_id for agent_id in ids)


def test_every_first_generation_identity_stays_below_100m_parameters() -> None:
    for row in build_bootstrap_agent_manifests():
        assert row.parameter_accounting["total_physical_parameters"] < 100_000_000


def test_all_canonical_components_bootstrap_at_0_0_0() -> None:
    components = build_component_manifests()
    assert len(components) >= 50
    assert len({row.component_id for row in components}) == len(components)
    assert all(row.version == ComponentVersion(0, 0, 0) for row in components)


def test_component_versions_are_strict_component_local_revisions() -> None:
    assert str(ComponentVersion.parse("0.0.0")) == "0.0.0"
    assert str(ComponentVersion.parse("0.0.47").next_revision()) == "0.0.48"
    with pytest.raises(ValueError):
        ComponentVersion.parse("0.1.0")
    with pytest.raises(ValueError):
        ComponentVersion.parse("1.0.0")
    with pytest.raises(ValueError):
        ComponentVersion.parse("0.0.-1")


def test_composition_lock_resolves_every_dependency_and_is_acyclic() -> None:
    lock = build_wave1_composition_lock()
    ids = set(lock.components)
    assert ids == {row.component_id for row in build_component_manifests()}
    assert all(version == "0.0.0" for version in lock.components.values())
    assert lock.unresolved_dependencies() == ()
    assert set(lock.topological_order()) == ids


def test_composition_lock_is_bound_to_pinned_source_snapshot() -> None:
    lock = build_wave1_composition_lock()
    assert lock.source_snapshot_sha == PINNED_SNAPSHOT
    assert len(lock.digest) == 64


def test_legacy_paths_default_to_keep_and_delete_is_fail_closed() -> None:
    row = LegacyPathRecord(path="cogcoder/r269_meta_learning_kernel.py")
    assert row.disposition is LegacyDisposition.KEEP
    assert row.review_depth is ReviewDepth.UNREVIEWED
    assert not row.destructive_action_allowed


def test_delete_requires_line_review_parity_migration_and_history_provenance() -> None:
    base = dict(
        path="cogcoder/organization/runtime_part15.py",
        disposition=LegacyDisposition.HISTORY,
        review_depth=ReviewDepth.LINE_REVIEWED,
        blob_sha="d19d65a27ec6ec2c1e0aa7a87408d562ec9eeb59",
    )

    assert not LegacyPathRecord(**base).destructive_action_allowed
    assert not LegacyPathRecord(**base, parity_receipt="parity-1").destructive_action_allowed
    assert not LegacyPathRecord(
        **base,
        parity_receipt="parity-1",
        migration_receipt="migration-1",
    ).destructive_action_allowed

    safe = LegacyPathRecord(
        **base,
        parity_receipt="parity-1",
        migration_receipt="migration-1",
        history_provenance="history/runtime-part15/d19d65a2",
    )
    assert safe.destructive_action_allowed


def test_active_legacy_runtime_layers_are_explicitly_preserved_in_wave1() -> None:
    lock = build_wave1_composition_lock()
    expected = {
        "cogcoder/organization/runtime_core.py",
        "cogcoder/organization/runtime_part13.py",
        "cogcoder/organization/runtime_part14.py",
        "cogcoder/organization/runtime_part15.py",
        "cogcoder/organization/runtime.py",
    }
    assert expected.issubset(set(lock.preserved_legacy_paths))


def test_component_manifest_distinguishes_software_neural_and_state_versions() -> None:
    for component in build_component_manifests():
        assert str(component.version) == "0.0.0"
        assert component.state_schema
        assert component.version_identity == "component_version"

    agents = build_bootstrap_agent_manifests()
    assert all(row.neural_version for row in agents)
    assert all(row.agent_definition_version == "0.0.0" for row in agents)
