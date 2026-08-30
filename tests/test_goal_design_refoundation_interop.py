from nolane.external_core.evidence_truth import EvidenceChannel, EvidencePolarity, TruthEvidence
from nolane.external_core.goal_design import (
    DecisionClass,
    DesignOption,
    DesignScenario,
    GoalDesignCoherencePlane,
    GoalDesignVersionVector,
    GoalObjective,
    GoalSpec,
    ObjectiveDirection,
    TraceabilityState,
)
from nolane.external_core.software_engineering import EngineeringEvidenceKind, EngineeringEvidenceLedger


def _truth_evidence(payload_digest: str) -> TruthEvidence:
    return TruthEvidence.create(
        evidence_id="evidence:goal-design-interop",
        subject_id="goal:refoundation-interop",
        source_id="source:truth-knowledge-a",
        source_family="truth-knowledge-a",
        channel=EvidenceChannel.AUDIT,
        polarity=EvidencePolarity.SUPPORT,
        payload_digest=payload_digest,
    )


def _admit(evidence_ref: str):
    authority = GoalDesignCoherencePlane()
    vector = GoalDesignVersionVector("r1", "p1", "a1", "i1", "c1")
    snapshot = authority.freeze_snapshot(vector)
    goal = GoalSpec(
        goal_id="goal:refoundation-interop",
        statement="Preserve truth provenance across Goal/Design authority admission",
        objectives=(GoalObjective("quality", ObjectiveDirection.MAXIMIZE),),
        constraints=("do not collapse Truth/Knowledge authority into Goal/Design",),
        evidence_refs=(evidence_ref,),
    )
    scenarios = (
        DesignScenario("base", 1.0, tags=("baseline",), evidence_refs=(evidence_ref,)),
    )
    options = (
        DesignOption(
            "selected",
            "Federated authority composition",
            {"base": 0.9},
            {"quality": 0.9},
            decision_class=DecisionClass.REVERSIBLE,
            evidence_refs=(evidence_ref,),
            requirement_refs=("req:1",),
            component_refs=("cmp:1",),
        ),
    )
    traceability = TraceabilityState(
        active_requirement_ids=("req:1",),
        planned_requirement_ids=("req:1",),
        architecture_component_ids=("cmp:1",),
        integration_component_refs=("cmp:1",),
    )
    return authority.admit_decision(
        goal=goal,
        scenarios=scenarios,
        options=options,
        selected_option_id="selected",
        snapshot=snapshot,
        current_vector=vector,
        traceability=traceability,
    )


def _engineering_attestation(receipt):
    ledger = EngineeringEvidenceLedger()
    return ledger.record(
        subject_ref=receipt.receipt_id,
        subject_digest=receipt.input_manifest_digest,
        producer_agent_id="agent:goal-design",
        verifier_agent_id="agent:verification",
        verifier_region="verification-testing",
        kind=EngineeringEvidenceKind.REVIEW,
        passed=True,
        evidence_refs=receipt.evidence_refs,
        source_revision=receipt.snapshot_digest,
        environment_digest="environment:goal-design-refoundation-interop",
    )


def test_truth_knowledge_content_identity_flows_into_goal_design_receipt():
    evidence = _truth_evidence("payload:a")
    receipt = _admit(evidence.content_digest)

    assert evidence.content_digest in receipt.evidence_refs
    assert receipt.goal_digest
    assert receipt.input_manifest_digest


def test_truth_knowledge_content_change_changes_goal_design_authority_identity():
    first = _truth_evidence("payload:a")
    second = _truth_evidence("payload:b")

    first_receipt = _admit(first.content_digest)
    second_receipt = _admit(second.content_digest)

    assert first.content_digest != second.content_digest
    assert first_receipt.goal_digest != second_receipt.goal_digest
    assert first_receipt.receipt_id != second_receipt.receipt_id


def test_software_engineering_attests_goal_design_manifest_without_rebinding_it():
    receipt = _admit(_truth_evidence("payload:a").content_digest)
    attestation = _engineering_attestation(receipt)

    assert attestation.subject_ref == receipt.receipt_id
    assert attestation.subject_digest == receipt.input_manifest_digest
    assert attestation.passed is True


def test_goal_design_manifest_change_propagates_into_engineering_evidence_identity():
    first_receipt = _admit(_truth_evidence("payload:a").content_digest)
    second_receipt = _admit(_truth_evidence("payload:b").content_digest)

    first_attestation = _engineering_attestation(first_receipt)
    second_attestation = _engineering_attestation(second_receipt)

    assert first_receipt.input_manifest_digest != second_receipt.input_manifest_digest
    assert first_attestation.subject_digest != second_attestation.subject_digest
    assert first_attestation.digest != second_attestation.digest
