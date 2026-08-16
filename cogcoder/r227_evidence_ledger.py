from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from .r219_representation_types import VerifierObservation
from .r220_language_synthesis import OperatorProposal
from .r220_operator_discovery import initial_proposal_supports, update_proposal_supports


@dataclass(frozen=True)
class LedgerObservation:
    observation_index: int
    query_id: str
    predicted_labels: tuple[tuple[str, bool], ...]
    observed_label: bool
    reliability: float
    channel: str
    cost: float
    supersedes: int | None = None
    superseded_by: int | None = None

    def __post_init__(self) -> None:
        idx = int(self.observation_index)
        if idx < 0:
            raise ValueError('observation_index must be non-negative')
        qid = str(self.query_id).strip().lower()
        if not qid:
            raise ValueError('query_id must be non-empty')
        rows = tuple(sorted((str(k), bool(v)) for k, v in tuple(self.predicted_labels)))
        if not rows or len({k for k, _ in rows}) != len(rows):
            raise ValueError('predicted_labels must be non-empty and unique')
        reliability = float(self.reliability)
        if not 0.5 < reliability <= 1.0:
            raise ValueError('reliability must be in (0.5, 1.0]')
        channel = str(self.channel).strip().lower()
        if not channel:
            raise ValueError('channel must be non-empty')
        cost = float(self.cost)
        if cost < 0.0:
            raise ValueError('cost must be non-negative')
        supersedes = None if self.supersedes is None else int(self.supersedes)
        superseded_by = None if self.superseded_by is None else int(self.superseded_by)
        if supersedes is not None and supersedes >= idx:
            raise ValueError('supersedes must reference an earlier observation')
        if superseded_by is not None and superseded_by <= idx:
            raise ValueError('superseded_by must reference a later observation')
        object.__setattr__(self, 'observation_index', idx)
        object.__setattr__(self, 'query_id', qid)
        object.__setattr__(self, 'predicted_labels', rows)
        object.__setattr__(self, 'observed_label', bool(self.observed_label))
        object.__setattr__(self, 'reliability', reliability)
        object.__setattr__(self, 'channel', channel)
        object.__setattr__(self, 'cost', cost)
        object.__setattr__(self, 'supersedes', supersedes)
        object.__setattr__(self, 'superseded_by', superseded_by)

    @property
    def active(self) -> bool:
        return self.superseded_by is None

    @property
    def prediction_map(self) -> dict[str, bool]:
        return dict(self.predicted_labels)


@dataclass(frozen=True)
class EvidenceLedger:
    entries: tuple[LedgerObservation, ...] = ()

    def __post_init__(self) -> None:
        rows = tuple(self.entries)
        if any(row.observation_index != i for i, row in enumerate(rows)):
            raise ValueError('ledger observation indices must be contiguous and ordered')
        object.__setattr__(self, 'entries', rows)

    @property
    def active_entries(self) -> tuple[LedgerObservation, ...]:
        return tuple(row for row in self.entries if row.active)


def _labels_tuple(predicted_labels: Mapping[str, bool]) -> tuple[tuple[str, bool], ...]:
    return tuple(sorted((str(k), bool(v)) for k, v in predicted_labels.items()))


def append_observation(
    ledger: EvidenceLedger,
    *,
    query_id: str,
    predicted_labels: Mapping[str, bool],
    observed_label: bool,
    reliability: float,
    channel: str,
    cost: float,
    supersedes: int | None = None,
) -> EvidenceLedger:
    row = LedgerObservation(
        observation_index=len(ledger.entries),
        query_id=query_id,
        predicted_labels=_labels_tuple(predicted_labels),
        observed_label=observed_label,
        reliability=reliability,
        channel=channel,
        cost=cost,
        supersedes=supersedes,
    )
    return EvidenceLedger(ledger.entries + (row,))


def _validate_supersession(ledger: EvidenceLedger) -> None:
    n = len(ledger.entries)
    for row in ledger.entries:
        if row.superseded_by is not None:
            j = row.superseded_by
            if j < 0 or j >= n:
                raise ValueError('broken supersession lineage')
            child = ledger.entries[j]
            if child.supersedes != row.observation_index or child.query_id != row.query_id:
                raise ValueError('broken supersession lineage')
        if row.supersedes is not None:
            j = row.supersedes
            if j < 0 or j >= n:
                raise ValueError('broken supersession lineage')
            parent = ledger.entries[j]
            if parent.superseded_by != row.observation_index or parent.query_id != row.query_id:
                raise ValueError('broken supersession lineage')


def supersede_observation(
    ledger: EvidenceLedger,
    *,
    observation_index: int,
    observed_label: bool,
    reliability: float,
    channel: str,
    cost: float,
) -> EvidenceLedger:
    idx = int(observation_index)
    if idx < 0 or idx >= len(ledger.entries):
        raise ValueError('observation_index out of range')
    old = ledger.entries[idx]
    if old.superseded_by is not None:
        raise ValueError('observation already superseded')
    new_idx = len(ledger.entries)
    updated = list(ledger.entries)
    updated[idx] = replace(old, superseded_by=new_idx)
    replacement = LedgerObservation(
        observation_index=new_idx,
        query_id=old.query_id,
        predicted_labels=old.predicted_labels,
        observed_label=observed_label,
        reliability=reliability,
        channel=channel,
        cost=cost,
        supersedes=idx,
    )
    result = EvidenceLedger(tuple(updated) + (replacement,))
    _validate_supersession(result)
    return result


def replay_supports(
    proposals: Sequence[OperatorProposal],
    ledger: EvidenceLedger,
    *,
    complexity_weight: float,
):
    proposals = tuple(proposals)
    _validate_supersession(ledger)
    proposal_ids = {p.operator_id for p in proposals}
    supports = initial_proposal_supports(proposals, complexity_weight=float(complexity_weight))
    for row in ledger.entries:
        labels = row.prediction_map
        if set(labels) != proposal_ids:
            raise ValueError('prediction coverage mismatch')
        if not row.active:
            continue
        supports = update_proposal_supports(
            proposals,
            supports,
            VerifierObservation(row.query_id, row.observed_label, row.reliability),
            labels,
        )
    return supports
