from __future__ import annotations

from types import SimpleNamespace

import pytest

import nolane.external_core.audit as external_audit
from nolane.external_core.observation_integration import build_observation_from_snapshot


def _capture(registry: object, profile: object):
    return build_observation_from_snapshot(
        registry,
        profile,
        observed_epoch=7,
        source={},
        evidence={},
        artifact={},
        freshness={},
        handoffs={},
        traces={},
        chain_id="external-core:test",
        previous_observation_digest=None,
    )


def test_capture_rejects_registry_missing_one_independently_expected_component() -> None:
    registry = external_audit.build_canonical_registry()
    profile = external_audit.build_canonical_fabric_profile()
    assert len(registry.manifests) >= 2

    missing_registry = SimpleNamespace(
        manifests=registry.manifests[:-1],
        registry_digest="registry-with-one-canonical-component-missing",
    )

    with pytest.raises(ValueError, match="component population"):
        _capture(missing_registry, profile)


def test_capture_rejects_unexpected_registry_component_even_if_contract_could_copy_it() -> None:
    registry = external_audit.build_canonical_registry()
    profile = external_audit.build_canonical_fabric_profile()
    unexpected_manifest = SimpleNamespace(component_id="external.synthetic-unexpected")
    expanded_registry = SimpleNamespace(
        manifests=(*registry.manifests, unexpected_manifest),
        registry_digest="registry-with-unexpected-component",
    )

    with pytest.raises(ValueError, match="component population"):
        _capture(expanded_registry, profile)


def test_capture_rejects_registry_profile_population_disagreement() -> None:
    registry = external_audit.build_canonical_registry()
    profile = external_audit.build_canonical_fabric_profile()
    assert len(profile.manifests) >= 2

    truncated_profile = SimpleNamespace(
        manifests=profile.manifests[:-1],
        authority_graph=profile.authority_graph,
    )

    with pytest.raises(ValueError, match="registry/profile population"):
        _capture(registry, truncated_profile)


def test_capture_contract_population_is_derived_from_independent_canonical_expectation() -> None:
    registry = external_audit.build_canonical_registry()
    profile = external_audit.build_canonical_fabric_profile()
    envelope = _capture(registry, profile)

    expected_ids = tuple(
        sorted(spec.source.COMPONENT_ID for spec in external_audit._canonical_adapter_specs())
    )
    observed_ids = tuple(sorted(row.component_id for row in registry.manifests))

    assert expected_ids == observed_ids
    assert envelope.surface_contract.required_component_ids == expected_ids
