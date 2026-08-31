from __future__ import annotations

from copy import deepcopy

import pytest

import nolane.external_core.assurance_justification_truth as assurance_v6
import nolane.external_core.epistemic_justification_truth as epistemic_v6
import nolane.external_core.knowledge_justification_truth as knowledge_v6
import nolane.external_core.verification_justification_truth as verification_v6
from nolane.external_core.epistemic_justification_truth import JustificationEpistemicJudge
from nolane.external_core.epistemic_provenance_truth import ProvenanceEpistemicJudge
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
from nolane.external_core.temporal_truth import TemporalContext
from nolane.memory.knowledge import RelationSemanticsRegistry


AS_OF = "2026-08-31T00:00:00Z"


def _state():
    knowledge = KnowledgeLedger()
    evidence = EvidenceLedger()
    relation_semantics = RelationSemanticsRegistry()
    knowledge_temporal = TemporalKnowledgeView()
    evidence_temporal = TemporalEvidenceView()
    provenance = SourceProvenanceRegistry()
    justifications = KnowledgeJustificationRegistry()
    context = TemporalContext.create(as_of=AS_OF)

    evidence.record(
        TruthEvidence.create(
            evidence_id="e-root",
            subject_id="claim-root",
            source_id="source-root",
            source_family="legacy-label",
            channel=EvidenceChannel.OBSERVATION,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest="payload-root",
        )
    )
    provenance.register(
        SourceProvenanceRevision.create(
            source_id="source-root",
            revision=1,
            predecessor_digest="",
            controller_id="controller-root",
            parent_source_ids=(),
        )
    )
    claim = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim-root",
            subject="system",
            relation="state",
            object="ok",
            evidence_ids=("e-root",),
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
        "context": context,
        "claim": claim,
    }


def test_a12_sidecars_preserve_exact_family_a_authority_ownership():
    modules = (
        (knowledge_v6, "external.knowledge", "truth-knowledge-justification-v6"),
        (epistemic_v6, "external.epistemic", "truth-justification-provenance-lineage-temporal-scope-v6"),
        (verification_v6, "external.verification", "truth-verification-justification-provenance-lineage-temporal-v6"),
        (assurance_v6, "external.assurance", "truth-assurance-justification-provenance-lineage-temporal-v6"),
    )
    for module, parent, protocol in modules:
        assert module.PARENT_COMPONENT_ID == parent
        assert module.TRUTH_PROTOCOL == protocol
        assert not hasattr(module, "COMPONENT_ID")
    assert epistemic_v6.JUSTIFICATION_BINDING_MODE == "justification-provenance-lineage-temporal-v6"
    assert verification_v6.JUSTIFICATION_BINDING_MODE == "justification-provenance-lineage-temporal-v6"


def test_a12_without_explicit_justifications_preserves_a11_epistemic_semantics():
    state = _state()
    legacy = ProvenanceEpistemicJudge().relation_aware_temporal_scope(
        state["claim"].claim_id,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["relation_semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
    )
    v6 = JustificationEpistemicJudge().relation_aware_temporal_scope(
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

    assert v6.lineage_claim_ids == legacy.temporal_scope.lineage_claim_ids
    assert v6.scope_claim_ids == legacy.temporal_scope.scope_claim_ids
    assert v6.evidence_ids == legacy.temporal_scope.evidence_ids
    assert v6.source_ids == legacy.source_ids
    assert v6.assessment("claim-root") == legacy.temporal_scope.assessment("claim-root")


def test_a12_scope_and_revision_are_protocol_domain_separated():
    state = _state()
    scope = JustificationEpistemicJudge().relation_aware_temporal_scope(
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
    forged_scope = deepcopy(scope.to_state())
    forged_scope["binding_mode"] = "provenance-lineage-temporal-v5"
    with pytest.raises(ValueError, match="unsupported justification epistemic binding mode"):
        epistemic_v6.JustificationTruthScope.from_state(forged_scope)

    revision = KnowledgeJustificationRevision.create(
        justification_id="j-domain",
        claim=state["claim"],
        evidence_ids=(),
        parent_claim_ids=(),
        enabled=False,
    )
    serialized = revision.to_state()
    assert serialized["protocol"] == knowledge_v6.TRUTH_PROTOCOL
    forged_revision = deepcopy(serialized)
    forged_revision["protocol"] = "truth-knowledge-v1"
    with pytest.raises(ValueError, match="unsupported knowledge justification protocol"):
        KnowledgeJustificationRevision.from_state(forged_revision)


def test_a12_justification_lineage_cannot_rebind_to_another_claim():
    state = _state()
    first = state["justifications"].register(
        KnowledgeJustificationRevision.create(
            justification_id="j-bound",
            claim=state["claim"],
            evidence_ids=(),
            enabled=False,
        ),
        knowledge=state["knowledge"],
    )
    other = state["knowledge"].add(
        KnowledgeClaim.create(
            claim_id="claim-other",
            subject="other",
            relation="state",
            object="ok",
        )
    )
    rebound = KnowledgeJustificationRevision.create(
        justification_id="j-bound",
        claim=other,
        revision=2,
        predecessor_digest=first.digest,
        enabled=False,
    )
    with pytest.raises(ValueError, match="cannot rebind"):
        state["justifications"].register(rebound, knowledge=state["knowledge"])
