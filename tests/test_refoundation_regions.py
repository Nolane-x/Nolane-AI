from __future__ import annotations

from cogcoder.refoundation.regions import build_region_manifests


def test_exactly_15_noncentral_region_manifests_cover_66_regional_identities() -> None:
    regions = build_region_manifests()
    assert len(regions) == 15
    all_ids = [agent_id for region in regions for agent_id in region.permanent_agent_ids]
    assert len(all_ids) == 66
    assert len(set(all_ids)) == 66
    assert "nolane.central" not in set(all_ids)


def test_each_region_has_exactly_one_chief_and_at_least_two_specialists() -> None:
    for region in build_region_manifests():
        assert region.chief_agent_id.endswith(".chief")
        assert region.chief_agent_id in region.permanent_agent_ids
        assert len(region.specialist_agent_ids) >= 2
        assert set(region.specialist_agent_ids) == set(region.permanent_agent_ids) - {region.chief_agent_id}


def test_region_manifests_preserve_direct_work_and_learning_contracts() -> None:
    for region in build_region_manifests():
        assert region.chief_direct_work_capable
        assert region.all_agents_learning_capable
        assert region.all_agents_direct_work_capable


def test_region_external_core_surface_is_explicit_and_nonempty() -> None:
    for region in build_region_manifests():
        assert region.external_core_surface
        assert len(set(region.external_core_surface)) == len(region.external_core_surface)


def test_region_definition_versions_start_independently_at_0_0_0() -> None:
    regions = build_region_manifests()
    assert all(region.region_definition_version == "0.0.0" for region in regions)
    assert len({region.region_id for region in regions}) == 15
    assert all(len(region.digest) == 64 for region in regions)
