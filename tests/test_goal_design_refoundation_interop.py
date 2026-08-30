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
