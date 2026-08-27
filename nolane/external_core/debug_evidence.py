from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping


class FailureClass(str, Enum):
    RUNTIME = 'runtime'
    STATIC = 'static'
    CONCURRENCY = 'concurrency'
    REGRESSION = 'regression'
    PERFORMANCE = 'performance'
    CRASH = 'crash'
    INTEGRATION = 'integration'


class DebugCaseStatus(str, Enum):
    OPEN = 'open'
    REPRODUCED = 'reproduced'
    ROOT_CAUSE_ACCEPTED = 'root_cause_accepted'
    PATCH_IN_PROGRESS = 'patch_in_progress'
    VERIFIED = 'verified'
    RESOLVED = 'resolved'
    QUARANTINED = 'quarantined'
    CLOSED_UNRESOLVED = 'closed_unresolved'


class DebugEvidenceKind(str, Enum):
    RUNTIME_TRACE = 'runtime_trace'
    STACK_TRACE = 'stack_trace'
    COVERAGE = 'coverage'
    STATE_DIFF = 'state_diff'
    STATIC_FLOW = 'static_flow'
    CONCURRENCY_TRACE = 'concurrency_trace'
    BISECT = 'bisect'
    CRASH_DUMP = 'crash_dump'
    LOG_CORRELATION = 'log_correlation'
    PROFILER = 'profiler'


@dataclass(frozen=True, slots=True)
class FailureCase:
    case_id: str
    task_id: str
    title: str
    symptom: str
    failure_class: FailureClass
    affected_refs: tuple[str, ...]
    reporter_agent_id: str
    initial_evidence_refs: tuple[str, ...]
    status: DebugCaseStatus = DebugCaseStatus.OPEN
    accepted_root_cause_hypothesis_id: str | None = None

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (self.case_id, self.task_id, self.title, self.symptom, self.reporter_agent_id)):
            raise ValueError('failure case identity/task/title/symptom/reporter must be explicit')
        if not self.affected_refs or not self.initial_evidence_refs:
            raise ValueError('failure case requires affected refs and evidence')

    def to_state(self) -> dict[str, Any]:
        return {
            'case_id': self.case_id, 'task_id': self.task_id, 'title': self.title, 'symptom': self.symptom,
            'failure_class': self.failure_class.value, 'affected_refs': list(self.affected_refs),
            'reporter_agent_id': self.reporter_agent_id, 'initial_evidence_refs': list(self.initial_evidence_refs),
            'status': self.status.value, 'accepted_root_cause_hypothesis_id': self.accepted_root_cause_hypothesis_id,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'FailureCase':
        return cls(
            case_id=str(state['case_id']), task_id=str(state['task_id']), title=str(state['title']),
            symptom=str(state['symptom']), failure_class=FailureClass(str(state['failure_class'])),
            affected_refs=tuple(str(x) for x in state.get('affected_refs', ())),
            reporter_agent_id=str(state['reporter_agent_id']),
            initial_evidence_refs=tuple(str(x) for x in state.get('initial_evidence_refs', ())),
            status=DebugCaseStatus(str(state.get('status', DebugCaseStatus.OPEN.value))),
            accepted_root_cause_hypothesis_id=None if state.get('accepted_root_cause_hypothesis_id') is None else str(state['accepted_root_cause_hypothesis_id']),
        )


@dataclass(frozen=True, slots=True)
class ReproductionReceipt:
    receipt_id: str
    sequence: int
    case_id: str
    reproducer_agent_id: str
    deterministic: bool
    minimized: bool
    environment_digest: str
    failure_fingerprint: str
    artifact_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (self.receipt_id, self.case_id, self.reproducer_agent_id, self.environment_digest, self.failure_fingerprint)):
            raise ValueError('reproduction identity/case/reproducer/environment/fingerprint must be explicit')
        if not self.artifact_refs or not self.evidence_refs:
            raise ValueError('reproduction requires artifact and evidence refs')

    def to_state(self) -> dict[str, Any]:
        return {
            'receipt_id': self.receipt_id, 'sequence': self.sequence, 'case_id': self.case_id,
            'reproducer_agent_id': self.reproducer_agent_id, 'deterministic': self.deterministic,
            'minimized': self.minimized, 'environment_digest': self.environment_digest,
            'failure_fingerprint': self.failure_fingerprint, 'artifact_refs': list(self.artifact_refs),
            'evidence_refs': list(self.evidence_refs),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ReproductionReceipt':
        return cls(
            receipt_id=str(state['receipt_id']), sequence=int(state['sequence']), case_id=str(state['case_id']),
            reproducer_agent_id=str(state['reproducer_agent_id']), deterministic=bool(state['deterministic']),
            minimized=bool(state['minimized']), environment_digest=str(state['environment_digest']),
            failure_fingerprint=str(state['failure_fingerprint']),
            artifact_refs=tuple(str(x) for x in state.get('artifact_refs', ())),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
        )


@dataclass(frozen=True, slots=True)
class DebugEvidenceArtifact:
    artifact_id: str
    sequence: int
    case_id: str
    producer_agent_id: str
    kind: DebugEvidenceKind
    summary: str
    input_artifact_refs: tuple[str, ...]
    output_artifact_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (self.artifact_id, self.case_id, self.producer_agent_id, self.summary)):
            raise ValueError('debug evidence identity/case/producer/summary must be explicit')
        if not self.evidence_refs:
            raise ValueError('debug evidence requires evidence refs')

    def to_state(self) -> dict[str, Any]:
        return {
            'artifact_id': self.artifact_id, 'sequence': self.sequence, 'case_id': self.case_id,
            'producer_agent_id': self.producer_agent_id, 'kind': self.kind.value, 'summary': self.summary,
            'input_artifact_refs': list(self.input_artifact_refs), 'output_artifact_refs': list(self.output_artifact_refs),
            'evidence_refs': list(self.evidence_refs),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'DebugEvidenceArtifact':
        return cls(
            artifact_id=str(state['artifact_id']), sequence=int(state['sequence']), case_id=str(state['case_id']),
            producer_agent_id=str(state['producer_agent_id']), kind=DebugEvidenceKind(str(state['kind'])),
            summary=str(state['summary']), input_artifact_refs=tuple(str(x) for x in state.get('input_artifact_refs', ())),
            output_artifact_refs=tuple(str(x) for x in state.get('output_artifact_refs', ())),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
        )


class DebugEvidenceLedger:
    def __init__(self) -> None:
        self._cases: dict[str, FailureCase] = {}
        self._reproductions: list[ReproductionReceipt] = []
        self._evidence: list[DebugEvidenceArtifact] = []
        self._sequence = 0
        self._repro_counter = 0
        self._evidence_counter = 0

    def cases(self) -> tuple[FailureCase, ...]:
        return tuple(self._cases[key] for key in sorted(self._cases))

    def get_case(self, case_id: str) -> FailureCase:
        try:
            return self._cases[str(case_id)]
        except KeyError as exc:
            raise KeyError(f'unknown debug case: {case_id}') from exc

    def open_case(
        self, *, case_id: str, task_id: str, title: str, symptom: str,
        failure_class: FailureClass, affected_refs: tuple[str, ...], reporter_agent_id: str,
        evidence_refs: tuple[str, ...],
    ) -> FailureCase:
        key = str(case_id)
        if key in self._cases:
            raise ValueError('debug case id already exists')
        row = FailureCase(
            key, str(task_id), str(title), str(symptom), FailureClass(failure_class),
            tuple(str(x) for x in affected_refs), str(reporter_agent_id), tuple(str(x) for x in evidence_refs),
        )
        self._cases[key] = row
        return row

    def record_reproduction(
        self, *, case_id: str, reproducer_agent_id: str, deterministic: bool, minimized: bool,
        environment_digest: str, failure_fingerprint: str, artifact_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
    ) -> ReproductionReceipt:
        case = self.get_case(case_id)
        self._sequence += 1
        self._repro_counter += 1
        row = ReproductionReceipt(
            f'repro-{self._repro_counter:08d}', self._sequence, case.case_id, str(reproducer_agent_id),
            bool(deterministic), bool(minimized), str(environment_digest), str(failure_fingerprint),
            tuple(str(x) for x in artifact_refs), tuple(str(x) for x in evidence_refs),
        )
        self._reproductions.append(row)
        if row.deterministic and case.status is DebugCaseStatus.OPEN:
            self._cases[case.case_id] = replace(case, status=DebugCaseStatus.REPRODUCED)
        return row

    def reproductions_for(self, case_id: str) -> tuple[ReproductionReceipt, ...]:
        self.get_case(case_id)
        return tuple(row for row in self._reproductions if row.case_id == str(case_id))

    def has_deterministic_reproduction(self, case_id: str) -> bool:
        return any(row.deterministic for row in self.reproductions_for(case_id))

    def add_evidence(
        self, *, case_id: str, producer_agent_id: str, kind: DebugEvidenceKind, summary: str,
        input_artifact_refs: tuple[str, ...] = (), output_artifact_refs: tuple[str, ...] = (),
        evidence_refs: tuple[str, ...],
    ) -> DebugEvidenceArtifact:
        case = self.get_case(case_id)
        self._sequence += 1
        self._evidence_counter += 1
        row = DebugEvidenceArtifact(
            f'debug-evidence-{self._evidence_counter:08d}', self._sequence, case.case_id,
            str(producer_agent_id), DebugEvidenceKind(kind), str(summary),
            tuple(str(x) for x in input_artifact_refs), tuple(str(x) for x in output_artifact_refs),
            tuple(str(x) for x in evidence_refs),
        )
        self._evidence.append(row)
        return row

    def get_evidence(self, artifact_id: str) -> DebugEvidenceArtifact:
        for row in self._evidence:
            if row.artifact_id == str(artifact_id):
                return row
        raise KeyError(f'unknown debug evidence artifact: {artifact_id}')

    def evidence_for(self, case_id: str) -> tuple[DebugEvidenceArtifact, ...]:
        self.get_case(case_id)
        return tuple(row for row in self._evidence if row.case_id == str(case_id))

    def set_root_cause(self, case_id: str, hypothesis_id: str) -> FailureCase:
        case = self.get_case(case_id)
        if case.accepted_root_cause_hypothesis_id is not None and case.accepted_root_cause_hypothesis_id != str(hypothesis_id):
            raise ValueError('case already has a different accepted root cause')
        if case.status not in {DebugCaseStatus.REPRODUCED, DebugCaseStatus.ROOT_CAUSE_ACCEPTED}:
            raise ValueError('root cause requires reproduced case')
        row = replace(
            case,
            status=DebugCaseStatus.ROOT_CAUSE_ACCEPTED,
            accepted_root_cause_hypothesis_id=str(hypothesis_id),
        )
        self._cases[case.case_id] = row
        return row

    def mark_patch_in_progress(self, case_id: str) -> FailureCase:
        case = self.get_case(case_id)
        if case.status is not DebugCaseStatus.ROOT_CAUSE_ACCEPTED:
            raise ValueError('patch handoff requires accepted root cause')
        row = replace(case, status=DebugCaseStatus.PATCH_IN_PROGRESS)
        self._cases[case.case_id] = row
        return row

    def mark_resolved(self, case_id: str) -> FailureCase:
        case = self.get_case(case_id)
        if case.status not in {DebugCaseStatus.PATCH_IN_PROGRESS, DebugCaseStatus.VERIFIED}:
            raise ValueError('resolution requires patch in progress or verified case')
        row = replace(case, status=DebugCaseStatus.RESOLVED)
        self._cases[case.case_id] = row
        return row

    def to_state(self) -> dict[str, Any]:
        return {
            'cases': [x.to_state() for x in self.cases()],
            'reproductions': [x.to_state() for x in self._reproductions],
            'evidence': [x.to_state() for x in self._evidence],
            'sequence': self._sequence,
            'repro_counter': self._repro_counter,
            'evidence_counter': self._evidence_counter,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'DebugEvidenceLedger':
        ledger = cls()
        for value in state.get('cases', ()):
            row = FailureCase.from_state(value)
            if row.case_id in ledger._cases:
                raise ValueError('duplicate debug case in snapshot')
            ledger._cases[row.case_id] = row
        ledger._reproductions = [ReproductionReceipt.from_state(x) for x in state.get('reproductions', ())]
        ledger._evidence = [DebugEvidenceArtifact.from_state(x) for x in state.get('evidence', ())]
        ledger._sequence = int(state.get('sequence', 0))
        ledger._repro_counter = int(state.get('repro_counter', len(ledger._reproductions)))
        ledger._evidence_counter = int(state.get('evidence_counter', len(ledger._evidence)))
        seen_ids: set[str] = set()
        last_sequence = 0
        for row in sorted((*ledger._reproductions, *ledger._evidence), key=lambda x: x.sequence):
            ledger.get_case(row.case_id)
            identity = row.receipt_id if isinstance(row, ReproductionReceipt) else row.artifact_id
            if identity in seen_ids or row.sequence <= last_sequence:
                raise ValueError('non-canonical debug evidence timeline')
            seen_ids.add(identity)
            last_sequence = row.sequence
        if ledger._sequence < last_sequence:
            raise ValueError('debug evidence sequence counter behind history')
        return ledger
