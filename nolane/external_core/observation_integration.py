from __future__ import annotations

from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.integration_admission import canonical_frontier_digest
from nolane.external_core.observation import (
    CanonicalObservationEnvelope,
    CanonicalObservationSurfaceContract,
    CanonicalSurfaceProviderExpectation,
    ObservationFinding,
    REQUIRED_SURFACE_KINDS,
    SurfaceObservationReceipt,
    detect_observation_forks,
    validate_observation_completeness,
    validate_observation_provenance,
    validate_observation_transition,
)
from nolane.external_core.observation_population import validate_observed_component_population


CANONICAL_OBSERVATION_CHAIN_ID = "external-core:canonical-observation"
CANONICAL_OBSERVER_PROVIDER_VERSION = "1"


def _component_ids(population: Any) -> tuple[str, ...]:
    rows: list[str] = []
    seen: set[str] = set()
    for manifest in population.manifests:
        component_id = getattr(manifest, "component_id", None)
        if type(component_id) is not str or not component_id.strip():
            raise ValueError("canonical observation component population contains an invalid identity")
        if component_id in seen:
            raise ValueError(f"canonical observation component population contains duplicate identity: {component_id}")
        seen.add(component_id)
        rows.append(component_id)
    return tuple(sorted(rows))


def _expected_component_ids() -> tuple[str, ...]:
    """Read the declared canonical adapter population independently of a registry capture."""

    from nolane.external_core.audit import _canonical_adapter_specs

    rows: list[str] = []
    seen: set[str] = set()
    for spec in _canonical_adapter_specs():
        component_id = getattr(spec.source, "COMPONENT_ID", None)
        if type(component_id) is not str or not component_id.strip():
            raise ValueError("expected canonical adapter population contains an invalid component identity")
        if component_id in seen:
            raise ValueError(f"expected canonical adapter population contains duplicate identity: {component_id}")
        seen.add(component_id)
        rows.append(component_id)
    return tuple(sorted(rows))


def _validate_capture_population(registry: Any, profile: Any) -> tuple[str, ...]:
    expected = _expected_component_ids()
    observed = _component_ids(registry)
    profile_ids = _component_ids(profile)

    if observed != expected:
        missing = sorted(set(expected) - set(observed))
        unexpected = sorted(set(observed) - set(expected))
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unexpected:
            details.append("unexpected=" + ",".join(unexpected))
        raise ValueError(
            "canonical observation component population does not match independently expected adapter population"
            + (": " + ";".join(details) if details else "")
        )
    if profile_ids != observed:
        raise ValueError("canonical observation registry/profile population mismatch")
    return expected


def canonical_observation_surface_digests(
    registry: Any,
    profile: Any,
    *,
    source: Mapping[str, str],
    evidence: Mapping[str, str],
    artifact: Mapping[str, str],
    freshness: Mapping[str, str],
    handoffs: Mapping[str, str],
    traces: Mapping[str, str],
) -> dict[str, str]:
    return {
        "registry": registry.registry_digest,
        "authority-graph": profile.authority_graph.digest,
        "source-state": canonical_frontier_digest("source-state", source),
        "evidence": canonical_frontier_digest("evidence", evidence),
        "artifact": canonical_frontier_digest("artifact", artifact),
        "freshness": canonical_frontier_digest("freshness", freshness),
        "handoff": canonical_frontier_digest("handoff", handoffs),
        "work-trace": canonical_frontier_digest("work-trace", traces),
    }


def canonical_observation_scope_digests(
    required_component_ids: Sequence[str],
) -> dict[str, str]:
    component_ids = tuple(sorted(required_component_ids))
    return {
        kind: "observation-scope-v1-"
        + canonical_digest(
            {
                "surface_kind": kind,
                "required_component_ids": list(component_ids),
                "enumeration": "complete-current-canonical-surface",
            }
        )
        for kind in REQUIRED_SURFACE_KINDS
    }


def canonical_observation_provider_expectations() -> dict[str, CanonicalSurfaceProviderExpectation]:
    expectations = {
        kind: CanonicalSurfaceProviderExpectation(
            surface_kind=kind,
            provider_id=f"external-core:canonical-observer:{kind}",
            provider_version=CANONICAL_OBSERVER_PROVIDER_VERSION,
            source_locator=f"nolane.external_core.observation_integration:{kind}",
        )
        for kind in REQUIRED_SURFACE_KINDS
    }
    expectations["registry"] = CanonicalSurfaceProviderExpectation(
        surface_kind="registry",
        provider_id="external-core:canonical-registry",
        provider_version=CANONICAL_OBSERVER_PROVIDER_VERSION,
        source_locator="nolane.external_core.audit:build_canonical_registry",
    )
    expectations["authority-graph"] = CanonicalSurfaceProviderExpectation(
        surface_kind="authority-graph",
        provider_id="external-core:canonical-authority-graph",
        provider_version=CANONICAL_OBSERVER_PROVIDER_VERSION,
        source_locator="nolane.external_core.audit:build_canonical_fabric_profile",
    )
    return expectations


def build_observation_from_snapshot(
    registry: Any,
    profile: Any,
    *,
    observed_epoch: int,
    source: Mapping[str, str],
    evidence: Mapping[str, str],
    artifact: Mapping[str, str],
    freshness: Mapping[str, str],
    handoffs: Mapping[str, str],
    traces: Mapping[str, str],
    chain_id: str,
    previous_observation_digest: str | None,
) -> CanonicalObservationEnvelope:
    component_ids = _validate_capture_population(registry, profile)
    surface_contract = CanonicalObservationSurfaceContract.create(
        required_component_ids=component_ids,
    )
    surface_digests = canonical_observation_surface_digests(
        registry,
        profile,
        source=source,
        evidence=evidence,
        artifact=artifact,
        freshness=freshness,
        handoffs=handoffs,
        traces=traces,
    )
    scope_digests = canonical_observation_scope_digests(component_ids)
    expectations = canonical_observation_provider_expectations()
    receipts = tuple(
        SurfaceObservationReceipt.create(
            surface_kind=kind,
            provider_id=expectations[kind].provider_id,
            provider_version=expectations[kind].provider_version,
            source_locator=expectations[kind].source_locator,
            scope_digest=scope_digests[kind],
            observed_state_digest=surface_digests[kind],
            enumeration_complete=True,
            observed_epoch=observed_epoch,
        )
        for kind in REQUIRED_SURFACE_KINDS
    )
    envelope = CanonicalObservationEnvelope.create(
        surface_contract=surface_contract,
        observed_epoch=observed_epoch,
        registry_digest=surface_digests["registry"],
        authority_graph_digest=surface_digests["authority-graph"],
        source_state_frontier_digest=surface_digests["source-state"],
        evidence_frontier_digest=surface_digests["evidence"],
        artifact_frontier_digest=surface_digests["artifact"],
        freshness_fence_frontier_digest=surface_digests["freshness"],
        handoff_frontier_digest=surface_digests["handoff"],
        work_trace_frontier_digest=surface_digests["work-trace"],
        surface_receipts=receipts,
        chain_id=chain_id,
        previous_observation_digest=previous_observation_digest,
    )
    envelope.validate_integrity()
    return envelope


def validate_observation_against_snapshot(
    envelope: CanonicalObservationEnvelope,
    *,
    registry: Any,
    profile: Any,
    source: Mapping[str, str],
    evidence: Mapping[str, str],
    artifact: Mapping[str, str],
    freshness: Mapping[str, str],
    handoffs: Mapping[str, str],
    traces: Mapping[str, str],
    predecessor: CanonicalObservationEnvelope | None,
    genesis: bool,
    competing_successors: Sequence[CanonicalObservationEnvelope],
) -> tuple[ObservationFinding, ...]:
    expected_component_ids = _expected_component_ids()
    observed_component_ids = _component_ids(registry)
    profile_component_ids = _component_ids(profile)
    surface_digests = canonical_observation_surface_digests(
        registry,
        profile,
        source=source,
        evidence=evidence,
        artifact=artifact,
        freshness=freshness,
        handoffs=handoffs,
        traces=traces,
    )
    scope_digests = canonical_observation_scope_digests(expected_component_ids)
    findings = list(
        validate_observation_completeness(
            envelope,
            expected_component_ids=expected_component_ids,
            observed_surface_digests=surface_digests,
            expected_scope_digests=scope_digests,
        )
    )
    findings.extend(
        validate_observed_component_population(
            expected_component_ids=expected_component_ids,
            contract_component_ids=envelope.surface_contract.required_component_ids,
            observed_component_ids=observed_component_ids,
        )
    )
    if profile_component_ids != observed_component_ids:
        findings.extend(
            validate_observed_component_population(
                expected_component_ids=expected_component_ids,
                contract_component_ids=envelope.surface_contract.required_component_ids,
                observed_component_ids=profile_component_ids,
            )
        )
    findings.extend(
        validate_observation_provenance(
            envelope,
            provider_expectations=canonical_observation_provider_expectations(),
            expected_scope_digests=scope_digests,
        )
    )
    findings.extend(validate_observation_transition(predecessor, envelope, genesis=genesis))
    findings.extend(detect_observation_forks((envelope, *competing_successors)))
    return tuple(sorted(set(findings), key=lambda row: (row.code, row.subject_id, row.detail)))


__all__ = (
    "CANONICAL_OBSERVATION_CHAIN_ID",
    "build_observation_from_snapshot",
    "canonical_observation_provider_expectations",
    "canonical_observation_scope_digests",
    "canonical_observation_surface_digests",
    "validate_observation_against_snapshot",
)
