from __future__ import annotations

from nolane.external_core.observation import (
    CanonicalObservationEnvelope,
    CanonicalObservationSurfaceContract,
    REQUIRED_SURFACE_KINDS,
    SurfaceObservationReceipt,
    detect_observation_forks,
    validate_observation_transition,
)


def _surface_digests(*, epoch: int, salt: str) -> dict[str, str]:
    return {
        kind: f"state:{kind}:{epoch}:{salt if kind == 'source-state' else 'stable'}"
        for kind in REQUIRED_SURFACE_KINDS
    }


def _observation(
    *,
    epoch: int,
    salt: str,
    chain_id: str = "external-core:default",
    previous_observation_digest: str | None = None,
) -> CanonicalObservationEnvelope:
    digests = _surface_digests(epoch=epoch, salt=salt)
    receipts = tuple(
        SurfaceObservationReceipt.create(
            surface_kind=kind,
            provider_id=f"provider:{kind}",
            provider_version="1",
            source_locator=f"source:{kind}",
            scope_digest=f"scope:{kind}:complete",
            observed_state_digest=digests[kind],
            enumeration_complete=True,
            observed_epoch=epoch,
        )
        for kind in REQUIRED_SURFACE_KINDS
    )
    return CanonicalObservationEnvelope.create(
        surface_contract=CanonicalObservationSurfaceContract.create(
            required_component_ids=("external.alpha", "external.beta"),
        ),
        observed_epoch=epoch,
        registry_digest=digests["registry"],
        authority_graph_digest=digests["authority-graph"],
        source_state_frontier_digest=digests["source-state"],
        evidence_frontier_digest=digests["evidence"],
        artifact_frontier_digest=digests["artifact"],
        freshness_fence_frontier_digest=digests["freshness"],
        handoff_frontier_digest=digests["handoff"],
        work_trace_frontier_digest=digests["work-trace"],
        surface_receipts=receipts,
        chain_id=chain_id,
        previous_observation_digest=previous_observation_digest,
    )


def _successor(
    previous: CanonicalObservationEnvelope,
    *,
    epoch: int,
    salt: str,
    chain_id: str | None = None,
    previous_digest: str | None = None,
) -> CanonicalObservationEnvelope:
    return _observation(
        epoch=epoch,
        salt=salt,
        chain_id=previous.chain_id if chain_id is None else chain_id,
        previous_observation_digest=(
            previous.digest if previous_digest is None else previous_digest
        ),
    )


def test_explicit_genesis_accepts_no_predecessor() -> None:
    genesis = _observation(epoch=1, salt="genesis")
    assert not validate_observation_transition(None, genesis, genesis=True)


def test_successor_requires_exact_predecessor_digest() -> None:
    previous = _observation(epoch=7, salt="previous")
    current = _successor(
        previous,
        epoch=8,
        salt="next",
        previous_digest="canonical-observation-v1-wrong",
    )
    findings = validate_observation_transition(previous, current)
    assert "OBSERVATION_PREDECESSOR_DIGEST_MISMATCH" in {
        row.code for row in findings
    }


def test_successor_requires_same_chain_id() -> None:
    previous = _observation(epoch=7, salt="previous")
    current = _successor(
        previous,
        epoch=8,
        salt="next",
        chain_id="external-core:other",
    )
    findings = validate_observation_transition(previous, current)
    assert "OBSERVATION_CHAIN_ID_MISMATCH" in {row.code for row in findings}


def test_successor_epoch_must_be_strictly_greater() -> None:
    previous = _observation(epoch=7, salt="previous")
    current = _successor(previous, epoch=7, salt="next")
    findings = validate_observation_transition(previous, current)
    assert "OBSERVATION_EPOCH_NOT_MONOTONIC" in {row.code for row in findings}


def test_missing_predecessor_is_not_silently_genesis() -> None:
    previous = _observation(epoch=7, salt="previous")
    current = _successor(previous, epoch=8, salt="next")
    findings = validate_observation_transition(None, current, genesis=False)
    assert "OBSERVATION_PREDECESSOR_UNAVAILABLE" in {row.code for row in findings}


def test_genesis_rejects_predecessor_commitment() -> None:
    current = _observation(
        epoch=1,
        salt="genesis",
        previous_observation_digest="canonical-observation-v1-predecessor",
    )
    findings = validate_observation_transition(None, current, genesis=True)
    assert "OBSERVATION_GENESIS_CONTEXT_INVALID" in {row.code for row in findings}


def test_distinct_sibling_successors_are_a_fork() -> None:
    previous = _observation(epoch=7, salt="previous")
    left = _successor(previous, epoch=8, salt="left")
    right = _successor(previous, epoch=8, salt="right")
    findings = detect_observation_forks((left, right))
    assert [row.code for row in findings] == ["OBSERVATION_FORK_DETECTED"]


def test_duplicate_successor_evidence_is_not_a_fork() -> None:
    previous = _observation(epoch=7, salt="previous")
    successor = _successor(previous, epoch=8, salt="same")
    assert not detect_observation_forks((successor, successor))
