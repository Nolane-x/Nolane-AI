from __future__ import annotations

import pytest

from nolane.external_core.audit import build_canonical_fabric_profile, build_canonical_registry
from nolane.external_core.handoff import ExternalHandoffEnvelope, HandoffAuthorityClass
from nolane.external_core.integration_admission import (
    AdmissionDisposition,
    CanonicalAdmissionContext,
    admit_handoff_state,
    canonical_frontier_digest,
)


class _StringLaunderer:
    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return self.value


def _handoff() -> ExternalHandoffEnvelope:
    profile = build_canonical_fabric_profile()
    edge = profile.authority_graph.edges[0]
    producer = next(row for row in profile.manifests if row.component_id == edge.source_component_id)
    return ExternalHandoffEnvelope.create(
        producer_component_id=producer.component_id,
        producer_component_version=producer.component_version,
        producer_agent_id="agent-a5-test",
        consumer_component_id=edge.target_component_id,
        consumer_contract_range="1",
        subject_id="subject-a5-test",
        subject_digest="subject-digest-a5-test",
        contract_kind=edge.contract_kind,
        contract_version="1",
        authority_class=HandoffAuthorityClass.INFORMATIVE,
        source_state_digest="source-state-a5-test",
        predecessor_handoff_ids=(),
        evidence_bindings=(),
        artifact_bindings=(),
        freshness_fence=None,
        limitations=("structural-test",),
        known_unknowns=(),
        payload={"kind": "a5-test"},
    )


def _frontiers(handoff: ExternalHandoffEnvelope) -> dict[str, dict[str, str]]:
    return {
        "source": {handoff.producer_component_id: handoff.source_state_digest},
        "evidence": {},
        "artifact": {},
        "freshness": {},
        "handoff": {},
        "trace": {},
    }


def _context(handoff: ExternalHandoffEnvelope, *, source_override: str | None = None) -> CanonicalAdmissionContext:
    registry = build_canonical_registry()
    profile = build_canonical_fabric_profile()
    frontiers = _frontiers(handoff)
    source_digest = source_override or canonical_frontier_digest("source-state", frontiers["source"])
    return CanonicalAdmissionContext.create(
        registry_digest=registry.registry_digest,
        authority_graph_digest=profile.authority_graph.digest,
        source_state_frontier_digest=source_digest,
        evidence_frontier_digest=canonical_frontier_digest("evidence", frontiers["evidence"]),
        artifact_frontier_digest=canonical_frontier_digest("artifact", frontiers["artifact"]),
        freshness_fence_frontier_digest=canonical_frontier_digest("freshness", frontiers["freshness"]),
        handoff_frontier_digest=canonical_frontier_digest("handoff", frontiers["handoff"]),
        work_trace_frontier_digest=canonical_frontier_digest("work-trace", frontiers["trace"]),
        observed_epoch=2,
    )


def _admit(handoff: ExternalHandoffEnvelope, *, context: CanonicalAdmissionContext | None = None, evidence: dict[object, object] | None = None):
    frontiers = _frontiers(handoff)
    return admit_handoff_state(
        handoff.to_state(),
        context=context or _context(handoff),
        current_source_state_digests=frontiers["source"],
        current_evidence_digests=frontiers["evidence"] if evidence is None else evidence,
        current_artifact_digests=frontiers["artifact"],
        current_freshness_fences=frontiers["freshness"],
        known_handoff_digests=frontiers["handoff"],
    )


def test_exact_current_handoff_is_admitted() -> None:
    handoff = _handoff()
    admitted = _admit(handoff)
    assert admitted.receipt.disposition is AdmissionDisposition.ADMITTED
    admitted.validate_integrity()


def test_raw_handoff_string_laundering_is_rejected_before_legacy_restore() -> None:
    handoff = _handoff()
    state = handoff.to_state()
    state["subject_id"] = _StringLaunderer(handoff.subject_id)
    frontiers = _frontiers(handoff)
    with pytest.raises(ValueError, match="subject_id|explicit string"):
        admit_handoff_state(
            state,
            context=_context(handoff),
            current_source_state_digests=frontiers["source"],
            current_evidence_digests=frontiers["evidence"],
            current_artifact_digests=frontiers["artifact"],
            current_freshness_fences=frontiers["freshness"],
            known_handoff_digests=frontiers["handoff"],
        )


def test_current_frontier_string_laundering_is_rejected_before_a2_validation() -> None:
    handoff = _handoff()
    with pytest.raises(ValueError, match="explicit string"):
        _admit(handoff, evidence={"unrelated": _StringLaunderer("digest")})


def test_handoff_cannot_replay_under_another_source_frontier_context() -> None:
    handoff = _handoff()
    admitted = _admit(handoff, context=_context(handoff, source_override="another-frontier"))
    assert admitted.receipt.disposition is AdmissionDisposition.BLOCKED
    assert "SOURCE_STATE_FRONTIER_CONTEXT_MISMATCH" in admitted.receipt.reason_codes
