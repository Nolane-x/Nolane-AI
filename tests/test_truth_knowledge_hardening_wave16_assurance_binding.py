from __future__ import annotations

from nolane.external_core import assurance_observation_truth
from nolane.external_core.assurance_observation_truth import ObservationTruthClosureCertificate
from nolane.external_core.epistemic_observation_truth import OBSERVATION_BINDING_MODE
from nolane.external_core.knowledge_context_truth import TruthContext
from nolane.external_core.knowledge_truth import KnowledgeRisk
from nolane.external_core.temporal_truth import TemporalContext


AS_OF = "2026-09-01T00:00:00Z"


def test_a16_assurance_sidecar_preserves_authority_and_binds_observation_projection():
    temporal = TemporalContext.create(as_of=AS_OF)
    truth_context = TruthContext.create()
    certificate = ObservationTruthClosureCertificate.create(
        claim_id="claim-binding-v10",
        risk=KnowledgeRisk.STANDARD,
        scope_digest="scope:v10",
        verification_scope_digest="verification:v10",
        truth_context_digest=truth_context.digest,
        temporal_context_digest=temporal.digest,
        as_of=temporal.as_of,
        observation_requirement_digest="requirements:v10",
        observation_result_digest="results:v10",
        verification_receipt_ids=(),
        epistemic_debt_ids=(),
        closed=False,
        reasons=("proof_only",),
    )
    assert assurance_observation_truth.PARENT_COMPONENT_ID == "external.assurance"
    assert not hasattr(assurance_observation_truth, "COMPONENT_ID")
    assert certificate.binding_mode == OBSERVATION_BINDING_MODE
    assert certificate.observation_requirement_digest == "requirements:v10"
    assert certificate.observation_result_digest == "results:v10"
    assert ObservationTruthClosureCertificate.from_state(certificate.to_state()) == certificate
