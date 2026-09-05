from __future__ import annotations

import pytest

from nolane.external_core.evidence import EvidenceRecord, ScopedEvidenceRecord


def _record(**overrides) -> ScopedEvidenceRecord:
    values = {
        "evidence_id": "scoped-ev-1",
        "subject_id": "external.integration",
        "subject_version": "0.0.3",
        "subject_digest": "subject-digest-1",
        "scope_digest": "scope-digest-1",
        "verifier_agent_id": "verification.agent.1",
        "observed_epoch": 17,
        "passed": True,
        "false_accepts": 0,
        "regressions": 0,
        "evidence_refs": ("artifact:a", "trace:b"),
        "limitations": ("linux-only",),
    }
    values.update(overrides)
    return ScopedEvidenceRecord.create(**values)


def test_scoped_evidence_is_content_addressed_and_exactly_restorable() -> None:
    record = _record()
    assert record.digest
    assert ScopedEvidenceRecord.from_state(record.to_state()) == record
    assert record.to_state()["protocol"] == "scoped-evidence-v2"


def test_scoped_evidence_canonicalizes_set_like_refs() -> None:
    left = _record(evidence_refs=("trace:b", "artifact:a"), limitations=("z", "a"))
    right = _record(evidence_refs=("artifact:a", "trace:b"), limitations=("a", "z"))
    assert left == right
    assert left.evidence_refs == ("artifact:a", "trace:b")
    assert left.limitations == ("a", "z")


def test_legacy_evidence_record_remains_backward_compatible() -> None:
    legacy = EvidenceRecord("legacy-1", "verification.agent.legacy", True, 0, 0, "kept")
    assert EvidenceRecord.from_state(legacy.to_state()) == legacy


def test_scoped_evidence_rejects_digest_tampering_on_restore() -> None:
    state = _record().to_state()
    state["digest"] = "forged"
    with pytest.raises(ValueError, match="digest|integrity|canonical"):
        ScopedEvidenceRecord.from_state(state)


def test_scoped_evidence_state_rejects_unknown_fields() -> None:
    state = _record().to_state()
    state["authority"] = "assurance"
    with pytest.raises(ValueError, match="canonical|state"):
        ScopedEvidenceRecord.from_state(state)
