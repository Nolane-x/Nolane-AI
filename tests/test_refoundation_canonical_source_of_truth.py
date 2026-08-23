from __future__ import annotations

import inspect

import cogcoder.refoundation.manifests as manifests_module
from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.refoundation.manifests import build_bootstrap_agent_manifests
from cogcoder.refoundation.regions import build_region_manifests


def test_manifest_builder_no_longer_calls_legacy_blueprint() -> None:
    source = inspect.getsource(manifests_module)
    assert "from cogcoder.organization.blueprint import" not in source
    assert "build_first_generation_blueprint()" not in inspect.getsource(
        manifests_module.build_bootstrap_agent_manifests
    )


def test_canonical_source_still_has_exact_legacy_parity() -> None:
    legacy = [row.to_state() for row in build_first_generation_blueprint()]
    canonical = [row.identity_state() for row in build_bootstrap_agent_manifests()]
    assert canonical == legacy


def test_region_manifests_are_derived_from_canonical_agent_manifests_not_legacy_region_specs() -> None:
    manifest_by_id = {row.agent_id: row for row in build_bootstrap_agent_manifests()}
    regions = build_region_manifests()
    for region in regions:
        members = [manifest_by_id[agent_id] for agent_id in region.permanent_agent_ids]
        assert all(row.region == region.region_id for row in members)
        assert {row.agent_id for row in members} == set(region.permanent_agent_ids)
