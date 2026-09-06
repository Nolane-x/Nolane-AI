from __future__ import annotations

import nolane.external_core.integration_admission as admission
import nolane.external_core.integration_admission_bundle as admission_bundle


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
