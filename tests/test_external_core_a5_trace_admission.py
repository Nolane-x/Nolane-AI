from __future__ import annotations

import pytest

from nolane.external_core.audit import build_canonical_fabric_profile, build_canonical_registry
from nolane.external_core.integration_admission import (
    AdmissionDisposition,
    CanonicalAdmissionContext,
    admit_work_trace_state,
    canonical_frontier_digest,
)
from nolane.external_core.work_trace import CognitiveWorkTrace, TraceNodeStatus


class _StringLaunderer:
    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return self.value


def _trace() -> CognitiveWorkTrace:
    trace = CognitiveWorkTrace("trace-a5-test")
    trace.append_node(
        component_id="external.evidence",
        subject_id="subject-a5-trace",
        subject_digest="subject-a5-trace-digest",
        status=TraceNodeStatus.INFORMATIVE,
        predecessor_node_ids=(),
        handoff_id="handoff-a5-test",
        evidence_refs=(),
        limitations=("structural-test",),
    )
    return trace


def _frontiers(trace: CognitiveWorkTrace) -> tuple[dict[str, str], dict[str, str]]:
    return {"handoff-a5-test": "handoff-digest-a5-test"}, {trace.trace_id: trace.digest}


def _context(trace: CognitiveWorkTrace, *, handoff_override: str | None = None) -> CanonicalAdmissionContext:
    registry = build_canonical_registry()
    profile = build_canonical_fabric_profile()
    handoffs, traces = _frontiers(trace)
    return CanonicalAdmissionContext.create(
        registry_digest=registry.registry_digest,
        authority_graph_digest=profile.authority_graph.digest,
        source_state_frontier_digest=canonical_frontier_digest("source-state", {}),
        evidence_frontier_digest=canonical_frontier_digest("evidence", {}),
        artifact_frontier_digest=canonical_frontier_digest("artifact", {}),
        freshness_fence_frontier_digest=canonical_frontier_digest("freshness", {}),
        handoff_frontier_digest=handoff_override or canonical_frontier_digest("handoff", handoffs),
        work_trace_frontier_digest=canonical_frontier_digest("work-trace", traces),
        observed_epoch=3,
    )


def _admit(trace: CognitiveWorkTrace, *, context: CanonicalAdmissionContext | None = None):
    handoffs, traces = _frontiers(trace)
    return admit_work_trace_state(
        trace.to_state(),
        context=context or _context(trace),
        known_handoff_digests=handoffs,
        current_work_trace_digests=traces,
    )


def test_exact_current_work_trace_is_admitted() -> None:
    trace = _trace()
    admitted = _admit(trace)
    assert admitted.receipt.disposition is AdmissionDisposition.ADMITTED
    admitted.validate_integrity()


def test_work_trace_raw_string_laundering_is_rejected_before_legacy_restore() -> None:
    trace = _trace()
    state = trace.to_state()
    state["trace_id"] = _StringLaunderer(trace.trace_id)
    handoffs, traces = _frontiers(trace)
    with pytest.raises(ValueError, match="trace_id|explicit string"):
        admit_work_trace_state(
            state,
            context=_context(trace),
            known_handoff_digests=handoffs,
            current_work_trace_digests=traces,
        )


def test_work_trace_serialized_nodes_must_remain_lists() -> None:
    trace = _trace()
    state = trace.to_state()
    state["nodes"] = tuple(state["nodes"])
    handoffs, traces = _frontiers(trace)
    with pytest.raises(ValueError, match="nodes.*serialized list|serialized list"):
        admit_work_trace_state(
            state,
            context=_context(trace),
            known_handoff_digests=handoffs,
            current_work_trace_digests=traces,
        )


def test_work_trace_cannot_replay_under_another_handoff_frontier_context() -> None:
    trace = _trace()
    admitted = _admit(trace, context=_context(trace, handoff_override="another-handoff-frontier"))
    assert admitted.receipt.disposition is AdmissionDisposition.BLOCKED
    assert "HANDOFF_FRONTIER_CONTEXT_MISMATCH" in admitted.receipt.reason_codes


def test_missing_current_handoff_reference_blocks_trace_admission() -> None:
    trace = _trace()
    _handoffs, traces = _frontiers(trace)
    context = CanonicalAdmissionContext.create(
        registry_digest=build_canonical_registry().registry_digest,
        authority_graph_digest=build_canonical_fabric_profile().authority_graph.digest,
        source_state_frontier_digest=canonical_frontier_digest("source-state", {}),
        evidence_frontier_digest=canonical_frontier_digest("evidence", {}),
        artifact_frontier_digest=canonical_frontier_digest("artifact", {}),
        freshness_fence_frontier_digest=canonical_frontier_digest("freshness", {}),
        handoff_frontier_digest=canonical_frontier_digest("handoff", {}),
        work_trace_frontier_digest=canonical_frontier_digest("work-trace", traces),
        observed_epoch=3,
    )
    admitted = admit_work_trace_state(
        trace.to_state(),
        context=context,
        known_handoff_digests={},
        current_work_trace_digests=traces,
    )
    assert admitted.receipt.disposition is AdmissionDisposition.BLOCKED
    assert "MISSING_HANDOFF_REFERENCE" in admitted.receipt.reason_codes
