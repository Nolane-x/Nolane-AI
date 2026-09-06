from __future__ import annotations

from collections.abc import Iterator, Mapping

from nolane.external_core import compatibility, integration
import nolane.external_core.integration_admission as admission
import nolane.external_core.integration_admission_bundle as admission_bundle
from nolane.external_core.handoff import ExternalHandoffEnvelope, HandoffAuthorityClass
from nolane.external_core.work_trace import CognitiveWorkTrace
from nolane.metadata.component_versions import component_revision_map


class _FlippingFrontier(Mapping[str, str]):
    def __init__(self, key: str, first: str, later: str) -> None:
        self._key = key
        self._first = first
        self._later = later
        self.reads = 0

    def __getitem__(self, key: str) -> str:
        if key != self._key:
            raise KeyError(key)
        return self._first if self.reads <= 1 else self._later

    def __iter__(self) -> Iterator[str]:
        yield self._key

    def __len__(self) -> int:
        return 1

    def items(self):
        self.reads += 1
        value = self._first if self.reads == 1 else self._later
        return ((self._key, value),)


def _count_canonical_reads(monkeypatch):
    strict_current_objects = admission_bundle._strict_current_objects
    admission_current_objects = admission._canonical_current_objects
    reads = {"bundle": 0, "admission": 0}

    def counted_bundle_observation():
        reads["bundle"] += 1
        return strict_current_objects()

    def counted_admission_observation():
        reads["admission"] += 1
        return admission_current_objects()

    monkeypatch.setattr(admission_bundle, "_strict_current_objects", counted_bundle_observation)
    monkeypatch.setattr(admission, "_canonical_current_objects", counted_admission_observation)
    return reads


def _valid_handoff_state() -> tuple[dict[str, object], dict[str, str]]:
    registry, _profile = admission_bundle._strict_current_objects()
    for producer in registry.manifests:
        for consumer in registry.manifests:
            shared = sorted(set(producer.produces_contracts) & set(consumer.consumes_contracts))
            if not shared:
                continue
            source_digest = "a7-source-state-digest"
            envelope = ExternalHandoffEnvelope.create(
                producer_component_id=producer.component_id,
                producer_component_version=producer.component_version,
                producer_agent_id="a7-observer",
                consumer_component_id=consumer.component_id,
                consumer_contract_range="*",
                subject_id="a7-handoff-subject",
                subject_digest="a7-handoff-subject-digest",
                contract_kind=shared[0],
                contract_version="1",
                authority_class=HandoffAuthorityClass.INFORMATIVE,
                source_state_digest=source_digest,
                predecessor_handoff_ids=(),
                evidence_bindings=(),
                artifact_bindings=(),
                freshness_fence=None,
                limitations=("a7-test-only",),
                known_unknowns=(),
                payload={"a7": "handoff"},
            )
            return envelope.to_state(), {producer.component_id: source_digest}
    raise AssertionError("canonical registry has no producer/consumer contract pair for an A7 handoff fixture")


def _valid_work_trace_state() -> tuple[dict[str, object], dict[str, str]]:
    trace = CognitiveWorkTrace("a7-work-trace")
    return trace.to_state(), {trace.trace_id: trace.digest}


def test_bundle_build_uses_one_canonical_observation(monkeypatch) -> None:
    reads = _count_canonical_reads(monkeypatch)

    bundle = admission_bundle.build_canonical_admission_bundle(observed_epoch=11)
    bundle.validate_integrity()

    assert reads == {"bundle": 1, "admission": 0}


def test_persisted_bundle_audit_uses_one_canonical_observation(monkeypatch) -> None:
    bundle = admission_bundle.build_canonical_admission_bundle(observed_epoch=11)
    reads = _count_canonical_reads(monkeypatch)

    report = admission_bundle.run_canonical_admission_audit(
        bundle=bundle,
        current_observed_epoch=11,
    )

    assert report.findings == ()
    assert reads == {"bundle": 1, "admission": 0}


def test_bundle_build_with_handoff_reuses_one_canonical_observation(monkeypatch) -> None:
    handoff_state, source = _valid_handoff_state()
    reads = _count_canonical_reads(monkeypatch)

    bundle = admission_bundle.build_canonical_admission_bundle(
        observed_epoch=11,
        current_source_state_digests=source,
        handoff_states=(handoff_state,),
    )
    bundle.validate_integrity()

    assert len(bundle.handoffs) == 1
    assert reads == {"bundle": 1, "admission": 0}


def test_bundle_build_with_work_trace_reuses_one_canonical_observation(monkeypatch) -> None:
    trace_state, traces = _valid_work_trace_state()
    reads = _count_canonical_reads(monkeypatch)

    bundle = admission_bundle.build_canonical_admission_bundle(
        observed_epoch=11,
        current_work_trace_digests=traces,
        work_trace_states=(trace_state,),
    )
    bundle.validate_integrity()

    assert len(bundle.work_traces) == 1
    assert reads == {"bundle": 1, "admission": 0}


def test_bundle_snapshots_mutable_frontier_once_before_handoff_admission() -> None:
    handoff_state, source = _valid_handoff_state()
    component_id, source_digest = next(iter(source.items()))
    flipping = _FlippingFrontier(component_id, source_digest, "a7-mutated-source-state-digest")

    bundle = admission_bundle.build_canonical_admission_bundle(
        observed_epoch=11,
        current_source_state_digests=flipping,
        handoff_states=(handoff_state,),
    )
    bundle.validate_integrity()

    assert len(bundle.handoffs) == 1
    assert flipping.reads == 1


def test_persisted_bundle_audit_snapshots_mutable_frontier_once_before_replay() -> None:
    handoff_state, source = _valid_handoff_state()
    bundle = admission_bundle.build_canonical_admission_bundle(
        observed_epoch=11,
        current_source_state_digests=source,
        handoff_states=(handoff_state,),
    )
    component_id, source_digest = next(iter(source.items()))
    flipping = _FlippingFrontier(component_id, source_digest, "a7-mutated-source-state-digest")

    report = admission_bundle.run_canonical_admission_audit(
        bundle=bundle,
        current_observed_epoch=11,
        current_source_state_digests=flipping,
    )

    assert report.findings == ()
    assert flipping.reads == 1


def test_fresh_audit_reuses_builder_canonical_observation(monkeypatch) -> None:
    reads = _count_canonical_reads(monkeypatch)

    report = admission_bundle.run_canonical_admission_audit(observed_epoch=11)

    assert report.findings == ()
    assert reads == {"bundle": 1, "admission": 0}


def test_a7_advances_only_current_integration_audit_lane() -> None:
    assert integration.COMPONENT_ID == "external.integration"
    assert integration.COMPONENT_VERSION == "0.0.6"
    assert compatibility.SEMANTIC_SURFACE_VERSION == "0.0.6"
    assert admission_bundle.COMPONENT_ID == "external.integration"
    assert admission_bundle.COMPONENT_VERSION == "0.0.6"
    assert component_revision_map()["external.integration"] == 6

    report = admission_bundle.run_canonical_admission_audit(observed_epoch=11)
    assert report.protocol == "external-integration-admission-audit-v3"
    assert report.digest.startswith("admission-audit-v3-")

    assert admission_bundle.ADMISSION_BUNDLE_PROTOCOL == "external-integration-admission-bundle-v2"
    assert admission.ADMISSION_PROTOCOL == "external-integration-admission-v2"
    assert admission.COMPONENT_VERSION == "0.0.4"
