from __future__ import annotations

import pytest

from nolane.external_core.component_contracts import ExternalComponentManifest, ExternalCoreFamily
from nolane.external_core.integration_evolution import (
    ComponentEvolutionDelta,
    EvolutionCompatibilityDisposition,
    qualify_component_evolution,
)


def _manifest(
    *,
    component_id: str = "external.integration",
    version: str = "0.0.1",
    consumes: tuple[str, ...] = ("candidate",),
    produces: tuple[str, ...] = ("integrated",),
    authorities: tuple[str, ...] = ("integrate",),
    forbidden: tuple[str, ...] = ("assure", "execute"),
    resources: tuple[str, ...] = ("integration.graph",),
) -> ExternalComponentManifest:
    return ExternalComponentManifest.create(
        component_id=component_id,
        component_version=version,
        family=ExternalCoreFamily.D,
        protocol_versions={"integration": "1"},
        consumes_contracts=consumes,
        produces_contracts=produces,
        authority_capabilities=authorities,
        forbidden_authorities=forbidden,
        mutable_resources=resources,
        evidence_inputs=("verification",),
        evidence_outputs=("integration-receipt",),
        restore_protocol="exact-revalidation",
        compatibility_floor=version,
        compatibility_ceiling=version,
    )


def test_identical_manifest_delta_is_compatible() -> None:
    manifest = _manifest()
    delta = ComponentEvolutionDelta.create(manifest, manifest)
    assert delta.changed_fields == ()
    qualification = qualify_component_evolution(delta)
    assert qualification.disposition is EvolutionCompatibilityDisposition.COMPATIBLE


def test_version_only_evolution_requires_revalidation_not_incompatibility() -> None:
    delta = ComponentEvolutionDelta.create(_manifest(), _manifest(version="0.0.2"))
    assert "component_version" in delta.changed_fields
    qualification = qualify_component_evolution(delta)
    assert qualification.disposition is EvolutionCompatibilityDisposition.REVALIDATION_REQUIRED


def test_removing_declared_contract_is_incompatible() -> None:
    delta = ComponentEvolutionDelta.create(_manifest(), _manifest(version="0.0.2", produces=()))
    qualification = qualify_component_evolution(delta)
    assert qualification.disposition is EvolutionCompatibilityDisposition.INCOMPATIBLE
    assert "PRODUCED_CONTRACT_REMOVED" in qualification.reason_codes


def test_mutable_resource_rebinding_is_incompatible() -> None:
    delta = ComponentEvolutionDelta.create(
        _manifest(),
        _manifest(version="0.0.2", resources=("integration.other",)),
    )
    qualification = qualify_component_evolution(delta)
    assert qualification.disposition is EvolutionCompatibilityDisposition.INCOMPATIBLE
    assert "MUTABLE_RESOURCE_AUTHORITY_CHANGED" in qualification.reason_codes


def test_evolution_delta_rejects_component_identity_rebinding() -> None:
    with pytest.raises(ValueError, match="component identity"):
        ComponentEvolutionDelta.create(_manifest(), _manifest(component_id="external.planning", version="0.0.2"))


def test_evolution_delta_exact_restore_rejects_digest_tamper() -> None:
    delta = ComponentEvolutionDelta.create(_manifest(), _manifest(version="0.0.2"))
    state = delta.to_state()
    state["delta_id"] = "forged"
    with pytest.raises(ValueError, match="delta"):
        ComponentEvolutionDelta.from_state(state)
