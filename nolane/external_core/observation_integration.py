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


def _component_ids(registry: Any) -> tuple[str, ...]:
    return tuple(sorted(row.component_id for row in registry.manifests))


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
    return {
        kind: CanonicalSurfaceProviderExpectation(
            surface_kind=kind,
            provider_id=f"external-core:canonical-observer:{kind}",
            provider_version=CANONICAL_OBSERVER_PROVIDER_VERSION,
            source_locator=f"nolane.external_core.observation_integration:{kind}",
        )
        for kind in REQUIRED_SURFACE_KINDS
    }


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
    component_ids = _component_ids(registry)
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
    component_ids = _component_ids(registry)
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
    findings = list(
        validate_observation_completeness(
            envelope,
            expected_component_ids=component_ids,
            observed_surface_digests=surface_digests,
            expected_scope_digests=scope_digests,
        )
    )
    findings.extend(
        validate_observed_component_population(
            expected_component_ids=component_ids,
            contract_component_ids=envelope.surface_contract.required_component_ids,
            observed_component_ids=component_ids,
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
    return tuple(sorted(findings, key=lambda row: (row.code, row.subject_id, row.detail)))


__all__ = (
    "CANONICAL_OBSERVATION_CHAIN_ID",
    "build_observation_from_snapshot",
    "canonical_observation_provider_expectations",
    "canonical_observation_scope_digests",
    "canonical_observation_surface_digests",
    "validate_observation_against_snapshot",
)
