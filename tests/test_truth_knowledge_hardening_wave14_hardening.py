from __future__ import annotations

import pytest

from nolane.external_core.assurance_defeasible_truth import DefeasibleTruthClosureCertificate
from nolane.external_core.assurance_dependence_truth import DependenceTruthClosureCertificate
from nolane.external_core.evidence_dependence_truth import (
    SourceDependenceRegistry,
    SourceDependenceRevision,
)
from nolane.external_core.evidence_provenance_truth import (
    SourceProvenanceRegistry,
    SourceProvenanceRevision,
)
from nolane.external_core.evidence_truth import EvidenceChannel
from nolane.external_core.knowledge_truth import KnowledgeRisk
from nolane.external_core.temporal_truth import TemporalContext
from nolane.external_core.verification_dependence_truth import (
    DependenceTruthVerificationLedger,
    DependenceTruthVerificationReceipt,
)


AS_OF = "2026-08-31T00:00:00Z"


def _receipt(receipt_id: str, verifier_id: str, channel: EvidenceChannel):
    context = TemporalContext.create(as_of=AS_OF)
    return DependenceTruthVerificationReceipt.create(
        receipt_id=receipt_id,
        claim_id="claim-v8",
        verifier_id=verifier_id,
        channel=channel,
        passed=True,
        scope_digest="scope:v8",
        temporal_context_digest=context.digest,
        as_of=context.as_of,
        evidence_ids=(f"evidence:{verifier_id}",),
        source_provenance_digest=f"provenance:{verifier_id}",
        source_dependence_digest=f"dependence:{verifier_id}",
    )


def test_a14_same_controller_still_collapses_even_when_basis_sets_are_disjoint():
    provenance = SourceProvenanceRegistry()
    dependence = SourceDependenceRegistry()
    for verifier_id, basis in (("v-a", "basis:a"), ("v-b", "basis:b")):
        provenance.register(
            SourceProvenanceRevision.create(
                source_id=verifier_id,
                revision=1,
                controller_id="shared-controller",
                parent_source_ids=(),
            )
        )
        dependence.register(
            SourceDependenceRevision.create(
                source_id=verifier_id,
                revision=1,
                basis_ids=(basis,),
            )
        )

    keys = DependenceTruthVerificationLedger._component_keys(
        (
            _receipt("r-a", "v-a", EvidenceChannel.TEST),
            _receipt("r-b", "v-b", EvidenceChannel.REPRODUCTION),
        ),
        source_provenance=provenance,
        source_dependence=dependence,
    )
    assert len(keys) == 1


def test_a14_v7_closure_certificate_cannot_masquerade_as_v8():
    context = TemporalContext.create(as_of=AS_OF)
    old = DefeasibleTruthClosureCertificate.create(
        claim_id="claim-v7",
        risk=KnowledgeRisk.STANDARD,
        scope_digest="scope:v7",
        verification_scope_digest="verification:v7",
        temporal_context_digest=context.digest,
        as_of=context.as_of,
        verification_receipt_ids=(),
        epistemic_debt_ids=(),
        closed=False,
        reasons=("historical-v7",),
    )
    with pytest.raises(ValueError, match="unsupported dependence assurance protocol"):
        DependenceTruthClosureCertificate.from_state(old.to_state())
