import pytest

from cogcoder.organization.authority import AuthorityGraph
from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.events import EventLedger
from cogcoder.organization.registry import AgentRegistry
from cogcoder.organization.ui_design import UXAcceptanceCriterion, UXDesignLedger, UXTransition


def _ledger():
    registry = AgentRegistry(build_first_generation_blueprint())
    authority = AuthorityGraph(registry)
    authority.claim_owner('ux-design-state', 'ux.chief')
    return UXDesignLedger(registry=registry, authority=authority, ledger=EventLedger())


def _criterion():
    return UXAcceptanceCriterion(
        criterion_id='UX-AC-1',
        statement='Keyboard user can submit the form and reach the confirmation state',
        verification_class='accessibility-interaction',
        evidence_expectations=('keyboard-e2e', 'accessibility-tree'),
    )


def test_ux_specialist_proposes_but_only_ux_chief_accepts_authoritative_revision():
    ledger = _ledger()
    proposal = ledger.propose(
        source_agent_id='ux.flow.01', flow_id='FLOW-CHECKOUT', task_id='T-UX',
        goal='Complete checkout with minimal ambiguity',
        states=('cart', 'details', 'review', 'confirmed'),
        transitions=(
            UXTransition('cart', 'details', 'continue'),
            UXTransition('details', 'review', 'submit-details'),
            UXTransition('review', 'confirmed', 'confirm-order'),
        ),
        design_token_refs=('spacing.form', 'type.body'),
        responsive_expectations=('mobile single-column', 'desktop constrained two-column'),
        accessibility_expectations=('logical tab order', 'visible focus', 'label association'),
        acceptance_criteria=(_criterion(),), evidence_refs=('EV-UX-PROPOSAL',),
    )
    with pytest.raises(PermissionError):
        ledger.accept(proposal.proposal_id, actor_agent_id='ux.flow.01')

    accepted = ledger.accept(proposal.proposal_id, actor_agent_id='ux.chief')
    assert accepted.revision == 1
    assert accepted.actor_agent_id == 'ux.chief'
    assert ledger.current('FLOW-CHECKOUT') == accepted
    assert accepted.acceptance_criteria[0].evidence_expectations == ('keyboard-e2e', 'accessibility-tree')


def test_ux_revisions_preserve_parent_history_and_canonical_restore():
    ledger = _ledger()
    first = ledger.propose(
        source_agent_id='ux.chief', flow_id='FLOW-EDITOR', task_id='T-UX-1', goal='Edit and save',
        states=('view', 'editing', 'saved'), transitions=(UXTransition('view', 'editing', 'edit'), UXTransition('editing', 'saved', 'save')),
        design_token_refs=('color.action',), responsive_expectations=('mobile stacked actions',),
        accessibility_expectations=('save button has accessible name',), acceptance_criteria=(_criterion(),),
        evidence_refs=('EV-FIRST',),
    )
    accepted1 = ledger.accept(first.proposal_id, actor_agent_id='ux.chief')
    second = ledger.propose(
        source_agent_id='ux.visual-accessibility.01', flow_id='FLOW-EDITOR', task_id='T-UX-2', goal='Edit, validate and save',
        states=('view', 'editing', 'invalid', 'saved'),
        transitions=(UXTransition('view', 'editing', 'edit'), UXTransition('editing', 'invalid', 'validation-fail'), UXTransition('editing', 'saved', 'save')),
        design_token_refs=('color.action', 'color.error'), responsive_expectations=('mobile stacked actions', 'desktop inline actions'),
        accessibility_expectations=('errors announced', 'visible focus'), acceptance_criteria=(_criterion(),), evidence_refs=('EV-SECOND',),
    )
    accepted2 = ledger.accept(second.proposal_id, actor_agent_id='ux.chief')
    assert accepted2.revision == 2
    assert accepted2.parent_revision == accepted1.revision
    state = ledger.to_state()
    restored = UXDesignLedger.from_state(registry=ledger.registry, authority=ledger.authority, ledger=EventLedger(), state=state)
    assert restored.to_state() == state
    assert restored.current('FLOW-EDITOR').revision == 2
