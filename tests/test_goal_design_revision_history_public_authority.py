import pytest

from nolane.external_core.goal_design_integrity_runtime import (
    VERIFIED_CAPABILITY_AUTHORITY_TRUST,
)
from nolane.external_core.goal_design_revision_history import (
    GOAL_REVISION_HISTORY_PROTOCOL,
    ROOT_INTEGRITY_CONTRACT_TRUST,
    GoalRevisionHistoryCapability,
    GoalRevisionHistoryEntry,
    GoalRevisionHistoryExport,
    GoalRevisionHistoryReceipt,
    GoalRevisionHistorySnapshot,
    verify_goal_revision_history_export,
)


_GOAL_ID = "goal:public-authority"


def _root(*, trust_label=ROOT_INTEGRITY_CONTRACT_TRUST, capability=None):
    capability = capability or GoalRevisionHistoryCapability()
    root = GoalRevisionHistoryEntry(
        goal_id=_GOAL_ID,
        ordinal=0,
        contract_digest="contract:root",
        trust_label=trust_label,
        source_refs=("provenance:root",),
    )
    snapshot = GoalRevisionHistorySnapshot(
        capability=capability,
        goal_id=_GOAL_ID,
        current_contract_digest=root.contract_digest,
        entries=(root,),
    )
    receipt = GoalRevisionHistoryReceipt(
        protocol_major=capability.major,
        protocol_minor=capability.minor,
        goal_id=snapshot.goal_id,
        history_digest=snapshot.history_digest,
        current_contract_digest=snapshot.current_contract_digest,
        entry_count=len(snapshot.entries),
    )
    return root, snapshot, receipt


def _export_with_successor(successor):
    capability = GoalRevisionHistoryCapability()
    root = GoalRevisionHistoryEntry(
        goal_id=_GOAL_ID,
        ordinal=0,
        contract_digest="contract:root",
        trust_label=ROOT_INTEGRITY_CONTRACT_TRUST,
        source_refs=("provenance:root",),
    )
    successor = successor(root)
    snapshot = GoalRevisionHistorySnapshot(
        capability=capability,
        goal_id=_GOAL_ID,
        current_contract_digest=successor.contract_digest,
        entries=(root, successor),
    )
    receipt = GoalRevisionHistoryReceipt(
        protocol_major=capability.major,
        protocol_minor=capability.minor,
        goal_id=snapshot.goal_id,
        history_digest=snapshot.history_digest,
        current_contract_digest=snapshot.current_contract_digest,
        entry_count=len(snapshot.entries),
    )
    return GoalRevisionHistoryExport(snapshot=snapshot, receipt=receipt)


def test_public_verifier_rejects_self_consistent_verified_trust_without_revision_authority():
    export = _export_with_successor(
        lambda root: GoalRevisionHistoryEntry(
            goal_id=_GOAL_ID,
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
    )

    with pytest.raises(ValueError, match="trust|authority|receipt|provenance"):
        verify_goal_revision_history_export(export)


def test_public_verifier_rejects_root_that_spoofs_revision_trust():
    root, snapshot, receipt = _root(trust_label=VERIFIED_CAPABILITY_AUTHORITY_TRUST)
    export = GoalRevisionHistoryExport(snapshot=snapshot, receipt=receipt)

    assert root.ordinal == 0
    with pytest.raises(ValueError, match="root|trust|authority"):
        verify_goal_revision_history_export(export)


def test_public_verifier_rejects_receipted_verified_revision_missing_evidence_contract():
    export = _export_with_successor(
        lambda root: GoalRevisionHistoryEntry(
            goal_id=_GOAL_ID,
            ordinal=1,
            contract_digest="contract:forged-receipted-successor",
            predecessor_digest=root.contract_digest,
            trust_label=VERIFIED_CAPABILITY_AUTHORITY_TRUST,
            evolution_receipt_id="receipt:forged",
            delta_digest="delta:forged",
            source_refs=(),
            evidence_refs=(),
            freshness_ref=None,
            confidence_milli=None,
            previous_entry_digest=root.entry_digest,
        )
    )

    with pytest.raises(ValueError, match="evidence|freshness|confidence|provenance|receipt"):
        verify_goal_revision_history_export(export)


def test_public_verifier_rejects_self_consistent_unsupported_protocol_capability():
    capability = GoalRevisionHistoryCapability(
        protocol_name=f"{GOAL_REVISION_HISTORY_PROTOCOL}.forged",
        major=99,
        minor=0,
    )
    _, snapshot, receipt = _root(capability=capability)
    export = GoalRevisionHistoryExport(snapshot=snapshot, receipt=receipt)

    with pytest.raises(ValueError, match="protocol|capability|major"):
        verify_goal_revision_history_export(export)
