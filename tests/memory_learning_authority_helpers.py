from __future__ import annotations

from nolane.external_core.evidence import EvidenceRecord
from nolane.memory.learning_substrate import EpistemicType


def clean_evidence(
    evidence_id: str,
    *,
    verifier_agent_id: str = "verification.chief",
    notes: str = "historical contract migrated to v0.0.12 authority",
) -> EvidenceRecord:
    return EvidenceRecord(
        str(evidence_id),
        str(verifier_agent_id),
        True,
        false_accepts=0,
        regressions=0,
        notes=notes,
    )


def authority_copy(substrate):
    authority = substrate.learning_authority
    return authority.from_state(authority.to_state())


def admit_memory(
    substrate,
    memory_or_id,
    *,
    evidence_id: str,
    actor_agent_id: str = "memory.chief",
    verifier_agent_id: str = "verification.chief",
):
    memory_id = str(getattr(memory_or_id, "memory_id", memory_or_id))
    row = substrate.memory.get(memory_id)
    evidence = clean_evidence(evidence_id, verifier_agent_id=verifier_agent_id)
    digest = substrate.memory_verification_subject_digest(
        memory_id,
        actor_agent_id=actor_agent_id,
    )
    lease = substrate.learning_authority.issue(
        subject_kind="memory",
        subject_id=memory_id,
        operation_class="memory.verify",
        producer_agent_id=row.owner_agent_id,
        evidence=evidence,
        subject_digest=digest,
        single_use=True,
    )
    return substrate.validate_memory(
        memory_id,
        actor_agent_id=actor_agent_id,
        evidence=evidence,
        authority_lease_id=lease.lease_id,
    )


def remember_verified(substrate, *, evidence_id: str, **remember_kwargs):
    row = substrate.remember(
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=(str(evidence_id),),
        **remember_kwargs,
    )
    return admit_memory(substrate, row, evidence_id=evidence_id)


def forget_memory(
    substrate,
    memory_or_id,
    *,
    actor_agent_id: str,
    reason: str,
    evidence_id: str,
    verifier_agent_id: str = "verification.chief",
):
    memory_id = str(getattr(memory_or_id, "memory_id", memory_or_id))
    evidence = clean_evidence(evidence_id, verifier_agent_id=verifier_agent_id)
    digest = substrate.forget_subject_digest(
        memory_id,
        actor_agent_id=actor_agent_id,
        reason=reason,
    )
    lease = substrate.learning_authority.issue(
        subject_kind="memory",
        subject_id=memory_id,
        operation_class="memory.forget",
        producer_agent_id=actor_agent_id,
        evidence=evidence,
        subject_digest=digest,
        single_use=True,
    )
    return substrate.forget(
        memory_id,
        actor_agent_id=actor_agent_id,
        reason=reason,
        evidence=evidence,
        authority_lease_id=lease.lease_id,
    )


def verify_skill(substrate, skill_id: str, evidence: EvidenceRecord):
    clean = bool(evidence.passed) and int(evidence.false_accepts) == 0 and int(evidence.regressions) == 0
    if not clean:
        return substrate.skills.verify(skill_id, evidence)
    skill = substrate.skills.get(skill_id)
    digest = substrate.skills.verification_subject_digest(skill_id)
    lease = substrate.learning_authority.issue(
        subject_kind="skill",
        subject_id=skill_id,
        operation_class="skill.verify",
        producer_agent_id=skill.owner_agent_id,
        evidence=evidence,
        subject_digest=digest,
        single_use=True,
    )
    return substrate.skills.verify(
        skill_id,
        evidence,
        authority_lease_id=lease.lease_id,
    )
