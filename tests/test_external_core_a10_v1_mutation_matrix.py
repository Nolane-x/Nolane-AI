from __future__ import annotations

from dataclasses import replace

import pytest

import nolane.external_core.integration_admission_bundle as admission_bundle
from nolane.external_core.observation import (
    CanonicalObservationEnvelope,
    CanonicalObservationSurfaceContract,
    CanonicalSurfaceProviderExpectation,
    REQUIRED_SURFACE_KINDS,
    SurfaceObservationReceipt,
    detect_observation_forks,
    validate_observation_completeness,
    validate_observation_provenance,
    validate_observation_transition,
)
from nolane.external_core.observation_integration import (
    canonical_observation_provider_expectations,
    canonical_observation_scope_digests,
)
from nolane.external_core.observation_population import validate_observed_component_population


ENVELOPE_KEYS = (
    "protocol",
    "surface_contract",
    "observed_epoch",
    "registry_digest",
    "authority_graph_digest",
    "source_state_frontier_digest",
    "evidence_frontier_digest",
    "artifact_frontier_digest",
    "freshness_fence_frontier_digest",
    "handoff_frontier_digest",
    "work_trace_frontier_digest",
    "surface_receipts",
    "chain_id",
    "previous_observation_digest",
    "digest",
)

CONTRACT_KEYS = (
    "protocol",
    "required_component_ids",
    "required_surface_kinds",
    "digest",
)

RECEIPT_KEYS = (
    "protocol",
    "surface_kind",
    "provider_id",
    "provider_version",
    "source_locator",
    "scope_digest",
    "observed_state_digest",
    "enumeration_complete",
    "observed_epoch",
    "digest",
)


def _frontiers() -> dict[str, dict[str, str]]:
    return {
        "current_source_state_digests": {},
        "current_evidence_digests": {},
        "current_artifact_digests": {},
        "current_freshness_fences": {},
        "known_handoff_digests": {},
        "current_work_trace_digests": {},
    }


def _envelope(
    *,
    epoch: int = 7,
    chain_id: str = "external-core:test",
    previous: str | None = None,
) -> CanonicalObservationEnvelope:
    return admission_bundle.build_canonical_observation(
        observed_epoch=epoch,
        chain_id=chain_id,
        previous_observation_digest=previous,
        **_frontiers(),
    )


def _surface_digests(envelope: CanonicalObservationEnvelope) -> dict[str, str]:
    return {
        "registry": envelope.registry_digest,
        "authority-graph": envelope.authority_graph_digest,
        "source-state": envelope.source_state_frontier_digest,
        "evidence": envelope.evidence_frontier_digest,
        "artifact": envelope.artifact_frontier_digest,
        "freshness": envelope.freshness_fence_frontier_digest,
        "handoff": envelope.handoff_frontier_digest,
        "work-trace": envelope.work_trace_frontier_digest,
    }


def _rebuild(
    envelope: CanonicalObservationEnvelope,
    *,
    surface_contract: CanonicalObservationSurfaceContract | None = None,
    observed_epoch: int | None = None,
    registry_digest: str | None = None,
    authority_graph_digest: str | None = None,
    source_state_frontier_digest: str | None = None,
    evidence_frontier_digest: str | None = None,
    artifact_frontier_digest: str | None = None,
    freshness_fence_frontier_digest: str | None = None,
    handoff_frontier_digest: str | None = None,
    work_trace_frontier_digest: str | None = None,
    surface_receipts: tuple[SurfaceObservationReceipt, ...] | None = None,
    chain_id: str | None = None,
    previous_observation_digest: object = ...,
) -> CanonicalObservationEnvelope:
    previous = (
        envelope.previous_observation_digest
        if previous_observation_digest is ...
        else previous_observation_digest
    )
    assert previous is None or isinstance(previous, str)
    return CanonicalObservationEnvelope.create(
        surface_contract=envelope.surface_contract if surface_contract is None else surface_contract,
        observed_epoch=envelope.observed_epoch if observed_epoch is None else observed_epoch,
        registry_digest=envelope.registry_digest if registry_digest is None else registry_digest,
        authority_graph_digest=(
            envelope.authority_graph_digest
            if authority_graph_digest is None
            else authority_graph_digest
        ),
        source_state_frontier_digest=(
            envelope.source_state_frontier_digest
            if source_state_frontier_digest is None
            else source_state_frontier_digest
        ),
        evidence_frontier_digest=(
            envelope.evidence_frontier_digest
            if evidence_frontier_digest is None
            else evidence_frontier_digest
        ),
        artifact_frontier_digest=(
            envelope.artifact_frontier_digest
            if artifact_frontier_digest is None
            else artifact_frontier_digest
        ),
        freshness_fence_frontier_digest=(
            envelope.freshness_fence_frontier_digest
            if freshness_fence_frontier_digest is None
            else freshness_fence_frontier_digest
        ),
        handoff_frontier_digest=(
            envelope.handoff_frontier_digest
            if handoff_frontier_digest is None
            else handoff_frontier_digest
        ),
        work_trace_frontier_digest=(
            envelope.work_trace_frontier_digest
            if work_trace_frontier_digest is None
            else work_trace_frontier_digest
        ),
        surface_receipts=envelope.surface_receipts if surface_receipts is None else surface_receipts,
        chain_id=envelope.chain_id if chain_id is None else chain_id,
        previous_observation_digest=previous,
    )


def _replace_receipt(
    envelope: CanonicalObservationEnvelope,
    kind: str,
    **changes: object,
) -> CanonicalObservationEnvelope:
    target = envelope.surface_receipt(kind)
    kwargs: dict[str, object] = {
        "surface_kind": target.surface_kind,
        "provider_id": target.provider_id,
        "provider_version": target.provider_version,
        "source_locator": target.source_locator,
        "scope_digest": target.scope_digest,
        "observed_state_digest": target.observed_state_digest,
        "enumeration_complete": target.enumeration_complete,
        "observed_epoch": target.observed_epoch,
    }
    kwargs.update(changes)
    replacement = SurfaceObservationReceipt.create(**kwargs)
    rows = tuple(
        replacement if row.surface_kind == kind else row
        for row in envelope.surface_receipts
    )
    return _rebuild(envelope, surface_receipts=rows)


@pytest.mark.parametrize("missing_key", ENVELOPE_KEYS)
def test_envelope_from_state_rejects_every_missing_top_level_key(missing_key: str) -> None:
    state = _envelope().to_state()
    state.pop(missing_key)
    with pytest.raises(ValueError):
        CanonicalObservationEnvelope.from_state(state)


def test_envelope_from_state_rejects_unknown_top_level_key() -> None:
    state = _envelope().to_state()
    state["unexpected"] = "value"
    with pytest.raises(ValueError, match="non-canonical"):
        CanonicalObservationEnvelope.from_state(state)


@pytest.mark.parametrize("missing_key", CONTRACT_KEYS)
def test_surface_contract_rejects_every_missing_key(missing_key: str) -> None:
    state = _envelope().surface_contract.to_state()
    state.pop(missing_key)
    with pytest.raises(ValueError):
        CanonicalObservationSurfaceContract.from_state(state)


def test_surface_contract_rejects_unknown_key() -> None:
    state = _envelope().surface_contract.to_state()
    state["unexpected"] = "value"
    with pytest.raises(ValueError, match="non-canonical"):
        CanonicalObservationSurfaceContract.from_state(state)


@pytest.mark.parametrize("missing_key", RECEIPT_KEYS)
def test_surface_receipt_rejects_every_missing_key(missing_key: str) -> None:
    state = _envelope().surface_receipts[0].to_state()
    state.pop(missing_key)
    with pytest.raises(ValueError):
        SurfaceObservationReceipt.from_state(state)


def test_surface_receipt_rejects_unknown_key() -> None:
    state = _envelope().surface_receipts[0].to_state()
    state["unexpected"] = "value"
    with pytest.raises(ValueError, match="non-canonical"):
        SurfaceObservationReceipt.from_state(state)


@pytest.mark.parametrize("epoch", [True, False, -1, 1.0, "1", None])
def test_epoch_type_and_range_smuggling_is_rejected(epoch: object) -> None:
    with pytest.raises(ValueError, match="exact non-negative integer"):
        SurfaceObservationReceipt.create(
            surface_kind="registry",
            provider_id="provider",
            provider_version="1",
            source_locator="locator",
            scope_digest="scope",
            observed_state_digest="state",
            enumeration_complete=True,
            observed_epoch=epoch,  # type: ignore[arg-type]
        )


def test_enumeration_complete_rejects_integer_boolean_laundering() -> None:
    with pytest.raises(ValueError, match="exact boolean"):
        SurfaceObservationReceipt.create(
            surface_kind="registry",
            provider_id="provider",
            provider_version="1",
            source_locator="locator",
            scope_digest="scope",
            observed_state_digest="state",
            enumeration_complete=1,  # type: ignore[arg-type]
            observed_epoch=1,
        )


@pytest.mark.parametrize(
    "values",
    [
        ("external.a", "external.a"),
        ("",),
        (True,),
    ],
)
def test_component_identity_contract_is_strict(values: tuple[object, ...]) -> None:
    with pytest.raises(ValueError):
        CanonicalObservationSurfaceContract.create(
            required_component_ids=values,  # type: ignore[arg-type]
        )


def test_contract_and_receipt_input_order_are_canonicalized() -> None:
    contract = CanonicalObservationSurfaceContract.create(
        required_component_ids=("external.b", "external.a")
    )
    assert contract.required_component_ids == ("external.a", "external.b")

    envelope = _envelope()
    reversed_receipts = tuple(reversed(envelope.surface_receipts))
    rebuilt = _rebuild(envelope, surface_receipts=reversed_receipts)
    assert rebuilt.surface_receipts == envelope.surface_receipts
    assert rebuilt.digest == envelope.digest


def test_frontier_mapping_order_does_not_change_observation_identity() -> None:
    forward = _frontiers()
    forward["current_source_state_digests"] = {
        "external.a": "digest-a",
        "external.b": "digest-b",
    }
    reverse = _frontiers()
    reverse["current_source_state_digests"] = {
        "external.b": "digest-b",
        "external.a": "digest-a",
    }
    left = admission_bundle.build_canonical_observation(
        observed_epoch=7,
        chain_id="external-core:test",
        **forward,
    )
    right = admission_bundle.build_canonical_observation(
        observed_epoch=7,
        chain_id="external-core:test",
        **reverse,
    )
    assert left.to_state() == right.to_state()
    assert left.digest == right.digest


def test_envelope_digest_changes_for_each_semantic_top_level_commitment() -> None:
    base = _envelope()
    contract = CanonicalObservationSurfaceContract.create(
        required_component_ids=(
            *base.surface_contract.required_component_ids,
            "external.synthetic",
        )
    )
    provider_mutation = _replace_receipt(
        base,
        "registry",
        provider_id="external-core:canonical-observer:registry:mutated",
    )

    variants = (
        _rebuild(base, observed_epoch=8),
        _rebuild(base, registry_digest="registry-mutated"),
        _rebuild(base, authority_graph_digest="authority-mutated"),
        _rebuild(base, source_state_frontier_digest="source-mutated"),
        _rebuild(base, evidence_frontier_digest="evidence-mutated"),
        _rebuild(base, artifact_frontier_digest="artifact-mutated"),
        _rebuild(base, freshness_fence_frontier_digest="freshness-mutated"),
        _rebuild(base, handoff_frontier_digest="handoff-mutated"),
        _rebuild(base, work_trace_frontier_digest="trace-mutated"),
        _rebuild(base, chain_id="external-core:other-chain"),
        _rebuild(base, previous_observation_digest="canonical-observation-v1-predecessor"),
        _rebuild(base, surface_contract=contract),
        provider_mutation,
    )
    digests = {base.digest, *(row.digest for row in variants)}
    assert len(digests) == 1 + len(variants)


@pytest.mark.parametrize("kind", REQUIRED_SURFACE_KINDS)
def test_every_missing_surface_is_classified(kind: str) -> None:
    envelope = _envelope()
    receipts = tuple(row for row in envelope.surface_receipts if row.surface_kind != kind)
    forged = _rebuild(envelope, surface_receipts=receipts)
    findings = validate_observation_completeness(
        forged,
        expected_component_ids=envelope.surface_contract.required_component_ids,
        observed_surface_digests=_surface_digests(envelope),
    )
    assert any(
        row.code == "OBSERVATION_REQUIRED_SURFACE_MISSING" and row.subject_id == kind
        for row in findings
    )


@pytest.mark.parametrize("kind", REQUIRED_SURFACE_KINDS)
def test_every_incomplete_surface_is_classified(kind: str) -> None:
    envelope = _replace_receipt(_envelope(), kind, enumeration_complete=False)
    findings = validate_observation_completeness(
        envelope,
        expected_component_ids=envelope.surface_contract.required_component_ids,
        observed_surface_digests=_surface_digests(envelope),
    )
    assert any(
        row.code == "OBSERVATION_ENUMERATION_INCOMPLETE" and row.subject_id == kind
        for row in findings
    )


@pytest.mark.parametrize("kind", REQUIRED_SURFACE_KINDS)
def test_every_surface_epoch_rebinding_is_classified(kind: str) -> None:
    envelope = _replace_receipt(_envelope(), kind, observed_epoch=6)
    findings = validate_observation_completeness(
        envelope,
        expected_component_ids=envelope.surface_contract.required_component_ids,
        observed_surface_digests=_surface_digests(envelope),
    )
    assert any(
        row.code == "OBSERVATION_SURFACE_EPOCH_MISMATCH" and row.subject_id == kind
        for row in findings
    )


@pytest.mark.parametrize("kind", REQUIRED_SURFACE_KINDS)
def test_every_detached_surface_digest_mismatch_is_classified(kind: str) -> None:
    envelope = _envelope()
    observed = _surface_digests(envelope)
    observed[kind] = "detached-state-mutated"
    findings = validate_observation_completeness(
        envelope,
        expected_component_ids=envelope.surface_contract.required_component_ids,
        observed_surface_digests=observed,
    )
    assert any(
        row.code == "OBSERVATION_SURFACE_STATE_DIGEST_MISMATCH"
        and row.subject_id == kind
        for row in findings
    )


@pytest.mark.parametrize("kind", REQUIRED_SURFACE_KINDS)
@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("provider_id", "OBSERVATION_PROVIDER_ID_MISMATCH"),
        ("provider_version", "OBSERVATION_PROVIDER_VERSION_MISMATCH"),
        ("source_locator", "OBSERVATION_SOURCE_LOCATOR_MISMATCH"),
    ],
)
def test_every_surface_provider_binding_field_is_enforced(
    kind: str,
    field: str,
    code: str,
) -> None:
    envelope = _replace_receipt(_envelope(), kind, **{field: f"mutated:{field}"})
    findings = validate_observation_provenance(
        envelope,
        provider_expectations=canonical_observation_provider_expectations(),
        expected_scope_digests=canonical_observation_scope_digests(
            envelope.surface_contract.required_component_ids
        ),
    )
    assert any(row.code == code and row.subject_id == kind for row in findings)


@pytest.mark.parametrize("kind", REQUIRED_SURFACE_KINDS)
@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("scope_digest", "scope-mutated", "OBSERVATION_PROVENANCE_SCOPE_MISMATCH"),
        ("observed_epoch", 6, "OBSERVATION_PROVENANCE_EPOCH_MISMATCH"),
        (
            "observed_state_digest",
            "content-mutated",
            "OBSERVATION_PROVENANCE_CONTENT_MISMATCH",
        ),
    ],
)
def test_every_surface_provenance_scope_epoch_and_content_binding_is_enforced(
    kind: str,
    field: str,
    value: object,
    code: str,
) -> None:
    envelope = _replace_receipt(_envelope(), kind, **{field: value})
    findings = validate_observation_provenance(
        envelope,
        provider_expectations=canonical_observation_provider_expectations(),
        expected_scope_digests=canonical_observation_scope_digests(
            envelope.surface_contract.required_component_ids
        ),
    )
    assert any(row.code == code and row.subject_id == kind for row in findings)


def test_forged_duplicate_and_unknown_receipts_fail_closed_at_integrity_boundary() -> None:
    envelope = _envelope()
    duplicate = replace(
        envelope,
        surface_receipts=(*envelope.surface_receipts, envelope.surface_receipts[0]),
    )
    with pytest.raises(ValueError, match="integrity validation failed"):
        duplicate.validate_integrity()

    unknown = replace(
        envelope,
        surface_receipts=(
            replace(envelope.surface_receipts[0], surface_kind="unknown-surface"),
            *envelope.surface_receipts[1:],
        ),
    )
    with pytest.raises(ValueError, match="integrity validation failed"):
        unknown.validate_integrity()


def test_transition_matrix_is_fail_closed_and_exact() -> None:
    genesis = _envelope(epoch=1)
    assert validate_observation_transition(None, genesis, genesis=True) == ()

    bad_genesis = _envelope(
        epoch=1,
        previous="canonical-observation-v1-not-allowed",
    )
    assert {
        row.code for row in validate_observation_transition(None, bad_genesis, genesis=True)
    } == {"OBSERVATION_GENESIS_CONTEXT_INVALID"}

    predecessor = _envelope(epoch=6, chain_id="external-core:test")
    valid = _envelope(
        epoch=7,
        chain_id="external-core:test",
        previous=predecessor.digest,
    )
    assert validate_observation_transition(predecessor, valid) == ()

    without_predecessor = _envelope(epoch=7, chain_id="external-core:test")
    assert {
        row.code for row in validate_observation_transition(None, without_predecessor)
    } == {"OBSERVATION_PREDECESSOR_UNAVAILABLE"}

    wrong_digest = _envelope(
        epoch=7,
        chain_id="external-core:test",
        previous="canonical-observation-v1-wrong",
    )
    assert "OBSERVATION_PREDECESSOR_DIGEST_MISMATCH" in {
        row.code for row in validate_observation_transition(predecessor, wrong_digest)
    }

    wrong_chain = _envelope(
        epoch=7,
        chain_id="external-core:other",
        previous=predecessor.digest,
    )
    assert "OBSERVATION_CHAIN_ID_MISMATCH" in {
        row.code for row in validate_observation_transition(predecessor, wrong_chain)
    }

    equal_epoch = _envelope(
        epoch=6,
        chain_id="external-core:test",
        previous=predecessor.digest,
    )
    lower_epoch = _envelope(
        epoch=5,
        chain_id="external-core:test",
        previous=predecessor.digest,
    )
    assert "OBSERVATION_EPOCH_NOT_MONOTONIC" in {
        row.code for row in validate_observation_transition(predecessor, equal_epoch)
    }
    assert "OBSERVATION_EPOCH_NOT_MONOTONIC" in {
        row.code for row in validate_observation_transition(predecessor, lower_epoch)
    }

    large_monotonic_jump = _envelope(
        epoch=100,
        chain_id="external-core:test",
        previous=predecessor.digest,
    )
    assert validate_observation_transition(predecessor, large_monotonic_jump) == ()


def test_fork_detection_is_strictly_limited_to_supplied_competing_evidence() -> None:
    predecessor = _envelope(epoch=6, chain_id="external-core:test")
    left_frontiers = _frontiers()
    left_frontiers["current_source_state_digests"] = {"external.a": "left"}
    right_frontiers = _frontiers()
    right_frontiers["current_source_state_digests"] = {"external.a": "right"}

    left = admission_bundle.build_canonical_observation(
        observed_epoch=7,
        chain_id="external-core:test",
        previous_observation_digest=predecessor.digest,
        **left_frontiers,
    )
    right = admission_bundle.build_canonical_observation(
        observed_epoch=7,
        chain_id="external-core:test",
        previous_observation_digest=predecessor.digest,
        **right_frontiers,
    )
    assert detect_observation_forks((left,)) == ()
    assert detect_observation_forks((left, left)) == ()
    assert {
        row.code for row in detect_observation_forks((left, right))
    } == {"OBSERVATION_FORK_DETECTED"}

    other_chain = _rebuild(right, chain_id="external-core:other")
    assert detect_observation_forks((left, other_chain)) == ()


def test_negative_space_population_cannot_be_laundered_by_expected_contract() -> None:
    findings = validate_observed_component_population(
        expected_component_ids=("external.a", "external.b"),
        contract_component_ids=("external.a", "external.b"),
        observed_component_ids=("external.a",),
    )
    assert {
        (row.code, row.subject_id) for row in findings
    } == {("OBSERVATION_REQUIRED_COMPONENT_UNOBSERVED", "external.b")}

    unexpected = validate_observed_component_population(
        expected_component_ids=("external.a",),
        contract_component_ids=("external.a",),
        observed_component_ids=("external.a", "external.x"),
    )
    assert {
        (row.code, row.subject_id) for row in unexpected
    } == {("OBSERVATION_UNEXPECTED_COMPONENT_OBSERVED", "external.x")}


def test_negative_space_population_rejects_duplicate_and_non_string_identities() -> None:
    with pytest.raises(ValueError, match="duplicate observed component identity"):
        validate_observed_component_population(
            expected_component_ids=("external.a",),
            contract_component_ids=("external.a",),
            observed_component_ids=("external.a", "external.a"),
        )
    with pytest.raises(ValueError, match="exact non-empty strings"):
        validate_observed_component_population(
            expected_component_ids=("external.a",),
            contract_component_ids=("external.a",),
            observed_component_ids=("external.a", True),  # type: ignore[arg-type]
        )
