from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from .authority import AuthorityGraph
from .events import EventLedger
from .registry import AgentRegistry
from .types import EventKind, canonical_digest


@dataclass(frozen=True, slots=True)
class UXAcceptanceCriterion:
    criterion_id: str
    statement: str
    verification_class: str
    evidence_expectations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.criterion_id.strip() or not self.statement.strip() or not self.verification_class.strip():
            raise ValueError('UX acceptance criterion identity/statement/class must be explicit')
        if not self.evidence_expectations:
            raise ValueError('UX acceptance criterion requires evidence expectations')

    def to_state(self) -> dict[str, Any]:
        return {
            'criterion_id': self.criterion_id,
            'statement': self.statement,
            'verification_class': self.verification_class,
            'evidence_expectations': list(self.evidence_expectations),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'UXAcceptanceCriterion':
        return cls(
            str(state['criterion_id']), str(state['statement']), str(state['verification_class']),
            tuple(str(x) for x in state.get('evidence_expectations', ())),
        )


@dataclass(frozen=True, slots=True)
class UXTransition:
    source_state: str
    target_state: str
    trigger: str

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (self.source_state, self.target_state, self.trigger)):
            raise ValueError('UX transition source/target/trigger must be explicit')

    def to_state(self) -> dict[str, str]:
        return {'source_state': self.source_state, 'target_state': self.target_state, 'trigger': self.trigger}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'UXTransition':
        return cls(str(state['source_state']), str(state['target_state']), str(state['trigger']))


@dataclass(frozen=True, slots=True)
class UXDesignProposal:
    proposal_id: str
    flow_id: str
    task_id: str
    source_agent_id: str
    goal: str
    states: tuple[str, ...]
    transitions: tuple[UXTransition, ...]
    design_token_refs: tuple[str, ...]
    responsive_expectations: tuple[str, ...]
    accessibility_expectations: tuple[str, ...]
    acceptance_criteria: tuple[UXAcceptanceCriterion, ...]
    evidence_refs: tuple[str, ...]
    status: str = 'proposed'
    accepted_revision: int | None = None
    digest: str = ''

    def payload(self) -> dict[str, Any]:
        return {
            'proposal_id': self.proposal_id, 'flow_id': self.flow_id, 'task_id': self.task_id,
            'source_agent_id': self.source_agent_id, 'goal': self.goal, 'states': list(self.states),
            'transitions': [x.to_state() for x in self.transitions], 'design_token_refs': list(self.design_token_refs),
            'responsive_expectations': list(self.responsive_expectations),
            'accessibility_expectations': list(self.accessibility_expectations),
            'acceptance_criteria': [x.to_state() for x in self.acceptance_criteria],
            'evidence_refs': list(self.evidence_refs), 'status': self.status,
            'accepted_revision': self.accepted_revision,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'UXDesignProposal':
        row = cls(
            proposal_id=str(state['proposal_id']), flow_id=str(state['flow_id']), task_id=str(state['task_id']),
            source_agent_id=str(state['source_agent_id']), goal=str(state['goal']),
            states=tuple(str(x) for x in state.get('states', ())),
            transitions=tuple(UXTransition.from_state(x) for x in state.get('transitions', ())),
            design_token_refs=tuple(str(x) for x in state.get('design_token_refs', ())),
            responsive_expectations=tuple(str(x) for x in state.get('responsive_expectations', ())),
            accessibility_expectations=tuple(str(x) for x in state.get('accessibility_expectations', ())),
            acceptance_criteria=tuple(UXAcceptanceCriterion.from_state(x) for x in state.get('acceptance_criteria', ())),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
            status=str(state.get('status', 'proposed')),
            accepted_revision=None if state.get('accepted_revision') is None else int(state['accepted_revision']),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('UX proposal digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class UXFlowSpec:
    flow_id: str
    revision: int
    parent_revision: int | None
    task_id: str
    actor_agent_id: str
    goal: str
    states: tuple[str, ...]
    transitions: tuple[UXTransition, ...]
    design_token_refs: tuple[str, ...]
    responsive_expectations: tuple[str, ...]
    accessibility_expectations: tuple[str, ...]
    acceptance_criteria: tuple[UXAcceptanceCriterion, ...]
    evidence_refs: tuple[str, ...]
    source_proposal_id: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'flow_id': self.flow_id, 'revision': self.revision, 'parent_revision': self.parent_revision,
            'task_id': self.task_id, 'actor_agent_id': self.actor_agent_id, 'goal': self.goal,
            'states': list(self.states), 'transitions': [x.to_state() for x in self.transitions],
            'design_token_refs': list(self.design_token_refs), 'responsive_expectations': list(self.responsive_expectations),
            'accessibility_expectations': list(self.accessibility_expectations),
            'acceptance_criteria': [x.to_state() for x in self.acceptance_criteria],
            'evidence_refs': list(self.evidence_refs), 'source_proposal_id': self.source_proposal_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'UXFlowSpec':
        row = cls(
            flow_id=str(state['flow_id']), revision=int(state['revision']),
            parent_revision=None if state.get('parent_revision') is None else int(state['parent_revision']),
            task_id=str(state['task_id']), actor_agent_id=str(state['actor_agent_id']), goal=str(state['goal']),
            states=tuple(str(x) for x in state.get('states', ())),
            transitions=tuple(UXTransition.from_state(x) for x in state.get('transitions', ())),
            design_token_refs=tuple(str(x) for x in state.get('design_token_refs', ())),
            responsive_expectations=tuple(str(x) for x in state.get('responsive_expectations', ())),
            accessibility_expectations=tuple(str(x) for x in state.get('accessibility_expectations', ())),
            acceptance_criteria=tuple(UXAcceptanceCriterion.from_state(x) for x in state.get('acceptance_criteria', ())),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
            source_proposal_id=str(state['source_proposal_id']), digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('UX flow revision digest mismatch')
        return row


class UXDesignLedger:
    def __init__(self, *, registry: AgentRegistry, authority: AuthorityGraph, ledger: EventLedger) -> None:
        self.registry = registry
        self.authority = authority
        self.ledger = ledger
        self._proposals: dict[str, UXDesignProposal] = {}
        self._revisions: list[UXFlowSpec] = []
        self._proposal_counter = 0

    def proposals(self) -> tuple[UXDesignProposal, ...]:
        return tuple(self._proposals[key] for key in sorted(self._proposals))

    def revisions(self) -> tuple[UXFlowSpec, ...]:
        return tuple(self._revisions)

    def current(self, flow_id: str) -> UXFlowSpec:
        matches = [row for row in self._revisions if row.flow_id == str(flow_id)]
        if not matches:
            raise KeyError(f'no accepted UX flow: {flow_id}')
        return matches[-1]

    def propose(
        self, *, source_agent_id: str, flow_id: str, task_id: str, goal: str, states: tuple[str, ...],
        transitions: tuple[UXTransition, ...], design_token_refs: tuple[str, ...],
        responsive_expectations: tuple[str, ...], accessibility_expectations: tuple[str, ...],
        acceptance_criteria: tuple[UXAcceptanceCriterion, ...], evidence_refs: tuple[str, ...],
    ) -> UXDesignProposal:
        identity = self.registry.get(source_agent_id)
        if identity.region != 'ux-product-design':
            raise PermissionError('UX design proposals require a UX-region identity')
        if not all(str(x).strip() for x in (flow_id, task_id, goal)):
            raise ValueError('UX proposal flow/task/goal must be explicit')
        if len(states) < 2 or not transitions or not responsive_expectations or not accessibility_expectations or not acceptance_criteria or not evidence_refs:
            raise ValueError('UX proposal requires states, transitions, responsive/a11y expectations, criteria and evidence')
        state_set = set(states)
        if any(x.source_state not in state_set or x.target_state not in state_set for x in transitions):
            raise ValueError('UX transition references unknown state')
        self._proposal_counter += 1
        proposal_id = f'ux-proposal-{self._proposal_counter:08d}'
        payload = {
            'proposal_id': proposal_id, 'flow_id': str(flow_id), 'task_id': str(task_id),
            'source_agent_id': str(source_agent_id), 'goal': str(goal), 'states': list(states),
            'transitions': [x.to_state() for x in transitions], 'design_token_refs': list(design_token_refs),
            'responsive_expectations': list(responsive_expectations),
            'accessibility_expectations': list(accessibility_expectations),
            'acceptance_criteria': [x.to_state() for x in acceptance_criteria],
            'evidence_refs': list(evidence_refs), 'status': 'proposed', 'accepted_revision': None,
        }
        row = UXDesignProposal(
            proposal_id, str(flow_id), str(task_id), str(source_agent_id), str(goal), tuple(states), tuple(transitions),
            tuple(design_token_refs), tuple(responsive_expectations), tuple(accessibility_expectations),
            tuple(acceptance_criteria), tuple(evidence_refs), 'proposed', None, canonical_digest(payload),
        )
        self._proposals[row.proposal_id] = row
        self.ledger.append(
            EventKind.PLAN_CHANGE_PROPOSED, source_agent_id=source_agent_id, target_agent_id='ux.chief',
            region='ux-product-design', evidence_refs=row.evidence_refs,
            payload={'ui_action': 'ux_design_proposed', 'proposal_id': row.proposal_id, 'flow_id': row.flow_id, 'task_id': row.task_id},
        )
        return row

    def accept(self, proposal_id: str, *, actor_agent_id: str) -> UXFlowSpec:
        try:
            proposal = self._proposals[str(proposal_id)]
        except KeyError as exc:
            raise KeyError(f'unknown UX proposal: {proposal_id}') from exc
        if proposal.status != 'proposed':
            raise PermissionError('only an active UX proposal can be accepted')
        self.authority.require_write(actor_agent_id, 'ux-design-state')
        if actor_agent_id != 'ux.chief':
            raise PermissionError('authoritative UX acceptance belongs to UX Chief')
        prior = [x for x in self._revisions if x.flow_id == proposal.flow_id]
        revision = (prior[-1].revision + 1) if prior else 1
        parent = prior[-1].revision if prior else None
        payload = {
            'flow_id': proposal.flow_id, 'revision': revision, 'parent_revision': parent,
            'task_id': proposal.task_id, 'actor_agent_id': str(actor_agent_id), 'goal': proposal.goal,
            'states': list(proposal.states), 'transitions': [x.to_state() for x in proposal.transitions],
            'design_token_refs': list(proposal.design_token_refs),
            'responsive_expectations': list(proposal.responsive_expectations),
            'accessibility_expectations': list(proposal.accessibility_expectations),
            'acceptance_criteria': [x.to_state() for x in proposal.acceptance_criteria],
            'evidence_refs': list(proposal.evidence_refs), 'source_proposal_id': proposal.proposal_id,
        }
        row = UXFlowSpec(
            proposal.flow_id, revision, parent, proposal.task_id, str(actor_agent_id), proposal.goal,
            proposal.states, proposal.transitions, proposal.design_token_refs, proposal.responsive_expectations,
            proposal.accessibility_expectations, proposal.acceptance_criteria, proposal.evidence_refs,
            proposal.proposal_id, canonical_digest(payload),
        )
        self._revisions.append(row)
        updated_payload = {**proposal.payload(), 'status': 'accepted', 'accepted_revision': revision}
        self._proposals[proposal.proposal_id] = replace(
            proposal, status='accepted', accepted_revision=revision, digest=canonical_digest(updated_payload),
        )
        self.ledger.append(
            EventKind.EVIDENCE_ADDED, source_agent_id='ux.chief', target_agent_id=proposal.source_agent_id,
            region='ux-product-design', evidence_refs=row.evidence_refs,
            object_refs=(row.flow_id,),
            payload={'ui_action': 'ux_design_accepted', 'proposal_id': proposal.proposal_id, 'flow_id': row.flow_id, 'revision': row.revision},
        )
        return row

    def to_state(self) -> dict[str, Any]:
        return {
            'proposals': [x.to_state() for x in self.proposals()],
            'revisions': [x.to_state() for x in self._revisions],
            'proposal_counter': self._proposal_counter,
        }

    @classmethod
    def from_state(
        cls, *, registry: AgentRegistry, authority: AuthorityGraph, ledger: EventLedger, state: Mapping[str, Any],
    ) -> 'UXDesignLedger':
        result = cls(registry=registry, authority=authority, ledger=ledger)
        for value in state.get('proposals', ()):
            row = UXDesignProposal.from_state(value)
            if row.proposal_id in result._proposals:
                raise ValueError('duplicate UX proposal id')
            registry.get(row.source_agent_id)
            result._proposals[row.proposal_id] = row
        result._revisions = [UXFlowSpec.from_state(x) for x in state.get('revisions', ())]
        by_flow: dict[str, int] = {}
        for row in result._revisions:
            registry.get(row.actor_agent_id)
            expected = by_flow.get(row.flow_id, 0) + 1
            if row.revision != expected or row.actor_agent_id != 'ux.chief':
                raise ValueError('non-canonical UX revision history')
            if row.parent_revision != (row.revision - 1 if row.revision > 1 else None):
                raise ValueError('UX parent revision mismatch')
            by_flow[row.flow_id] = row.revision
        max_counter = 0
        for row in result._proposals.values():
            try:
                max_counter = max(max_counter, int(row.proposal_id.rsplit('-', 1)[1]))
            except Exception as exc:
                raise ValueError('non-canonical UX proposal id') from exc
        result._proposal_counter = int(state.get('proposal_counter', max_counter))
        if result._proposal_counter < max_counter:
            raise ValueError('UX proposal counter is behind history')
        for row in result._revisions:
            proposal = result._proposals.get(row.source_proposal_id)
            if proposal is None or proposal.status != 'accepted' or proposal.accepted_revision != row.revision:
                raise ValueError('UX revision/proposal provenance mismatch')
        return result
