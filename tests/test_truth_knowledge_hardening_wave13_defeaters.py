from __future__ import annotations

from copy import deepcopy

import pytest

from nolane.external_core.epistemic_defeasible_truth import (
    DEFEASIBLE_BINDING_MODE,
    DefeasibleEpistemicJudge,
)
from nolane.external_core.epistemic_justification_truth import JustificationEpistemicJudge
from nolane.external_core.epistemic_truth import EpistemicDisposition
from nolane.external_core.evidence_provenance_truth import (
    SourceProvenanceRegistry,
    SourceProvenanceRevision,
)
from nolane.external_core.evidence_temporal_truth import TemporalEvidenceView
from nolane.external_core.evidence_truth import (
    EvidenceChannel,
    EvidenceLedger,
    EvidencePolarity,
    TruthEvidence,
)
from nolane.external_core.knowledge_justification_truth import (
    KnowledgeJustificationRegistry,
    KnowledgeJustificationRevision,
)
from nolane.external_core.knowledge_temporal_truth import TemporalKnowledgeView
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger
from nolane.external_core.knowledge_undercutter_truth import (
    JustificationUndercutterRegistry,
    JustificationUndercutterRevision,
)
from nolane.external_core.temporal_truth import TemporalContext
from nolane.memory.knowledge import RelationSemanticsRegistry


AS_OF = "2026-08-31T00:00:00Z"


def _provenance(source_id: str, controller_id: str) -> SourceProvenanceRevision:
    return SourceProvenanceRevision.create(
        source_id=source_id,
        revision=1,
        predecessor_digest="",
        controller_id=controller_id,
        parent_source_ids=(),
    )


def _record(
    ledger: EvidenceLedger,
    *,
    evidence_id: str,
    subject_id: str,
    source_id: str,
    polarity: EvidencePolarity = EvidencePolarity.SUPPORT,
    channel: EvidenceChannel = EvidenceChannel.OBSERVATION,
) -> None:
    ledger.record(
        TruthEvidence.create(
            evidence_id=evidence_id,
            subject_id=subject_id,
            source_id=source_id,
            source_family=f"legacy-family:{source_id}",
            channel=channel,
            polarity=polarity,
            payload_digest=f"payload:{evidence_id}",
        )
    )


def _register_source(state, source_id: str, controller_id: str | None = None) -> None:
    state["provenance"].register(_provenance(source_id, controller_id or f"controller:{source_id}"))


def _base_state():
    knowledge = KnowledgeLedger()
    evidence = EvidenceLedger()
    relation_semantics = RelationSemanticsRegistry()
    knowledge_temporal = TemporalKnowledgeView()
    evidence_temporal = TemporalEvidenceView()
    provenance = SourceProvenanceRegistry()
    justifications = KnowledgeJustificationRegistry()
    undercutters = JustificationUndercutterRegistry()
    context = TemporalContext.create(as_of=AS_OF)

    _record(
        evidence,
        evidence_id="claim-support",
        subject_id="claim-a13",
        source_id="claim-source",
    )
    _record(
        evidence,
        evidence_id="undercutter-support",
        subject_id="u-invalid-method",
        source_id="undercutter-source",
    )
    provenance.register(_provenance("claim-source", "claim-controller"))
    provenance.register(_provenance("undercutter-source", "undercutter-controller"))

    claim = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim-a13",
            subject="system",
            relation="is_valid",
            object="yes",
            evidence_ids=("claim-support",),
        )
    )
    return {
        "knowledge": knowledge,
        "evidence": evidence,
        "relation_semantics": relation_semantics,
        "knowledge_temporal": knowledge_temporal,
        "evidence_temporal": evidence_temporal,
        "provenance": provenance,
        "justifications": justifications,
        "undercutters": undercutters,
        "context": context,
        "claim": claim,
    }


def _scope(state):
    return DefeasibleEpistemicJudge().relation_aware_temporal_scope(
        state["claim"].claim_id,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["relation_semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
        undercutters=state["undercutters"],
    )


def _v6_scope(state):
    return JustificationEpistemicJudge().relation_aware_temporal_scope(
        state["claim"].claim_id,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["relation_semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
    )


def _register_attack(
    state,
    *,
    undercutter_id: str = "u-invalid-method",
    target_basis=None,
    evidence_ids=("undercutter-support",),
    parent_claim_ids=(),
):
    target_basis = target_basis or state["justifications"].legacy_basis(state["claim"])
    row = JustificationUndercutterRevision.create(
        undercutter_id=undercutter_id,
        claim=state["claim"],
        target_basis=target_basis,
        evidence_ids=evidence_ids,
        parent_claim_ids=parent_claim_ids,
    )
    return state["undercutters"].register(
        row,
        knowledge=state["knowledge"],
        justifications=state["justifications"],
    )


def test_a13_supported_undercutter_defeats_exact_legacy_basis():
    state = _base_state()
    legacy = state["justifications"].legacy_basis(state["claim"])
    _register_attack(state, target_basis=legacy)

    scope = _scope(state)

    assert scope.binding_mode == DEFEASIBLE_BINDING_MODE
    assert scope.undercutter_status("u-invalid-method").status == "supported"
    assert scope.justification_status(legacy.justification_id).intrinsic_status == "supported"
    assert scope.justification_status(legacy.justification_id).status == "defeated"
    assert scope.assessment(state["claim"].claim_id).disposition is EpistemicDisposition.UNKNOWN


def test_a13_clean_alternative_survives_defeated_legacy_basis():
    state = _base_state()
    _record(
        state["evidence"],
        evidence_id="alternate-support",
        subject_id=state["claim"].claim_id,
        source_id="alternate-source",
    )
    _register_source(state, "alternate-source")
    alt = state["justifications"].register(
        KnowledgeJustificationRevision.create(
            justification_id="j-alt",
            claim=state["claim"],
            evidence_ids=("alternate-support",),
        ),
        knowledge=state["knowledge"],
    )
    _register_attack(state)

    scope = _scope(state)

    assert scope.justification_status(scope.justification_status("j-alt").justification_id).status == "supported"
    assert scope.justification_status(state["justifications"].legacy_basis(state["claim"]).justification_id).status == "defeated"
    assert scope.assessment(state["claim"].claim_id).disposition is EpistemicDisposition.SUPPORTED
    assert alt.digest


def test_a13_refuted_undercutter_cannot_defeat_supported_path():
    state = _base_state()
    _record(
        state["evidence"],
        evidence_id="undercutter-refute",
        subject_id="u-invalid-method",
        source_id="undercutter-refuter",
        polarity=EvidencePolarity.REFUTE,
    )
    _register_source(state, "undercutter-refuter")
    _register_attack(state, evidence_ids=("undercutter-refute",))

    scope = _scope(state)
    legacy_id = state["justifications"].legacy_basis(state["claim"]).justification_id

    assert scope.undercutter_status("u-invalid-method").status == "refuted"
    assert scope.justification_status(legacy_id).status == "supported"
    assert scope.assessment(state["claim"].claim_id).disposition is EpistemicDisposition.SUPPORTED
    assert "undercutter-refuter" in scope.decision_source_ids


def test_a13_contradicted_undercutter_contests_path_instead_of_defeating_it():
    state = _base_state()
    _record(
        state["evidence"],
        evidence_id="undercutter-refute",
        subject_id="u-invalid-method",
        source_id="undercutter-refuter",
        polarity=EvidencePolarity.REFUTE,
    )
    _register_source(state, "undercutter-refuter")
    _register_attack(
        state,
        evidence_ids=("undercutter-support", "undercutter-refute"),
    )

    scope = _scope(state)
    legacy_id = state["justifications"].legacy_basis(state["claim"]).justification_id

    assert scope.undercutter_status("u-invalid-method").status == "contradicted"
    assert scope.justification_status(legacy_id).status == "contested"
    assert scope.assessment(state["claim"].claim_id).disposition is EpistemicDisposition.UNKNOWN
    assert any(row.reason == "undercutter_contradicted" for row in scope.debts)


def test_a13_unknown_undercutter_is_auditable_but_cannot_attack_spam_dos_support():
    state = _base_state()
    _record(
        state["evidence"],
        evidence_id="undercutter-neutral",
        subject_id="u-invalid-method",
        source_id="neutral-source",
        polarity=EvidencePolarity.NEUTRAL,
    )
    _register_source(state, "neutral-source")
    _register_attack(state, evidence_ids=("undercutter-neutral",))

    scope = _scope(state)
    legacy_id = state["justifications"].legacy_basis(state["claim"]).justification_id

    assert scope.undercutter_status("u-invalid-method").status == "unknown"
    assert scope.justification_status(legacy_id).status == "supported"
    assert scope.assessment(state["claim"].claim_id).disposition is EpistemicDisposition.SUPPORTED
    assert any(row.reason == "undercutter_unknown" for row in scope.debts)
    assert "neutral-source" not in scope.decision_source_ids


def test_a13_empty_attack_basis_and_revision_attacks_fail_closed():
    state = _base_state()
    legacy = state["justifications"].legacy_basis(state["claim"])
    with pytest.raises(ValueError, match="must contain evidence or parent claims"):
        JustificationUndercutterRevision.create(
            undercutter_id="u-empty",
            claim=state["claim"],
            target_basis=legacy,
        )

    first = _register_attack(state)
    with pytest.raises(ValueError, match="predecessor"):
        state["undercutters"].register(
            JustificationUndercutterRevision.create(
                undercutter_id="u-invalid-method",
                claim=state["claim"],
                target_basis=legacy,
                revision=2,
                predecessor_digest="forged",
                evidence_ids=("undercutter-support",),
            ),
            knowledge=state["knowledge"],
            justifications=state["justifications"],
        )
    with pytest.raises(ValueError, match="advance exactly once"):
        state["undercutters"].register(
            JustificationUndercutterRevision.create(
                undercutter_id="u-invalid-method",
                claim=state["claim"],
                target_basis=legacy,
                revision=3,
                predecessor_digest=first.digest,
                evidence_ids=("undercutter-support",),
            ),
            knowledge=state["knowledge"],
            justifications=state["justifications"],
        )


def test_a13_undercutter_lineage_cannot_rebind_another_exact_basis():
    state = _base_state()
    _record(
        state["evidence"],
        evidence_id="alternate-support",
        subject_id=state["claim"].claim_id,
        source_id="alternate-source",
    )
    _register_source(state, "alternate-source")
    alt = state["justifications"].register(
        KnowledgeJustificationRevision.create(
            justification_id="j-alt",
            claim=state["claim"],
            evidence_ids=("alternate-support",),
        ),
        knowledge=state["knowledge"],
    )
    first = _register_attack(state)
    alt_basis = alt.basis()

    with pytest.raises(ValueError, match="cannot rebind target basis"):
        state["undercutters"].register(
            JustificationUndercutterRevision.create(
                undercutter_id="u-invalid-method",
                claim=state["claim"],
                target_basis=alt_basis,
                revision=2,
                predecessor_digest=first.digest,
                evidence_ids=("undercutter-support",),
            ),
            knowledge=state["knowledge"],
            justifications=state["justifications"],
        )


def test_a13_combined_justification_and_undercutter_dependency_cycle_fails_closed():
    state = _base_state()
    claim_b = state["knowledge"].add(
        KnowledgeClaim.create(
            claim_id="claim-b",
            subject="system-b",
            relation="valid",
            object="yes",
        )
    )
    state["justifications"].register(
        KnowledgeJustificationRevision.create(
            justification_id="j-b-via-a",
            claim=claim_b,
            parent_claim_ids=(state["claim"].claim_id,),
        ),
        knowledge=state["knowledge"],
    )
    legacy = state["justifications"].legacy_basis(state["claim"])

    with pytest.raises(ValueError, match="cycle"):
        state["undercutters"].register(
            JustificationUndercutterRevision.create(
                undercutter_id="u-cycle",
                claim=state["claim"],
                target_basis=legacy,
                parent_claim_ids=(claim_b.claim_id,),
            ),
            knowledge=state["knowledge"],
            justifications=state["justifications"],
        )


def test_a13_undercutter_parent_lineage_enters_scope_and_controls_attack_liveness():
    state = _base_state()
    _record(
        state["evidence"],
        evidence_id="parent-support",
        subject_id="claim-parent",
        source_id="parent-source",
    )
    _register_source(state, "parent-source")
    parent = state["knowledge"].add(
        KnowledgeClaim.create(
            claim_id="claim-parent",
            subject="method",
            relation="is_invalid",
            object="yes",
            evidence_ids=("parent-support",),
        )
    )
    _register_attack(state, parent_claim_ids=(parent.claim_id,))

    scope = _scope(state)
    assert parent.claim_id in scope.scope_claim_ids
    assert scope.undercutter_status("u-invalid-method").status == "supported"

    state["evidence"].revoke("parent-support", reason="parent support withdrawn")
    changed = _scope(state)
    assert changed.undercutter_status("u-invalid-method").status == "dead"
    assert changed.assessment(state["claim"].claim_id).disposition is EpistemicDisposition.SUPPORTED


def test_a13_stale_exact_basis_attack_does_not_follow_revised_justification():
    state = _base_state()
    _record(
        state["evidence"],
        evidence_id="alternate-support-1",
        subject_id=state["claim"].claim_id,
        source_id="alternate-source-1",
    )
    _record(
        state["evidence"],
        evidence_id="alternate-support-2",
        subject_id=state["claim"].claim_id,
        source_id="alternate-source-2",
    )
    _record(
        state["evidence"],
        evidence_id="u-revisable-support",
        subject_id="u-revisable",
        source_id="u-revisable-source",
    )
    _register_source(state, "alternate-source-1")
    _register_source(state, "alternate-source-2")
    _register_source(state, "u-revisable-source")
    first = state["justifications"].register(
        KnowledgeJustificationRevision.create(
            justification_id="j-revisable",
            claim=state["claim"],
            evidence_ids=("alternate-support-1",),
        ),
        knowledge=state["knowledge"],
    )
    _register_attack(
        state,
        undercutter_id="u-revisable",
        target_basis=first.basis(),
        evidence_ids=("u-revisable-support",),
    )
    state["evidence"].revoke("claim-support", reason="force explicit path")

    before = _scope(state)
    assert before.justification_status("j-revisable").status == "defeated"
    assert before.assessment(state["claim"].claim_id).disposition is EpistemicDisposition.UNKNOWN

    state["justifications"].register(
        KnowledgeJustificationRevision.create(
            justification_id="j-revisable",
            claim=state["claim"],
            revision=2,
            predecessor_digest=first.digest,
            evidence_ids=("alternate-support-2",),
        ),
        knowledge=state["knowledge"],
    )
    after = _scope(state)

    assert after.digest != before.digest
    assert after.justification_status("j-revisable").status == "supported"
    assert after.assessment(state["claim"].claim_id).disposition is EpistemicDisposition.SUPPORTED
    with pytest.raises(KeyError, match="undercutter missing"):
        after.undercutter_status("u-revisable")


def test_a13_projection_is_relevant_only_and_restore_is_domain_separated():
    state = _base_state()
    first = _register_attack(state)
    before = state["undercutters"].projection_digest(
        (state["claim"].claim_id,),
        knowledge=state["knowledge"],
    )

    unrelated = state["knowledge"].add(
        KnowledgeClaim.create(
            claim_id="claim-unrelated",
            subject="other",
            relation="state",
            object="ok",
        )
    )
    unrelated_basis = state["justifications"].legacy_basis(unrelated)
    state["undercutters"].register(
        JustificationUndercutterRevision.create(
            undercutter_id="u-unrelated",
            claim=unrelated,
            target_basis=unrelated_basis,
            parent_claim_ids=(state["claim"].claim_id,),
        ),
        knowledge=state["knowledge"],
        justifications=state["justifications"],
    )
    assert state["undercutters"].projection_digest(
        (state["claim"].claim_id,),
        knowledge=state["knowledge"],
    ) == before

    state["undercutters"].register(
        JustificationUndercutterRevision.create(
            undercutter_id="u-invalid-method",
            claim=state["claim"],
            target_basis=state["justifications"].legacy_basis(state["claim"]),
            revision=2,
            predecessor_digest=first.digest,
            evidence_ids=("undercutter-support",),
            enabled=False,
        ),
        knowledge=state["knowledge"],
        justifications=state["justifications"],
    )
    assert state["undercutters"].projection_digest(
        (state["claim"].claim_id,),
        knowledge=state["knowledge"],
    ) != before

    serialized = state["undercutters"].to_state()
    forged = deepcopy(serialized)
    forged["protocol"] = "another-domain"
    with pytest.raises(ValueError, match="unsupported knowledge undercutter protocol"):
        JustificationUndercutterRegistry.from_state(
            forged,
            knowledge=state["knowledge"],
            justifications=state["justifications"],
        )

    duplicated = deepcopy(serialized)
    duplicated["revisions"].append(deepcopy(duplicated["revisions"][0]))
    with pytest.raises(ValueError, match="duplicate serialized undercutter revision"):
        JustificationUndercutterRegistry.from_state(
            duplicated,
            knowledge=state["knowledge"],
            justifications=state["justifications"],
        )


def test_a13_without_undercutters_preserves_a12_epistemic_disposition():
    state = _base_state()

    v6 = _v6_scope(state)
    v7 = _scope(state)
    legacy_id = state["justifications"].legacy_basis(state["claim"]).justification_id

    assert v7.assessment(state["claim"].claim_id).disposition is v6.assessment(state["claim"].claim_id).disposition
    assert v7.justification_status(legacy_id).intrinsic_status == v6.justification_status(legacy_id).status
    assert v7.justification_status(legacy_id).status == v6.justification_status(legacy_id).status
    assert v7.undercutter_statuses == ()
