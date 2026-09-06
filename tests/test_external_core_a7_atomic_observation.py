from __future__ import annotations

import nolane.external_core.integration_admission as admission
import nolane.external_core.integration_admission_bundle as admission_bundle
from nolane.external_core.handoff import ExternalHandoffEnvelope, HandoffAuthorityClass


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
