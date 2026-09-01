from __future__ import annotations

from types import SimpleNamespace

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.evidence import EvidenceRecord
from nolane.external_core.self_model import SelfModelRegistry
from nolane.memory.experience import ExperienceLedger, ExperienceOutcome, LearningLayer
from nolane.memory.learning_authority import LearningEvidenceAuthority
from nolane.memory.skills import SkillEvolutionEngine


class _RegistryStub:
    def __init__(self) -> None:
        self._rows = {
            "producer": SimpleNamespace(
                agent_id="producer",
                region="memory-context-knowledge",
                self_model_version="self-model-0.1",
            ),
            "verifier": SimpleNamespace(
                agent_id="verifier",
                region="verification-assurance",
                self_model_version="self-model-0.1",
            ),
        }
        self.updated: dict[str, str] = {}

    def identities(self):
        return tuple(self._rows[key] for key in sorted(self._rows))

    def get(self, agent_id: str):
        return self._rows[str(agent_id)]

    def set_self_model_version(self, agent_id: str, version: str) -> None:
        self.get(agent_id)
        self.updated[str(agent_id)] = str(version)


class _EventsStub:
    def latest_event_id(self):
        return None

    def get(self, event_id: str):
        raise KeyError(event_id)


def _evidence(evidence_id: str = "evidence-clean") -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id,
        "verifier",
        True,
        false_accepts=0,
        regressions=0,
        notes="exact learning operation verified",
    )


def test_bound_experience_positive_attribution_requires_exact_preissued_lease_and_consumes_it() -> None:
    authority = LearningEvidenceAuthority()
    ledger = ExperienceLedger(
        registry=_RegistryStub(),
        events=_EventsStub(),
        learning_authority=authority,
    )
    experience = ledger.record(
        agent_id="producer",
        author_agent_id="producer",
        domain="reasoning",
        outcome=ExperienceOutcome.SUCCESS,
        summary="the candidate strategy passed its governed check",
        evidence_refs=("source-proof",),
    )
    evidence = _evidence()
    digest = ledger.attribution_subject_digest(
        experience.experience_id,
        learning_layer=LearningLayer.STRATEGY,
        lesson="prefer the verified strategy under this regime",
    )
    lease = authority.issue(
        subject_kind="experience_attribution",
        subject_id=experience.experience_id,
        operation_class="experience.attribute",
        producer_agent_id="producer",
        evidence=evidence,
        subject_digest=digest,
        single_use=True,
    )

    with pytest.raises(PermissionError, match="preissued learning evidence lease"):
        ledger.attribute(
            experience.experience_id,
            learning_layer=LearningLayer.STRATEGY,
            lesson="prefer the verified strategy under this regime",
            evidence=evidence,
        )

    attribution = ledger.attribute(
        experience.experience_id,
        learning_layer=LearningLayer.STRATEGY,
        lesson="prefer the verified strategy under this regime",
        evidence=evidence,
        authority_lease_id=lease.lease_id,
    )
    uses = authority.uses_for(lease.lease_id)
    assert attribution.positive is True
    assert len(uses) == 1
    assert uses[0].use_ref == attribution.attribution_id

    with pytest.raises(PermissionError, match="already consumed"):
        ledger.attribute(
            experience.experience_id,
            learning_layer=LearningLayer.STRATEGY,
            lesson="prefer the verified strategy under this regime",
            evidence=evidence,
            authority_lease_id=lease.lease_id,
        )


def test_bound_experience_rejects_laundered_lease_for_different_lesson() -> None:
    authority = LearningEvidenceAuthority()
    ledger = ExperienceLedger(
        registry=_RegistryStub(), events=_EventsStub(), learning_authority=authority
    )
    experience = ledger.record(
        agent_id="producer",
        author_agent_id="producer",
        domain="reasoning",
        outcome="success",
        summary="verified run",
    )
    evidence = _evidence()
    digest = ledger.attribution_subject_digest(
        experience.experience_id,
        learning_layer="strategy",
        lesson="lesson A",
    )
    lease = authority.issue(
        subject_kind="experience_attribution",
        subject_id=experience.experience_id,
        operation_class="experience.attribute",
        producer_agent_id="producer",
        evidence=evidence,
        subject_digest=digest,
    )

    with pytest.raises(PermissionError, match="exact learning operation"):
        ledger.attribute(
            experience.experience_id,
            learning_layer="strategy",
            lesson="lesson B",
            evidence=evidence,
            authority_lease_id=lease.lease_id,
        )


def test_bound_self_model_update_requires_exact_current_state_and_proposed_update_lease() -> None:
    authority = LearningEvidenceAuthority()
    models = SelfModelRegistry(_RegistryStub(), learning_authority=authority)
    evidence = _evidence("evidence-self-model")
    digest = models.competence_subject_digest("producer", domain="reasoning", score=0.8)
    lease = authority.issue(
        subject_kind="self_model",
        subject_id="producer",
        operation_class="self_model.update_competence",
        producer_agent_id="producer",
        evidence=evidence,
        subject_digest=digest,
    )

    with pytest.raises(PermissionError, match="preissued learning evidence lease"):
        models.update_competence(
            "producer", domain="reasoning", score=0.8, evidence=evidence
        )

    updated = models.update_competence(
        "producer",
        domain="reasoning",
        score=0.8,
        evidence=evidence,
        authority_lease_id=lease.lease_id,
    )
    assert updated.domain_competence == (("reasoning", 0.8),)
    assert authority.uses_for(lease.lease_id)[0].use_ref == updated.version


def test_self_model_lease_becomes_stale_after_any_committed_model_revision() -> None:
    authority = LearningEvidenceAuthority()
    models = SelfModelRegistry(_RegistryStub(), learning_authority=authority)
    first_evidence = _evidence("evidence-first")
    first_digest = models.competence_subject_digest("producer", domain="reasoning", score=0.8)
    first = authority.issue(
        subject_kind="self_model",
        subject_id="producer",
        operation_class="self_model.update_competence",
        producer_agent_id="producer",
        evidence=first_evidence,
        subject_digest=first_digest,
    )
    stale_evidence = _evidence("evidence-stale")
    stale_digest = models.competence_subject_digest("producer", domain="coding", score=0.7)
    stale = authority.issue(
        subject_kind="self_model",
        subject_id="producer",
        operation_class="self_model.update_competence",
        producer_agent_id="producer",
        evidence=stale_evidence,
        subject_digest=stale_digest,
    )

    models.update_competence(
        "producer",
        domain="reasoning",
        score=0.8,
        evidence=first_evidence,
        authority_lease_id=first.lease_id,
    )
    with pytest.raises(PermissionError, match="exact learning operation"):
        models.update_competence(
            "producer",
            domain="coding",
            score=0.7,
            evidence=stale_evidence,
            authority_lease_id=stale.lease_id,
        )


def test_bound_skill_positive_verification_requires_exact_lease_and_stales_parallel_lease() -> None:
    authority = LearningEvidenceAuthority()
    skills = SkillEvolutionEngine(learning_authority=authority)
    skill = skills.propose(
        owner_agent_id="producer",
        region="memory-context-knowledge",
        name="verified strategy",
        body="apply only after independent verification",
    )
    first_evidence = _evidence("evidence-skill-first")
    first_digest = skills.verification_subject_digest(skill.skill_id)
    first = authority.issue(
        subject_kind="skill",
        subject_id=skill.skill_id,
        operation_class="skill.verify",
        producer_agent_id="producer",
        evidence=first_evidence,
        subject_digest=first_digest,
    )
    stale_evidence = _evidence("evidence-skill-stale")
    stale = authority.issue(
        subject_kind="skill",
        subject_id=skill.skill_id,
        operation_class="skill.verify",
        producer_agent_id="producer",
        evidence=stale_evidence,
        subject_digest=first_digest,
    )

    with pytest.raises(PermissionError, match="preissued learning evidence lease"):
        skills.verify(skill.skill_id, first_evidence)

    verified = skills.verify(
        skill.skill_id,
        first_evidence,
        authority_lease_id=first.lease_id,
    )
    assert verified.evidence == (first_evidence,)
    assert len(authority.uses_for(first.lease_id)) == 1

    with pytest.raises(PermissionError, match="exact learning operation"):
        skills.verify(
            skill.skill_id,
            stale_evidence,
            authority_lease_id=stale.lease_id,
        )


def test_runtime_b_graph_shares_one_learning_evidence_authority_and_restores_it() -> None:
    runtime = OrganizationRuntime.first_generation()
    authority = runtime.learning_substrate.learning_authority

    assert authority is not None
    assert runtime.learning_substrate.experiences.learning_authority is authority
    assert runtime.evolution.learning_authority is authority
    assert runtime.individual_evolution.learning_authority is authority
    assert runtime.individual_evolution.experiences.learning_authority is authority
    assert runtime.individual_evolution.self_models.learning_authority is authority

    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(state)
    restored_authority = restored.learning_substrate.learning_authority
    assert restored_authority is not None
    assert restored.evolution.learning_authority is restored_authority
    assert restored.individual_evolution.learning_authority is restored_authority
    assert restored.individual_evolution.experiences.learning_authority is restored_authority
    assert restored.individual_evolution.self_models.learning_authority is restored_authority
    assert restored_authority.to_state() == authority.to_state()
    assert restored.to_state() == state
