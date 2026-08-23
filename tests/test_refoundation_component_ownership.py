from __future__ import annotations

from cogcoder.refoundation.manifests import build_component_manifests
from cogcoder.refoundation.runtime_state_map import build_runtime_state_bindings


def test_every_runtime_state_owner_is_a_declared_versioned_component() -> None:
    component_ids = {row.component_id for row in build_component_manifests()}
    owners = {row.canonical_owner for row in build_runtime_state_bindings()}
    assert owners.issubset(component_ids)


def test_fixed_67_and_temporary_work_units_are_separate_declared_components() -> None:
    component_ids = {row.component_id for row in build_component_manifests()}
    assert "organization.identity" in component_ids
    assert "organization.temporary_work_units" in component_ids


def test_coordination_and_evaluation_have_aggregate_state_owners_plus_subcomponents() -> None:
    component_ids = {row.component_id for row in build_component_manifests()}
    assert {
        "organization.coordination",
        "organization.coordination.leases",
        "organization.coordination.delivery",
        "evaluation.scaling",
        "evaluation.regimes",
        "evaluation.evidence",
        "evaluation.stress",
        "evaluation.parameters",
        "evaluation.release",
        "evaluation.claims",
    }.issubset(component_ids)
