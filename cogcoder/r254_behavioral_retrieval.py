from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping, Sequence

from .r253_external_cognition import (
    CognitiveOperatorRegistry,
    CognitiveSnapshot,
    CompiledProcedure,
    DeficitSignal,
    ExternalWorkingState,
    ProcedureCard,
    ProcedureCompiler,
)
from .r254_cognitive_retrieval import CognitiveAttachment, content_digest


@dataclass(frozen=True, slots=True)
class RetrievedProcedureRejection:
    artifact_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class RetrievedCompiledProcedure:
    artifact_id: str
    attachment: CognitiveAttachment
    compiled: CompiledProcedure

    @property
    def procedure_id(self) -> str:
        return self.compiled.procedure_id


@dataclass(frozen=True, slots=True)
class ProcedureAcquisitionReceipt:
    accepted: tuple[RetrievedCompiledProcedure, ...]
    rejected: tuple[RetrievedProcedureRejection, ...]


@dataclass(frozen=True, slots=True)
class RetrievedProcedureExecutionReceipt:
    success: bool
    verified: bool
    procedure_id: str
    executed_operator_ids: tuple[str, ...]
    evidence: tuple[str, ...]
    reason: str


class RetrievedProcedureAcquirer:
    """Turn retrieved procedure manifests into bounded R2.53 programs.

    External artifacts are data only.  This class never evaluates source code from a retrieval
    result.  A manifest can become executable only by naming operators already registered in the
    host-controlled R2.53 registry and surviving the existing ProcedureCompiler gates.
    """

    trainable_parameter_count = 0

    def __init__(
        self,
        registry: CognitiveOperatorRegistry,
        *,
        min_artifact_trust: float = 0.8,
        min_card_trust: float = 0.75,
        global_max_steps: int = 16,
    ) -> None:
        self.registry = registry
        self.min_artifact_trust = self._unit(min_artifact_trust, 'min_artifact_trust')
        self.min_card_trust = self._unit(min_card_trust, 'min_card_trust')
        self.compiler = ProcedureCompiler(
            registry,
            min_trust=self.min_card_trust,
            global_max_steps=global_max_steps,
        )

    @staticmethod
    def _unit(value: float, name: str) -> float:
        value = float(value)
        if not 0.0 <= value <= 1.0:
            raise ValueError(f'{name} must be in [0,1]')
        return value

    @staticmethod
    def _as_strings(payload: Mapping[str, object], key: str, *, nonempty: bool = False) -> tuple[str, ...]:
        raw = payload.get(key, ())
        if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
            raise ValueError(f'{key} must be a sequence of strings')
        out = tuple(str(value).strip() for value in raw)
        if any(not value for value in out):
            raise ValueError(f'{key} contains an empty value')
        if nonempty and not out:
            raise ValueError(f'{key} must be non-empty')
        return out

    @staticmethod
    def _parse_manifest(attachment: CognitiveAttachment) -> ProcedureCard:
        try:
            payload = json.loads(attachment.text)
        except json.JSONDecodeError as exc:
            raise ValueError(f'invalid procedure manifest JSON: {exc.msg}') from exc
        if not isinstance(payload, Mapping):
            raise ValueError('procedure manifest must be a JSON object')

        required = (
            'procedure_id', 'version', 'deficit_tags', 'context_tags', 'steps', 'preconditions',
            'expected_outputs', 'verifier_operator_id', 'max_cost', 'max_risk', 'trust_score',
            'source_uri', 'content_sha256',
        )
        missing = [key for key in required if key not in payload]
        if missing:
            raise ValueError(f'procedure manifest missing fields: {missing}')

        verifier = payload.get('verifier_operator_id')
        verifier_id = None if verifier is None else str(verifier).strip()
        if verifier is not None and not verifier_id:
            raise ValueError('verifier_operator_id must be non-empty when provided')

        return ProcedureCard(
            procedure_id=str(payload['procedure_id']).strip(),
            version=str(payload['version']).strip(),
            deficit_tags=frozenset(RetrievedProcedureAcquirer._as_strings(payload, 'deficit_tags', nonempty=True)),
            context_tags=frozenset(RetrievedProcedureAcquirer._as_strings(payload, 'context_tags')),
            steps=RetrievedProcedureAcquirer._as_strings(payload, 'steps', nonempty=True),
            preconditions=frozenset(RetrievedProcedureAcquirer._as_strings(payload, 'preconditions')),
            expected_outputs=frozenset(RetrievedProcedureAcquirer._as_strings(payload, 'expected_outputs')),
            verifier_operator_id=verifier_id,
            max_cost=float(payload['max_cost']),
            max_risk=float(payload['max_risk']),
            trust_score=float(payload['trust_score']),
            source_uri=str(payload['source_uri']).strip(),
            content_sha256=str(payload['content_sha256']).strip(),
        )

    def acquire(self, attachments: Sequence[CognitiveAttachment]) -> ProcedureAcquisitionReceipt:
        accepted: list[RetrievedCompiledProcedure] = []
        rejected: list[RetrievedProcedureRejection] = []
        for attachment in attachments:
            if attachment.kind != 'procedure':
                continue
            if content_digest(attachment.text) != attachment.content_sha256:
                rejected.append(RetrievedProcedureRejection(attachment.artifact_id, 'artifact provenance digest mismatch'))
                continue
            try:
                card = self._parse_manifest(attachment)
            except (TypeError, ValueError) as exc:
                rejected.append(RetrievedProcedureRejection(attachment.artifact_id, str(exc)))
                continue

            # Trust is conjunctive rather than substitutive: neither a trusted transport nor a
            # self-declared trusted card can rescue the other side of the boundary.
            effective_artifact_trust = min(float(attachment.trust_score), float(card.trust_score))
            if effective_artifact_trust < self.min_artifact_trust:
                rejected.append(RetrievedProcedureRejection(attachment.artifact_id, 'artifact trust below acquisition threshold'))
                continue
            if card.trust_score < self.min_card_trust:
                rejected.append(RetrievedProcedureRejection(attachment.artifact_id, 'procedure card trust below acquisition threshold'))
                continue
            try:
                compiled = self.compiler.compile(card)
            except (KeyError, TypeError, ValueError) as exc:
                rejected.append(RetrievedProcedureRejection(attachment.artifact_id, str(exc)))
                continue
            accepted.append(RetrievedCompiledProcedure(attachment.artifact_id, attachment, compiled))

        accepted.sort(
            key=lambda row: (
                -float(row.attachment.activation),
                -float(row.compiled.card.trust_score),
                row.compiled.procedure_id,
                row.compiled.card.version,
                row.artifact_id,
            )
        )
        rejected.sort(key=lambda row: row.artifact_id)
        return ProcedureAcquisitionReceipt(tuple(accepted), tuple(rejected))


class RetrievedProcedureExecutor:
    """Execute an already compiled retrieved procedure using only registered operators."""

    trainable_parameter_count = 0

    def execute(
        self,
        acquired: RetrievedCompiledProcedure,
        state: ExternalWorkingState,
        snapshot: CognitiveSnapshot,
        signal: DeficitSignal,
    ) -> RetrievedProcedureExecutionReceipt:
        procedure = acquired.compiled
        executed: list[str] = []
        evidence: list[str] = []
        verifier_success: bool | None = None

        for operator in procedure.operators:
            missing = set(operator.requires).difference(state.capabilities)
            if missing:
                return RetrievedProcedureExecutionReceipt(
                    False,
                    False,
                    procedure.procedure_id,
                    tuple(executed),
                    tuple(evidence),
                    f'runtime capability check failed before {operator.operator_id}: {sorted(missing)}',
                )

            raw = dict(operator.executor(state, snapshot, signal))
            success = bool(raw.get('success', False))
            executed.append(operator.operator_id)

            updates = raw.get('updates', {})
            if updates is not None:
                if not isinstance(updates, Mapping):
                    raise TypeError('operator updates must be a mapping')
                state.context.update(updates)

            provided = set(operator.provides)
            provided.update(map(str, raw.get('provides', ())))
            state.capabilities.update(provided)
            row_evidence = tuple(map(str, raw.get('evidence', ())))
            evidence.extend(row_evidence)
            state.evidence.extend(row_evidence)

            if operator.operator_id == procedure.card.verifier_operator_id:
                verifier_success = success
            if not success:
                reason = str(raw.get('reason', f'operator_failed:{operator.operator_id}'))
                return RetrievedProcedureExecutionReceipt(
                    False,
                    False,
                    procedure.procedure_id,
                    tuple(executed),
                    tuple(evidence),
                    reason,
                )

        verified = verifier_success if procedure.card.verifier_operator_id is not None else True
        return RetrievedProcedureExecutionReceipt(
            bool(verified),
            bool(verified),
            procedure.procedure_id,
            tuple(executed),
            tuple(evidence),
            'procedure_executed' if verified else 'verifier_rejected',
        )
