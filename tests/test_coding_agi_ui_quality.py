import pytest

from cogcoder.organization.ui import UIQualityEvidence, UIQualityKind


def test_ui_quality_evidence_rejects_negative_counters_and_requires_observations():
    with pytest.raises(ValueError):
        UIQualityEvidence(
            evidence_id='EV-BAD', verifier_agent_id='verification.integration-e2e.01',
            kind=UIQualityKind.VISUAL_DIFF, passed=True, false_accepts=-1,
            observation_ids=('ui-observation-00000001',), evidence_refs=('EV-RAW',),
        )
    with pytest.raises(ValueError):
        UIQualityEvidence(
            evidence_id='EV-NO-OBS', verifier_agent_id='verification.integration-e2e.01',
            kind=UIQualityKind.ACCESSIBILITY, passed=True,
            observation_ids=(), evidence_refs=('EV-RAW',),
        )


def test_ui_quality_evidence_round_trips_canonically():
    row = UIQualityEvidence(
        evidence_id='EV-QUALITY', verifier_agent_id='verification.integration-e2e.01',
        kind=UIQualityKind.RESPONSIVE, passed=True, false_accepts=0, regressions=0,
        observation_ids=('ui-observation-00000001', 'ui-observation-00000002'),
        evidence_refs=('EV-MOBILE', 'EV-DESKTOP'),
    )
    assert UIQualityEvidence.from_state(row.to_state()) == row
