from __future__ import annotations

from types import SimpleNamespace

from nolane.external_core.evidence import EvidenceRecord
from nolane.external_core.self_model import SelfModelRegistry
from nolane.memory.learning_authority import LearningEvidenceAuthority


class _Registry:
    def __init__(self) -> None:
        self._rows = {
            agent_id: SimpleNamespace(agent_id=agent_id, self_model_version="self-model-0.1")
            for agent_id in ("agent-alpha", "agent-beta", "verifier")
        }
        self.updated: dict[str, str] = {}

    def identities(self):
        return tuple(self._rows[key] for key in sorted(self._rows))

    def get(self, agent_id: str):
        return self._rows[str(agent_id)]

    def set_self_model_version(self, agent_id: str, version: str) -> None:
        self.get(agent_id)
        self.updated[str(agent_id)] = str(version)


def _evidence(evidence_id: str) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id,
        "verifier",
        True,
        false_accepts=0,
        regressions=0,
        notes="independent self-model verification",
    )


def test_shared_authority_does_not_confuse_same_revision_number_across_agents() -> None:
    authority = LearningEvidenceAuthority()
    models = SelfModelRegistry(_Registry(), learning_authority=authority)

    evidence_alpha = _evidence("evidence-alpha")
    evidence_beta = _evidence("evidence-beta")
    lease_alpha = authority.issue(
        subject_kind="self_model",
        subject_id="agent-alpha",
        operation_class="self_model.update_competence",
        producer_agent_id="agent-alpha",
        evidence=evidence_alpha,
        subject_digest=models.competence_subject_digest(
            "agent-alpha", domain="reasoning", score=0.7
        ),
    )
    lease_beta = authority.issue(
        subject_kind="self_model",
        subject_id="agent-beta",
        operation_class="self_model.update_competence",
        producer_agent_id="agent-beta",
        evidence=evidence_beta,
        subject_digest=models.competence_subject_digest(
            "agent-beta", domain="reasoning", score=0.7
        ),
    )

    alpha = models.update_competence(
        "agent-alpha",
        domain="reasoning",
        score=0.7,
        evidence=evidence_alpha,
        authority_lease_id=lease_alpha.lease_id,
    )
    beta = models.update_competence(
        "agent-beta",
        domain="reasoning",
        score=0.7,
        evidence=evidence_beta,
        authority_lease_id=lease_beta.lease_id,
    )

    assert alpha.version == beta.version == "self-model-00000002"
    alpha_use = authority.uses_for(lease_alpha.lease_id)[0]
    beta_use = authority.uses_for(lease_beta.lease_id)[0]
    assert alpha_use.use_ref == "self-model:agent-alpha:self-model-00000002"
    assert beta_use.use_ref == "self-model:agent-beta:self-model-00000002"
    assert alpha_use.use_ref != beta_use.use_ref
