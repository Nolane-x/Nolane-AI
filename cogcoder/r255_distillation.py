from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .r254_cognitive_retrieval import CognitiveAttachment
from .r255_reliability import _nonempty, _unit

@dataclass(frozen=True, slots=True)
class VerifiedTrajectory:
    trajectory_id: str
    deficit_tags: frozenset[str]
    context_tags: frozenset[str]
    operator_ids: tuple[str, ...]
    preconditions: frozenset[str]
    expected_outputs: frozenset[str]
    verifier_operator_id: str
    evidence: tuple[str, ...]
    verified: bool

    def __post_init__(self) -> None:
        _nonempty(self.trajectory_id, 'trajectory_id')
        _nonempty(self.verifier_operator_id, 'verifier_operator_id')
        if not self.operator_ids:
            raise ValueError('trajectory must contain operators')
        if not self.deficit_tags:
            raise ValueError('trajectory must target a deficit')


class ProcedureDistiller:
    """Compress a verified successful trajectory into a non-authoritative procedure artifact."""

    trainable_parameter_count = 0

    def __init__(self, registry, *, distilled_trust: float = 0.82) -> None:
        self.registry = registry
        self.distilled_trust = _unit(distilled_trust, 'distilled_trust')

    def distill(self, trajectory: VerifiedTrajectory) -> CognitiveAttachment:
        from .r253_external_cognition import make_procedure_digest
        if not trajectory.verified:
            raise ValueError('cannot distill an unverified trajectory')
        if trajectory.verifier_operator_id not in trajectory.operator_ids:
            raise ValueError('trajectory verifier must be part of operator_ids')
        capabilities = set(trajectory.preconditions)
        total_cost = 0.0
        survival = 1.0
        for operator_id in trajectory.operator_ids:
            if not self.registry.has(operator_id):
                raise ValueError(f'unregistered trajectory operator: {operator_id}')
            operator = self.registry.get(operator_id)
            missing = set(operator.requires).difference(capabilities)
            if missing:
                raise ValueError(f'trajectory capability gap before {operator_id}: {sorted(missing)}')
            capabilities.update(operator.provides)
            total_cost += float(operator.cost)
            survival *= 1.0 - float(operator.risk)
        if not set(trajectory.expected_outputs).issubset(capabilities):
            raise ValueError('trajectory does not provide its expected outputs')
        semantic = {
            'deficit_tags': sorted(trajectory.deficit_tags),
            'context_tags': sorted(trajectory.context_tags),
            'operator_ids': list(trajectory.operator_ids),
            'preconditions': sorted(trajectory.preconditions),
            'expected_outputs': sorted(trajectory.expected_outputs),
            'verifier_operator_id': trajectory.verifier_operator_id,
        }
        fingerprint = hashlib.sha256(json.dumps(semantic, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        procedure_id = f'distilled.{fingerprint[:16]}'
        source_uri = f'nolane://distilled/{trajectory.trajectory_id}/{fingerprint[:16]}'
        fields = dict(
            procedure_id=procedure_id,
            version='1',
            deficit_tags=trajectory.deficit_tags,
            context_tags=trajectory.context_tags,
            steps=trajectory.operator_ids,
            preconditions=trajectory.preconditions,
            expected_outputs=trajectory.expected_outputs,
            verifier_operator_id=trajectory.verifier_operator_id,
            max_cost=total_cost + 1e-9,
            max_risk=min(1.0, 1.0 - survival + 1e-9),
            trust_score=self.distilled_trust,
            source_uri=source_uri,
        )
        manifest = json.dumps({
            **fields,
            'deficit_tags': sorted(fields['deficit_tags']),
            'context_tags': sorted(fields['context_tags']),
            'steps': list(fields['steps']),
            'preconditions': sorted(fields['preconditions']),
            'expected_outputs': sorted(fields['expected_outputs']),
            'content_sha256': make_procedure_digest(**fields),
            'distillation_evidence': list(trajectory.evidence),
            'distilled_from_trajectory': trajectory.trajectory_id,
        }, sort_keys=True)
        return CognitiveAttachment(
            artifact_id=procedure_id,
            kind='procedure',
            text=manifest,
            source_uri=source_uri,
            version='1',
            activation=0.6,
            trust_score=self.distilled_trust,
            rationale=('verified-trajectory-distillation', 'non-authoritative-until-promoted'),
            content_sha256=hashlib.sha256(manifest.encode('utf-8')).hexdigest(),
        )
