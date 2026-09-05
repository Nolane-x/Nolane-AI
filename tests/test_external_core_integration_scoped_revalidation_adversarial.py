from __future__ import annotations

from dataclasses import replace

import pytest

from nolane.external_core.authority_graph import AuthorityEdge, AuthorityRelation, ExternalAuthorityGraph
from nolane.external_core.component_contracts import ExternalComponentManifest, ExternalCoreFamily
from nolane.external_core.evidence import EvidenceRecord, ScopedEvidenceRecord
from nolane.external_core.integration_evolution import ComponentEvolutionDelta, build_integration_impact_closure, qualify_component_evolution
from nolane.external_core.integration_revalidation import RevalidationDisposition, build_revalidation_plan
from nolane.external_core.integration_scoped_revalidation import (
    RevalidationCompletionReceipt,
    RevalidationScope,
    ScopedRevalidationEvidenceBinding,
    assess_scoped_revalidation,
    build_revalidation_challenges,
    build_revalidation_scope,
    challenge_subject_digest,
)


def _manifest(component_id: str, version: str, *, consumes: tuple[str, ...] = (), produces: tuple[str, ...] = ()) -> ExternalComponentManifest:
    return ExternalComponentManifest.create(
        component_id=component_id,
        component_version=version,
        family=ExternalCoreFamily.D,
        protocol_versions={"integration": "2"},
        consumes_contracts=consumes,
        produces_contracts=produces,
        authority_capabilities=("integrate",) if component_id == "external.integration" else ("plan",),
        forbidden_authorities=("assure", "execute", "promote"),
        mutable_resources=(f"state:{component_id}",),
        evidence_inputs=("scoped-evidence-v2",),
        evidence_outputs=("integration-revalidation-v2",),
        restore_protocol="exact-revalidation-v2",
        compatibility_floor="0.0.1",
        compatibility_ceiling=version,
    )


def _case(new_version: str = "0.0.3", *, planning_version: str = "0.0.1"):
    old = _manifest("external.integration", "0.0.2", produces=("integrated",))
    new = _manifest("external.integration", new_version, produces=("integrated",))
    planning = _manifest("external.planning", planning_version, consumes=("integrated",))
    graph = ExternalAuthorityGraph(
        (new, planning),
        (
            AuthorityEdge.create(
                source_component_id="external.integration",
                target_component_id="external.planning",
                relation=AuthorityRelation.PROPOSES_TO,
                contract_kind="integrated",
            ),
        ),
    )
    delta = ComponentEvolutionDelta.create(old, new)
    closure = build_integration_impact_closure(("external.integration",), graph)
    plan = build_revalidation_plan(delta=delta, qualification=qualify_component_evolution(delta), impact_closure=closure)
    scope = build_revalidation_scope(delta=delta, impact_closure=closure, plan=plan)
    challenges = build_revalidation_challenges(scope=scope, plan=plan, authority_graph=graph)
    return graph, delta, closure, plan, scope, challenges


def _evidence(challenge, suffix: str, *, epoch: int = 10, passed: bool = True, regressions: int = 0) -> ScopedEvidenceRecord:
    return ScopedEvidenceRecord.create(
        evidence_id=f"scoped-{suffix}",
        subject_id=challenge.component_id,
        subject_version=challenge.target_component_version,
        subject_digest=challenge_subject_digest(challenge),
        scope_digest=challenge.scope_id,
        verifier_agent_id=f"verification.agent.{suffix}",
        observed_epoch=epoch,
        passed=passed,
        false_accepts=0,
        regressions=regressions,
        evidence_refs=(f"artifact:{suffix}",),
        limitations=(),
    )


def _bindings(challenges, *, epoch: int = 10):
    return tuple(
        ScopedRevalidationEvidenceBinding.create(challenge=row, evidence=_evidence(row, str(index), epoch=epoch))
        for index, row in enumerate(challenges)
    )


def test_adversarial_all_exact_scoped_evidence_can_make_transition_current() -> None:
    _, _, _, plan, scope, challenges = _case()
    bindings = _bindings(challenges)
    assessment = assess_scoped_revalidation(
        scope=scope,
        plan=plan,
        challenges=challenges,
        evidence_bindings=bindings,
        minimum_observed_epoch=5,
    )
    assert assessment.disposition is RevalidationDisposition.CURRENT
    assert not assessment.missing_challenge_ids


def test_adversarial_cross_version_evidence_replay_is_rejected() -> None:
    _, _, _, _, _, challenges = _case()
    challenge = challenges[0]
    evidence = _evidence(challenge, "old-version")
    forged_version = replace(evidence, subject_version="0.0.2")
    with pytest.raises(ValueError, match="version|integrity|subject"):
        ScopedRevalidationEvidenceBinding.create(challenge=challenge, evidence=forged_version)


def test_adversarial_cross_scope_or_plan_replay_cannot_satisfy_new_transition() -> None:
    _, _, _, old_plan, old_scope, old_challenges = _case()
    old_binding = ScopedRevalidationEvidenceBinding.create(challenge=old_challenges[0], evidence=_evidence(old_challenges[0], "old"))

    _, _, _, new_plan, new_scope, new_challenges = _case(planning_version="0.0.2")
    assert new_scope.scope_id != old_scope.scope_id
    assessment = assess_scoped_revalidation(
        scope=new_scope,
        plan=new_plan,
        challenges=new_challenges,
        evidence_bindings=(old_binding,),
        minimum_observed_epoch=0,
    )
    assert assessment.disposition is RevalidationDisposition.BLOCKED
    assert any(code in assessment.reason_codes for code in ("SCOPE_MISMATCH", "UNEXPECTED_EVIDENCE_BINDING", "CHALLENGE_MISMATCH"))


def test_adversarial_wrong_scope_digest_or_subject_digest_is_rejected() -> None:
    _, _, _, _, _, challenges = _case()
    challenge = challenges[0]
    evidence = _evidence(challenge, "wrong-digest")
    for forged in (
        replace(evidence, scope_digest="other-scope"),
        replace(evidence, subject_digest="other-subject"),
    ):
        with pytest.raises(ValueError, match="integrity|scope|subject"):
            ScopedRevalidationEvidenceBinding.create(challenge=challenge, evidence=forged)


def test_adversarial_self_certification_is_rejected() -> None:
    _, _, _, _, _, challenges = _case()
    challenge = challenges[0]
    evidence = ScopedEvidenceRecord.create(
        evidence_id="self",
        subject_id=challenge.component_id,
        subject_version=challenge.target_component_version,
        subject_digest=challenge_subject_digest(challenge),
        scope_digest=challenge.scope_id,
        verifier_agent_id=challenge.component_id,
        observed_epoch=10,
        passed=True,
        evidence_refs=("artifact:self",),
    )
    with pytest.raises(ValueError, match="self"):
        ScopedRevalidationEvidenceBinding.create(challenge=challenge, evidence=evidence)


def test_adversarial_duplicate_binding_blocks_instead_of_double_counting() -> None:
    _, _, _, plan, scope, challenges = _case()
    binding = ScopedRevalidationEvidenceBinding.create(challenge=challenges[0], evidence=_evidence(challenges[0], "dup"))
    assessment = assess_scoped_revalidation(
        scope=scope,
        plan=plan,
        challenges=challenges,
        evidence_bindings=(binding, binding),
        minimum_observed_epoch=0,
    )
    assert assessment.disposition is RevalidationDisposition.BLOCKED
    assert "DUPLICATE_EVIDENCE_BINDING" in assessment.reason_codes


def test_adversarial_stale_or_dirty_scoped_evidence_blocks() -> None:
    _, _, _, plan, scope, challenges = _case()
    stale = ScopedRevalidationEvidenceBinding.create(challenge=challenges[0], evidence=_evidence(challenges[0], "stale", epoch=3))
    stale_assessment = assess_scoped_revalidation(
        scope=scope,
        plan=plan,
        challenges=challenges,
        evidence_bindings=(stale,),
        minimum_observed_epoch=5,
    )
    assert stale_assessment.disposition is RevalidationDisposition.BLOCKED
    assert "EVIDENCE_STALE" in stale_assessment.reason_codes

    dirty = ScopedRevalidationEvidenceBinding.create(challenge=challenges[0], evidence=_evidence(challenges[0], "dirty", regressions=1))
    dirty_assessment = assess_scoped_revalidation(
        scope=scope,
        plan=plan,
        challenges=challenges,
        evidence_bindings=(dirty,),
        minimum_observed_epoch=0,
    )
    assert dirty_assessment.disposition is RevalidationDisposition.BLOCKED
    assert "EVIDENCE_NOT_CLEAN" in dirty_assessment.reason_codes


def test_adversarial_v1_evidence_cannot_enter_v2_binding() -> None:
    _, _, _, _, _, challenges = _case()
    legacy = EvidenceRecord("legacy", "verification.agent.legacy", True)
    with pytest.raises(ValueError, match="scoped"):
        ScopedRevalidationEvidenceBinding.create(challenge=challenges[0], evidence=legacy)  # type: ignore[arg-type]


def test_adversarial_completion_requires_current_exact_assessment() -> None:
    _, _, _, plan, scope, challenges = _case()
    incomplete = assess_scoped_revalidation(
        scope=scope,
        plan=plan,
        challenges=challenges,
        evidence_bindings=(),
        minimum_observed_epoch=0,
    )
    assert incomplete.disposition is RevalidationDisposition.REVALIDATION_REQUIRED
    with pytest.raises(ValueError, match="CURRENT|current"):
        RevalidationCompletionReceipt.create(
            scope=scope,
            assessment=incomplete,
            challenges=challenges,
            evidence_bindings=(),
        )


def test_adversarial_completion_is_exactly_restorable_and_forgery_fails() -> None:
    _, _, _, plan, scope, challenges = _case()
    bindings = _bindings(challenges)
    assessment = assess_scoped_revalidation(
        scope=scope,
        plan=plan,
        challenges=challenges,
        evidence_bindings=bindings,
        minimum_observed_epoch=0,
    )
    receipt = RevalidationCompletionReceipt.create(
        scope=scope,
        assessment=assessment,
        challenges=challenges,
        evidence_bindings=bindings,
    )
    assert RevalidationCompletionReceipt.from_state(receipt.to_state()) == receipt
    forged = replace(receipt, receipt_id="forged")
    with pytest.raises(ValueError, match="integrity"):
        forged.validate_integrity()


def test_adversarial_v2_surfaces_expose_no_control_authority() -> None:
    forbidden = ("authorize", "verify", "assure", "promote", "execute", "deploy", "repair", "auto_migrate", "register_runtime")
    for cls in (RevalidationScope, ScopedRevalidationEvidenceBinding, RevalidationCompletionReceipt):
        for name in forbidden:
            assert not hasattr(cls, name)
