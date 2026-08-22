from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Mapping

from .code_claims import CodeClaimLedger
from .types import canonical_digest


class CodingPatchStatus(str, Enum):
    DRAFT = 'draft'
    EVIDENCE_READY = 'evidence_ready'
    VERIFIED = 'verified'
    REJECTED = 'rejected'
    SUPERSEDED = 'superseded'


def _path(value: str) -> str:
    text = str(value).replace('\\', '/').strip()
    if not text:
        raise ValueError('patch file path must be non-empty')
    normalized = str(PurePosixPath(text))
    while normalized.startswith('./'):
        normalized = normalized[2:]
    if normalized.startswith('/') or normalized == '..' or normalized.startswith('../'):
        raise ValueError('patch file path must be repository-relative')
    return normalized


def _symbol(value: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError('patch symbol must be non-empty')
    return text


@dataclass(frozen=True, slots=True)
class ToolInvocationReceipt:
    receipt_id: str
    agent_id: str
    task_id: str
    tool_id: str
    input_artifact_refs: tuple[str, ...]
    output_artifact_refs: tuple[str, ...]
    success: bool
    evidence_refs: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'agent_id': self.agent_id,
            'task_id': self.task_id,
            'tool_id': self.tool_id,
            'input_artifact_refs': list(self.input_artifact_refs),
            'output_artifact_refs': list(self.output_artifact_refs),
            'success': self.success,
            'evidence_refs': list(self.evidence_refs),
        }

    def to_state(self) -> dict[str, Any]:
        return {'receipt_id': self.receipt_id, **self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ToolInvocationReceipt':
        row = cls(
            receipt_id=str(state['receipt_id']),
            agent_id=str(state['agent_id']),
            task_id=str(state['task_id']),
            tool_id=str(state['tool_id']),
            input_artifact_refs=tuple(str(x) for x in state.get('input_artifact_refs', ())),
            output_artifact_refs=tuple(str(x) for x in state.get('output_artifact_refs', ())),
            success=bool(state['success']),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
            digest=str(state['digest']),
        )
        expected = canonical_digest(row.payload())
        if expected != row.digest or row.receipt_id != 'tool-' + expected[:20]:
            raise ValueError('tool invocation receipt digest/id mismatch')
        return row


@dataclass(frozen=True, slots=True)
class CodingPatchCandidate:
    patch_id: str
    producer_agent_id: str
    task_id: str
    work_id: str
    base_plan_version: int
    base_architecture_version: int
    touched_files: tuple[str, ...]
    touched_symbols: tuple[str, ...]
    patch_artifact_id: str
    compile_evidence_refs: tuple[str, ...] = ()
    test_evidence_refs: tuple[str, ...] = ()
    static_evidence_refs: tuple[str, ...] = ()
    known_risks: tuple[str, ...] = ()
    plan_gap_event_refs: tuple[str, ...] = ()
    architecture_concern_event_refs: tuple[str, ...] = ()
    status: CodingPatchStatus = CodingPatchStatus.DRAFT

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (self.patch_id, self.producer_agent_id, self.task_id, self.work_id, self.patch_artifact_id)):
            raise ValueError('patch identity/producer/task/work/artifact must be explicit')
        if self.base_plan_version < 0 or self.base_architecture_version < 0:
            raise ValueError('patch base versions must be non-negative')
        if not self.touched_files and not self.touched_symbols:
            raise ValueError('patch must declare touched source scope')

    def to_state(self) -> dict[str, Any]:
        return {
            'patch_id': self.patch_id,
            'producer_agent_id': self.producer_agent_id,
            'task_id': self.task_id,
            'work_id': self.work_id,
            'base_plan_version': self.base_plan_version,
            'base_architecture_version': self.base_architecture_version,
            'touched_files': list(self.touched_files),
            'touched_symbols': list(self.touched_symbols),
            'patch_artifact_id': self.patch_artifact_id,
            'compile_evidence_refs': list(self.compile_evidence_refs),
            'test_evidence_refs': list(self.test_evidence_refs),
            'static_evidence_refs': list(self.static_evidence_refs),
            'known_risks': list(self.known_risks),
            'plan_gap_event_refs': list(self.plan_gap_event_refs),
            'architecture_concern_event_refs': list(self.architecture_concern_event_refs),
            'status': self.status.value,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CodingPatchCandidate':
        return cls(
            patch_id=str(state['patch_id']),
            producer_agent_id=str(state['producer_agent_id']),
            task_id=str(state['task_id']),
            work_id=str(state['work_id']),
            base_plan_version=int(state['base_plan_version']),
            base_architecture_version=int(state['base_architecture_version']),
            touched_files=tuple(_path(x) for x in state.get('touched_files', ())),
            touched_symbols=tuple(_symbol(x) for x in state.get('touched_symbols', ())),
            patch_artifact_id=str(state['patch_artifact_id']),
            compile_evidence_refs=tuple(str(x) for x in state.get('compile_evidence_refs', ())),
            test_evidence_refs=tuple(str(x) for x in state.get('test_evidence_refs', ())),
            static_evidence_refs=tuple(str(x) for x in state.get('static_evidence_refs', ())),
            known_risks=tuple(str(x) for x in state.get('known_risks', ())),
            plan_gap_event_refs=tuple(str(x) for x in state.get('plan_gap_event_refs', ())),
            architecture_concern_event_refs=tuple(str(x) for x in state.get('architecture_concern_event_refs', ())),
            status=CodingPatchStatus(str(state.get('status', CodingPatchStatus.DRAFT.value))),
        )


class CodingPatchLedger:
    def __init__(self, claims: CodeClaimLedger) -> None:
        self.claims = claims
        self._patches: dict[str, CodingPatchCandidate] = {}
        self._tool_receipts: dict[str, ToolInvocationReceipt] = {}
        self._patch_counter = 0

    def patches(self) -> tuple[CodingPatchCandidate, ...]:
        return tuple(self._patches[key] for key in sorted(self._patches))

    def get_patch(self, patch_id: str) -> CodingPatchCandidate:
        try:
            return self._patches[str(patch_id)]
        except KeyError as exc:
            raise KeyError(f'unknown coding patch: {patch_id}') from exc

    def register_patch(
        self,
        *,
        producer_agent_id: str,
        task_id: str,
        work_id: str,
        base_plan_version: int,
        base_architecture_version: int,
        touched_files: tuple[str, ...] = (),
        touched_symbols: tuple[str, ...] = (),
        patch_artifact_id: str,
        compile_evidence_refs: tuple[str, ...] = (),
        test_evidence_refs: tuple[str, ...] = (),
        static_evidence_refs: tuple[str, ...] = (),
        known_risks: tuple[str, ...] = (),
        plan_gap_event_refs: tuple[str, ...] = (),
        architecture_concern_event_refs: tuple[str, ...] = (),
    ) -> CodingPatchCandidate:
        files = tuple(sorted(set(_path(x) for x in touched_files)))
        symbols = tuple(sorted(set(_symbol(x) for x in touched_symbols)))
        compile_refs = tuple(str(x) for x in compile_evidence_refs if str(x).strip())
        test_refs = tuple(str(x) for x in test_evidence_refs if str(x).strip())
        status = CodingPatchStatus.EVIDENCE_READY if compile_refs and test_refs else CodingPatchStatus.DRAFT
        self._patch_counter += 1
        row = CodingPatchCandidate(
            patch_id=f'patch-{self._patch_counter:08d}',
            producer_agent_id=str(producer_agent_id),
            task_id=str(task_id),
            work_id=str(work_id),
            base_plan_version=int(base_plan_version),
            base_architecture_version=int(base_architecture_version),
            touched_files=files,
            touched_symbols=symbols,
            patch_artifact_id=str(patch_artifact_id),
            compile_evidence_refs=compile_refs,
            test_evidence_refs=test_refs,
            static_evidence_refs=tuple(str(x) for x in static_evidence_refs if str(x).strip()),
            known_risks=tuple(str(x) for x in known_risks if str(x).strip()),
            plan_gap_event_refs=tuple(str(x) for x in plan_gap_event_refs if str(x).strip()),
            architecture_concern_event_refs=tuple(str(x) for x in architecture_concern_event_refs if str(x).strip()),
            status=status,
        )
        self._patches[row.patch_id] = row
        return row

    def claim_coverage(self, patch_id: str) -> bool:
        row = self.get_patch(patch_id)
        return self.claims.covers(
            agent_id=row.producer_agent_id,
            task_id=row.task_id,
            file_paths=row.touched_files,
            symbol_ids=row.touched_symbols,
        )

    def set_status(self, patch_id: str, status: CodingPatchStatus) -> CodingPatchCandidate:
        old = self.get_patch(patch_id)
        row = replace(old, status=CodingPatchStatus(status))
        self._patches[row.patch_id] = row
        return row

    def record_tool_invocation(
        self,
        *,
        agent_id: str,
        task_id: str,
        tool_id: str,
        input_artifact_refs: tuple[str, ...] = (),
        output_artifact_refs: tuple[str, ...] = (),
        success: bool,
        evidence_refs: tuple[str, ...] = (),
    ) -> ToolInvocationReceipt:
        agent = str(agent_id).strip()
        task = str(task_id).strip()
        tool = str(tool_id).strip()
        if not agent or not task or not tool:
            raise ValueError('tool invocation requires agent/task/tool')
        payload = {
            'agent_id': agent,
            'task_id': task,
            'tool_id': tool,
            'input_artifact_refs': [str(x) for x in input_artifact_refs],
            'output_artifact_refs': [str(x) for x in output_artifact_refs],
            'success': bool(success),
            'evidence_refs': [str(x) for x in evidence_refs],
        }
        digest = canonical_digest(payload)
        row = ToolInvocationReceipt(
            receipt_id='tool-' + digest[:20],
            agent_id=agent,
            task_id=task,
            tool_id=tool,
            input_artifact_refs=tuple(payload['input_artifact_refs']),
            output_artifact_refs=tuple(payload['output_artifact_refs']),
            success=bool(success),
            evidence_refs=tuple(payload['evidence_refs']),
            digest=digest,
        )
        existing = self._tool_receipts.get(row.receipt_id)
        if existing is not None and existing != row:
            raise ValueError('tool receipt id collision')
        self._tool_receipts[row.receipt_id] = row
        return row

    def get_tool_receipt(self, receipt_id: str) -> ToolInvocationReceipt:
        try:
            return self._tool_receipts[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f'unknown tool receipt: {receipt_id}') from exc

    def tool_receipts(self) -> tuple[ToolInvocationReceipt, ...]:
        return tuple(self._tool_receipts[key] for key in sorted(self._tool_receipts))

    def to_state(self) -> dict[str, Any]:
        return {
            'patch_counter': self._patch_counter,
            'patches': [row.to_state() for row in self.patches()],
            'tool_receipts': [row.to_state() for row in self.tool_receipts()],
        }

    @classmethod
    def from_state(cls, *, claims: CodeClaimLedger, state: Mapping[str, Any]) -> 'CodingPatchLedger':
        ledger = cls(claims)
        for value in state.get('patches', ()):
            row = CodingPatchCandidate.from_state(value)
            if row.patch_id in ledger._patches:
                raise ValueError('duplicate patch id in snapshot')
            ledger._patches[row.patch_id] = row
        for value in state.get('tool_receipts', ()):
            row = ToolInvocationReceipt.from_state(value)
            existing = ledger._tool_receipts.get(row.receipt_id)
            if existing is not None and existing != row:
                raise ValueError('duplicate tool receipt id in snapshot')
            ledger._tool_receipts[row.receipt_id] = row
        ledger._patch_counter = int(state.get('patch_counter', len(ledger._patches)))
        expected_max = 0
        for patch_id in ledger._patches:
            try:
                expected_max = max(expected_max, int(patch_id.rsplit('-', 1)[1]))
            except Exception as exc:
                raise ValueError('non-canonical patch id') from exc
        if ledger._patch_counter < expected_max:
            raise ValueError('patch counter is behind patch history')
        return ledger
