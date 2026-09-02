import pytest

from nolane.external_core.goal_design_integrity_runtime import (
    VERIFIED_CAPABILITY_AUTHORITY_TRUST,
)
from nolane.external_core.goal_design_revision_history import (
    ROOT_INTEGRITY_CONTRACT_TRUST,
    GoalRevisionHistoryCapability,
    GoalRevisionHistoryEntry,
    GoalRevisionHistoryExport,
    GoalRevisionHistoryReceipt,
    GoalRevisionHistorySnapshot,
    verify_goal_revision_history_export,
)


def test_public_verifier_rejects_self_consistent_verified_trust_without_revision_authority():
    capability = GoalRevisionHistoryCapability()
    root = GoalRevisionHistoryEntry(
        goal_id="goal:public-authority",
        ordinal=0,
        contract_digest="contract:root",
        trust_label=ROOT_INTEGRITY_CONTRACT_TRUST,
        source_refs=("provenance:root",),
    )
    forged_verified = GoalRevisionHistoryEntry(
        goal_id="goal:public-authority",
        ordinal=1,
        contract_digest="contract:forged-successor",
        predecessor_digest=root.contract_digest,
        trust_label=VERIFIED_CAPABILITY_AUTHORITY_TRUST,
        evolution_receipt_id=None,
        delta_digest=None,
        source_refs=(),
        evidence_refs=(),
        freshness_ref=None,
        confidence_milli=None,
        previous_entry_digest=root.entry_digest,
    )
    snapshot = GoalRevisionHistorySnapshot(
        capability=capability,
        goal_id="goal:public-authority",
        current_contract_digest=forged_verified.contract_digest,
        entries=(root, forged_verified),
    )
    receipt = GoalRevisionHistoryReceipt(
        protocol_major=capability.major,
        protocol_minor=capability.minor,
        goal_id=snapshot.goal_id,
        history_digest=snapshot.history_digest,
        current_contract_digest=snapshot.current_contract_digest,
        entry_count=len(snapshot.entries),
    )
    export = GoalRevisionHistoryExport(snapshot=snapshot, receipt=receipt)

    with pytest.raises(ValueError, match="trust|authority|receipt|provenance"):
        verify_goal_revision_history_export(export)
