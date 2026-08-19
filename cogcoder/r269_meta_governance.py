from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Sequence

from .r269_causal_basis_adapter import PortableExperience
from .r269_meta_learning_kernel import PublicTaskSignature
from .r269_transfer_runtime import MetaLearningReceipt, PriorRegistry

_GAP_TYPES = frozenset({
    'representation_gap', 'retrieval_gap', 'binding_gap', 'search_budget_gap',
    'experiment_selection_gap', 'operator_gap', 'verification_gap',
    'tool_oracle_gap', 'negative_transfer_gap',
})


def _nonempty(value: object, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f'{name} must be non-empty')
    return text


def _digest(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class MetaCreditRecord:
    prior_digest: str
    structural_class_digest: str
    credited: bool
    oracle_call_advantage: int
    search_work_advantage: int
    rollback_identity: str
    evidence_digests: tuple[str, ...]
    reason: str
    record_digest: str

    def __post_init__(self) -> None:
        if not self.prior_digest or not self.structural_class_digest:
            raise ValueError('credit identity must be non-empty')
        if not self.rollback_identity:
            raise ValueError('rollback_identity must be non-empty')
        if not self.evidence_digests:
            raise ValueError('credit requires verifier evidence digests')
        payload = {
            'prior_digest': self.prior_digest,
            'structural_class_digest': self.structural_class_digest,
            'credited': self.credited,
            'oracle_call_advantage': self.oracle_call_advantage,
            'search_work_advantage': self.search_work_advantage,
            'rollback_identity': self.rollback_identity,
            'evidence_digests': list(self.evidence_digests),
            'reason': self.reason,
        }
        if self.record_digest != _digest(payload):
            raise ValueError('record_digest must bind exact meta-credit content')


class MetaCreditLedger:
    def __init__(self) -> None:
        self._records: list[MetaCreditRecord] = []

    @property
    def records(self) -> tuple[MetaCreditRecord, ...]:
        return tuple(self._records)

    def append(self, record: MetaCreditRecord) -> None:
        if not isinstance(record, MetaCreditRecord):
            raise TypeError('record must be MetaCreditRecord')
        self._records.append(record)


@dataclass(frozen=True, slots=True)
class CapabilityGapRecord:
    gap_type: str
    structural_class_digest: str
    failure_receipt_digests: tuple[str, ...]
    falsified_prior_digests: tuple[str, ...]
    observation_cost: int
    search_cost: int
    required_evidence: str
    gap_digest: str

    def __post_init__(self) -> None:
        if self.gap_type not in _GAP_TYPES:
            raise ValueError('unsupported capability gap type')
        if not self.structural_class_digest:
            raise ValueError('structural_class_digest must be non-empty')
        if not self.failure_receipt_digests:
            raise ValueError('failure_receipt_digests must be non-empty')
        if self.observation_cost < 0 or self.search_cost < 0:
            raise ValueError('gap costs must be non-negative')
        if not self.required_evidence:
            raise ValueError('required_evidence must be non-empty')
        payload = {
            'gap_type': self.gap_type,
            'structural_class_digest': self.structural_class_digest,
            'failure_receipt_digests': sorted(self.failure_receipt_digests),
            'falsified_prior_digests': sorted(self.falsified_prior_digests),
            'observation_cost': self.observation_cost,
            'search_cost': self.search_cost,
            'required_evidence': self.required_evidence,
        }
        if self.gap_digest != _digest(payload):
            raise ValueError('gap_digest must bind exact gap content')


class CapabilityGapLedger:
    def __init__(self) -> None:
        self._records: list[CapabilityGapRecord] = []
        self._counts: dict[str, int] = {}

    @property
    def records(self) -> tuple[CapabilityGapRecord, ...]:
        return tuple(self._records)

    def append(self, record: CapabilityGapRecord) -> None:
        if not isinstance(record, CapabilityGapRecord):
            raise TypeError('record must be CapabilityGapRecord')
        self._records.append(record)
        self._counts[record.gap_digest] = self._counts.get(record.gap_digest, 0) + 1

    def recurrence_count(self, gap_digest: str) -> int:
        return self._counts.get(str(gap_digest), 0)


def _make_credit_record(*, prior: PortableExperience, signature: PublicTaskSignature, credited: bool, oracle_advantage: int, search_advantage: int, rollback_identity: str, evidence_digests: Sequence[str], reason: str) -> MetaCreditRecord:
    evidence = tuple(sorted({_nonempty(row, 'evidence digest') for row in evidence_digests}))
    rollback = _nonempty(rollback_identity, 'rollback_identity')
    payload = {
        'prior_digest': prior.portable_digest,
        'structural_class_digest': signature.structural_class_digest,
        'credited': bool(credited),
        'oracle_call_advantage': int(oracle_advantage),
        'search_work_advantage': int(search_advantage),
        'rollback_identity': rollback,
        'evidence_digests': list(evidence),
        'reason': str(reason),
    }
    return MetaCreditRecord(
        prior_digest=prior.portable_digest,
        structural_class_digest=signature.structural_class_digest,
        credited=bool(credited),
        oracle_call_advantage=int(oracle_advantage),
        search_work_advantage=int(search_advantage),
        rollback_identity=rollback,
        evidence_digests=evidence,
        reason=str(reason),
        record_digest=_digest(payload),
    )


def adjudicate_prior_credit(*, prior: PortableExperience, signature: PublicTaskSignature, accepted_receipt: MetaLearningReceipt, ablation_receipt: MetaLearningReceipt, registry: PriorRegistry, credit_ledger: MetaCreditLedger, rollback_identity: str, evidence_digests: Sequence[str]) -> MetaCreditRecord:
    if not isinstance(prior, PortableExperience):
        raise TypeError('prior must be PortableExperience')
    if not isinstance(signature, PublicTaskSignature):
        raise TypeError('signature must be PublicTaskSignature')
    if not isinstance(accepted_receipt, MetaLearningReceipt) or not isinstance(ablation_receipt, MetaLearningReceipt):
        raise TypeError('receipts must be MetaLearningReceipt')
    if not isinstance(registry, PriorRegistry) or not isinstance(credit_ledger, MetaCreditLedger):
        raise TypeError('governance ledgers are invalid')

    oracle_advantage = ablation_receipt.physical_diagnostic_calls - accepted_receipt.physical_diagnostic_calls
    accepted_work = accepted_receipt.transfer_candidates_considered if accepted_receipt.mode == 'transfer' else accepted_receipt.scratch_candidates_considered
    search_advantage = ablation_receipt.scratch_candidates_considered - accepted_work

    if not accepted_receipt.passed or accepted_receipt.false_accepts != 0:
        credited = False; reason = 'target_not_accepted'
    elif accepted_receipt.mode != 'transfer' or accepted_receipt.selected_prior_digest != prior.portable_digest:
        credited = False; reason = 'prior_not_causally_selected'
    elif ablation_receipt.passed and oracle_advantage <= 0 and search_advantage <= 0:
        credited = False; reason = 'ablation_retains_advantage'
    else:
        credited = True; reason = 'ablation_supported_prior_credit'

    record = _make_credit_record(
        prior=prior, signature=signature, credited=credited,
        oracle_advantage=oracle_advantage, search_advantage=search_advantage,
        rollback_identity=rollback_identity, evidence_digests=evidence_digests, reason=reason,
    )
    credit_ledger.append(record)
    if credited:
        registry.credit(prior.portable_digest, 1)
    return record


def record_capability_gap(*, ledger: CapabilityGapLedger, gap_type: str, signature: PublicTaskSignature, failure_receipt_digests: Sequence[str], falsified_prior_digests: Sequence[str], observation_cost: int, search_cost: int, required_evidence: str) -> CapabilityGapRecord:
    if not isinstance(ledger, CapabilityGapLedger):
        raise TypeError('ledger must be CapabilityGapLedger')
    if not isinstance(signature, PublicTaskSignature):
        raise TypeError('signature must be PublicTaskSignature')
    gap_type = str(gap_type)
    if gap_type not in _GAP_TYPES:
        raise ValueError('unsupported capability gap type')
    failures = tuple(sorted({_nonempty(row, 'failure receipt digest') for row in failure_receipt_digests}))
    priors = tuple(sorted({_nonempty(row, 'falsified prior digest') for row in falsified_prior_digests}))
    required = _nonempty(required_evidence, 'required_evidence')
    observation_cost = int(observation_cost); search_cost = int(search_cost)
    payload = {
        'gap_type': gap_type,
        'structural_class_digest': signature.structural_class_digest,
        'failure_receipt_digests': list(failures),
        'falsified_prior_digests': list(priors),
        'observation_cost': observation_cost,
        'search_cost': search_cost,
        'required_evidence': required,
    }
    record = CapabilityGapRecord(
        gap_type=gap_type,
        structural_class_digest=signature.structural_class_digest,
        failure_receipt_digests=failures,
        falsified_prior_digests=priors,
        observation_cost=observation_cost,
        search_cost=search_cost,
        required_evidence=required,
        gap_digest=_digest(payload),
    )
    ledger.append(record)
    return record


__all__ = [
    'MetaCreditRecord', 'MetaCreditLedger', 'CapabilityGapRecord', 'CapabilityGapLedger',
    'adjudicate_prior_credit', 'record_capability_gap',
]
