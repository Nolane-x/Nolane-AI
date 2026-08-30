import pytest

from nolane.external_core.goal_design import GoalDesignCoherencePlane, GoalDesignVersionVector
from nolane.external_core.goal_design_ledger import AuthorityLevel, EventKind, GoalDesignLedger


def _snapshot():
    return GoalDesignCoherencePlane().freeze_snapshot(GoalDesignVersionVector("r1", "p1", "a1", "i1", "c1"))


def test_generic_cognition_cannot_self_grant_authority():
    ledger = GoalDesignLedger()
    with pytest.raises(ValueError, match="typed authority"):
        ledger.append(EventKind.PROPOSAL, {"idea": "rewrite everything"}, authority_level=AuthorityLevel.AUTHORITY)


def test_snapshot_is_typed_authority_and_content_addressed():
    ledger = GoalDesignLedger()
    snapshot = _snapshot()
    first = ledger.record_snapshot(snapshot)
    second = ledger.record_snapshot(snapshot)
    assert first.authority_level is AuthorityLevel.AUTHORITY
    assert first.event_id == second.event_id
    assert len(ledger.events) == 1


def test_unknown_causal_parent_is_rejected():
    with pytest.raises(ValueError, match="causal parents"):
        GoalDesignLedger().append(EventKind.OBSERVATION, {"x": 1}, parent_ids=("missing",))
