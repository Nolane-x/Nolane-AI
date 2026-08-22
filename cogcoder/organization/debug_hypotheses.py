from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from .debug_evidence import DebugCaseStatus, DebugEvidenceKind, DebugEvidenceLedger, FailureClass


class HypothesisStatus(str, Enum):
    ACTIVE = 'active'
    REJECTED = 'rejected'
    ACCEPTED = 'accepted'


@dataclass(frozen=True, slots=True)
class DebugHypothesis:
    hypothesis_id: str
    case_id: str
    proposer_agent_id: str
    statement: str
    supporting_evidence_ids: tuple[str, ...]
    confidence: float
    status: HypothesisStatus = HypothesisStatus.ACTIVE
    refuting_evidence_ids: tuple[str, ...] = ()
    rejection_reason: str | None = None

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (self.hypothesis_id, self.case_id, self.proposer_agent_id, self.statement)):
            raise ValueError('debug hypothesis identity/case/proposer/statement must be explicit')
        if not self.supporting_evidence_ids:
            raise ValueError('debug hypothesis requires supporting evidence')
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError('debug hypothesis confidence must be in [0,1]')

    def to_state(self) -> dict[str, Any]:
        return {
            'hypothesis_id': self.hypothesis_id, 'case_id': self.case_id,
            'proposer_agent_id': self.proposer_agent_id, 'statement': self.statement,
            'supporting_evidence_ids': list(self.supporting_evidence_ids), 'confidence': self.confidence,
            'status': self.status.value, 'refuting_evidence_ids': list(self.refuting_evidence_ids),
            'rejection_reason': self.rejection_reason,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'DebugHypothesis':
        return cls(
            hypothesis_id=str(state['hypothesis_id']), case_id=str(state['case_id']),
            proposer_agent_id=str(state['proposer_agent_id']), statement=str(state['statement']),
            supporting_evidence_ids=tuple(str(x) for x in state.get('supporting_evidence_ids', ())),
            confidence=float(state['confidence']),
            status=HypothesisStatus(str(state.get('status', HypothesisStatus.ACTIVE.value))),
            refuting_evidence_ids=tuple(str(x) for x in state.get('refuting_evidence_ids', ())),
            rejection_reason=None if state.get('rejection_reason') is None else str(state['rejection_reason']),
        )


class DebugHypothesisLedger:
    def __init__(self, evidence: DebugEvidenceLedger) -> None:
        self.evidence = evidence
        self._hypotheses: dict[str, DebugHypothesis] = {}
        self._counter = 0

    def hypotheses(self) -> tuple[DebugHypothesis, ...]:
        return tuple(self._hypotheses[key] for key in sorted(self._hypotheses))

    def get(self, hypothesis_id: str) -> DebugHypothesis:
        try:
            return self._hypotheses[str(hypothesis_id)]
        except KeyError as exc:
            raise KeyError(f'unknown debug hypothesis: {hypothesis_id}') from exc

    def _validate_evidence_ids(self, case_id: str, evidence_ids: tuple[str, ...]) -> tuple[str, ...]:
        result = tuple(str(x) for x in evidence_ids)
        if not result:
            raise ValueError('debug hypothesis evidence cannot be empty')
        for artifact_id in result:
            artifact = self.evidence.get_evidence(artifact_id)
            if artifact.case_id != str(case_id):
                raise ValueError('debug hypothesis evidence belongs to another case')
        return result

    def propose(
        self, *, case_id: str, proposer_agent_id: str, statement: str,
        supporting_evidence_ids: tuple[str, ...], confidence: float,
    ) -> DebugHypothesis:
        self.evidence.get_case(case_id)
        support = self._validate_evidence_ids(case_id, supporting_evidence_ids)
        self._counter += 1
        row = DebugHypothesis(
            f'hypothesis-{self._counter:08d}', str(case_id), str(proposer_agent_id), str(statement),
            support, float(confidence),
        )
        self._hypotheses[row.hypothesis_id] = row
        return row

    def reject(
        self, hypothesis_id: str, *, actor_agent_id: str, reason: str,
        refuting_evidence_ids: tuple[str, ...],
    ) -> DebugHypothesis:
        if str(actor_agent_id) != 'debug.chief':
            raise PermissionError('only Debug Chief may reject authoritative root-cause hypotheses')
        old = self.get(hypothesis_id)
        if old.status is not HypothesisStatus.ACTIVE:
            raise ValueError('only active hypothesis may be rejected')
        reason_text = str(reason).strip()
        if not reason_text:
            raise ValueError('hypothesis rejection requires reason')
        refuting = self._validate_evidence_ids(old.case_id, refuting_evidence_ids)
        row = replace(
            old, status=HypothesisStatus.REJECTED,
            refuting_evidence_ids=refuting, rejection_reason=reason_text,
        )
        self._hypotheses[row.hypothesis_id] = row
        return row

    def accept(self, hypothesis_id: str, *, actor_agent_id: str) -> DebugHypothesis:
        if str(actor_agent_id) != 'debug.chief':
            raise PermissionError('only Debug Chief may accept authoritative root cause')
        old = self.get(hypothesis_id)
        if old.status is HypothesisStatus.REJECTED:
            raise ValueError('rejected hypothesis cannot be accepted in place')
        if old.status is HypothesisStatus.ACCEPTED:
            return old
        case = self.evidence.get_case(old.case_id)
        if case.status is not DebugCaseStatus.REPRODUCED or not self.evidence.has_deterministic_reproduction(case.case_id):
            raise ValueError('root cause requires deterministic reproduced case')
        supporting = tuple(self.evidence.get_evidence(x) for x in old.supporting_evidence_ids)
        if not supporting:
            raise ValueError('root cause requires supporting evidence')
        if case.failure_class is FailureClass.CONCURRENCY and not any(x.kind is DebugEvidenceKind.CONCURRENCY_TRACE for x in supporting):
            raise ValueError('concurrency root cause requires concurrency trace evidence')
        if case.failure_class is FailureClass.REGRESSION and not any(x.kind is DebugEvidenceKind.BISECT for x in supporting):
            raise ValueError('regression root cause requires bisect evidence')
        if case.accepted_root_cause_hypothesis_id is not None and case.accepted_root_cause_hypothesis_id != old.hypothesis_id:
            raise ValueError('case already has a different accepted root cause')
        row = replace(old, status=HypothesisStatus.ACCEPTED)
        self.evidence.set_root_cause(case.case_id, row.hypothesis_id)
        self._hypotheses[row.hypothesis_id] = row
        return row

    def current_root_cause(self, case_id: str) -> DebugHypothesis:
        case = self.evidence.get_case(case_id)
        if case.accepted_root_cause_hypothesis_id is None:
            raise KeyError(f'case has no accepted root cause: {case_id}')
        row = self.get(case.accepted_root_cause_hypothesis_id)
        if row.status is not HypothesisStatus.ACCEPTED:
            raise ValueError('case root cause does not point to accepted hypothesis')
        return row

    def to_state(self) -> dict[str, Any]:
        return {'counter': self._counter, 'hypotheses': [x.to_state() for x in self.hypotheses()]}

    @classmethod
    def from_state(cls, evidence: DebugEvidenceLedger, state: Mapping[str, Any]) -> 'DebugHypothesisLedger':
        ledger = cls(evidence)
        for value in state.get('hypotheses', ()):
            row = DebugHypothesis.from_state(value)
            if row.hypothesis_id in ledger._hypotheses:
                raise ValueError('duplicate debug hypothesis id')
            evidence.get_case(row.case_id)
            ledger._validate_evidence_ids(row.case_id, row.supporting_evidence_ids)
            if row.refuting_evidence_ids:
                ledger._validate_evidence_ids(row.case_id, row.refuting_evidence_ids)
            ledger._hypotheses[row.hypothesis_id] = row
        ledger._counter = int(state.get('counter', len(ledger._hypotheses)))
        max_counter = 0
        for key in ledger._hypotheses:
            try:
                max_counter = max(max_counter, int(key.rsplit('-', 1)[1]))
            except Exception as exc:
                raise ValueError('non-canonical debug hypothesis id') from exc
        if ledger._counter < max_counter:
            raise ValueError('debug hypothesis counter behind history')
        for case in evidence.cases():
            if case.accepted_root_cause_hypothesis_id is not None:
                row = ledger.get(case.accepted_root_cause_hypothesis_id)
                if row.case_id != case.case_id or row.status is not HypothesisStatus.ACCEPTED:
                    raise ValueError('invalid accepted root-cause reference')
        return ledger
