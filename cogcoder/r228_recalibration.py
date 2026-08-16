from __future__ import annotations

from collections.abc import Sequence

from .r219_representation_types import VerifierObservation
from .r220_language_synthesis import OperatorProposal
from .r220_operator_discovery import initial_proposal_supports, update_proposal_supports
from .r227_evidence_ledger import EvidenceLedger, _validate_supersession


def replay_with_calibrated_cheap_reliability(
    proposals: Sequence[OperatorProposal],
    ledger: EvidenceLedger,
    *,
    cheap_channel: str,
    calibrated_reliability: float,
    complexity_weight: float,
):
    """Replay active evidence while replacing only cheap-channel reliability.

    The ledger is immutable. Superseded cheap observations remain excluded exactly
    as in R2.27; active non-cheap observations retain their recorded reliability.
    """
    calibrated = float(calibrated_reliability)
    if not 0.5 < calibrated <= 1.0:
        raise ValueError('calibrated_reliability must lie in (0.5,1.0]')
    channel = str(cheap_channel).strip().lower()
    if not channel:
        raise ValueError('cheap_channel must be non-empty')

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
        reliability = calibrated if row.channel == channel else row.reliability
        supports = update_proposal_supports(
            proposals,
            supports,
            VerifierObservation(row.query_id, row.observed_label, reliability),
            labels,
        )
    return supports
