from __future__ import annotations

import pytest

from nolane.external_core.authority_graph import AuthorityEdge, AuthorityRelation, ExternalAuthorityGraph
from nolane.external_core.component_contracts import ExternalComponentManifest, ExternalCoreFamily
from nolane.external_core.integration_evolution import ComponentEvolutionDelta, build_integration_impact_closure, qualify_component_evolution
from nolane.external_core.integration_revalidation import build_revalidation_plan
from nolane.external_core.integration_scoped_revalidation import (
    RevalidationChallenge,
    RevalidationScope,
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


def _inputs():
    old = _manifest("external.integration", "0.0.2", produces=("integrated",))
    new = _manifest("external.integration", "0.0.3", produces=("integrated",))
    planning = _manifest("external.planning", "0.0.1", consumes=("integrated",))
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
    qualification = qualify_component_evolution(delta)
    closure = build_integration_impact_closure(("external.integration",), graph)
    plan = build_revalidation_plan(delta=delta, qualification=qualification, impact_closure=closure)
    return old, new, graph, delta, closure, plan


def test_revalidation_scope_binds_exact_transition_plan_closure_and_graph() -> None:
    old, new, graph, delta, closure, plan = _inputs()
    scope = build_revalidation_scope(delta=delta, impact_closure=closure, plan=plan)
    assert scope.component_id == "external.integration"
    assert scope.old_manifest_digest == old.manifest_digest
    assert scope.new_manifest_digest == new.manifest_digest
    assert scope.old_component_version == "0.0.2"
    assert scope.new_component_version == "0.0.3"
    assert scope.delta_id == delta.delta_id
    assert scope.impact_closure_id == closure.closure_id
    assert scope.authority_graph_digest == graph.digest
    assert scope.plan_id == plan.plan_id
    assert RevalidationScope.from_state(scope.to_state()) == scope


def test_revalidation_challenges_are_deterministic_for_exact_requirements() -> None:
    _, _, graph, delta, closure, plan = _inputs()
    scope = build_revalidation_scope(delta=delta, impact_closure=closure, plan=plan)
    left = build_revalidation_challenges(scope=scope, plan=plan, authority_graph=graph)
    right = build_revalidation_challenges(scope=scope, plan=plan, authority_graph=graph)
    assert left == right
    expected = sum(len(row.required_evidence_kinds) for row in plan.requirements)
    assert len(left) == expected
    assert len({row.challenge_id for row in left}) == expected
    assert all(row.scope_id == scope.scope_id and row.plan_id == plan.plan_id for row in left)


def test_challenge_target_versions_come_from_exact_transition_and_graph_population() -> None:
    _, _, graph, delta, closure, plan = _inputs()
    scope = build_revalidation_scope(delta=delta, impact_closure=closure, plan=plan)
    challenges = build_revalidation_challenges(scope=scope, plan=plan, authority_graph=graph)
    integration_versions = {row.target_component_version for row in challenges if row.component_id == "external.integration"}
    planning_versions = {row.target_component_version for row in challenges if row.component_id == "external.planning"}
    assert integration_versions == {"0.0.3"}
    assert planning_versions == {"0.0.1"}
    assert all(challenge_subject_digest(row) for row in challenges)


def test_challenge_exact_restore_rejects_tampering() -> None:
    _, _, graph, delta, closure, plan = _inputs()
    scope = build_revalidation_scope(delta=delta, impact_closure=closure, plan=plan)
    challenge = build_revalidation_challenges(scope=scope, plan=plan, authority_graph=graph)[0]
    assert RevalidationChallenge.from_state(challenge.to_state()) == challenge
    state = challenge.to_state()
    state["target_component_version"] = "9.9.9"
    with pytest.raises(ValueError, match="challenge|integrity|canonical"):
        RevalidationChallenge.from_state(state)


def test_scope_rejects_plan_or_graph_substitution() -> None:
    _, _, graph, delta, closure, plan = _inputs()
    scope = build_revalidation_scope(delta=delta, impact_closure=closure, plan=plan)
    state = scope.to_state()
    state["authority_graph_digest"] = "other-graph"
    with pytest.raises(ValueError, match="scope|integrity|canonical"):
        RevalidationScope.from_state(state)
