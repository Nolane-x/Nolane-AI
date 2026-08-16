from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .r219_representation_types import VerifierObservation
from .r222_voi_types import VerifierChannel, VerifierRegime


@dataclass(frozen=True)
class TrustShiftRegime:
    regime_id: str
    nominal_cheap: VerifierChannel
    actual_cheap_reliability: float
    strong: VerifierChannel

    def __post_init__(self) -> None:
        rid=str(self.regime_id).strip().lower()
        if not rid:
            raise ValueError('regime_id must be non-empty')
        actual=float(self.actual_cheap_reliability)
        if not 0.5 < actual <= 1.0:
            raise ValueError('actual_cheap_reliability must lie in (0.5,1.0]')
        if self.nominal_cheap.name == self.strong.name:
            raise ValueError('verifier channel names must be distinct')
        object.__setattr__(self,'regime_id',rid)
        object.__setattr__(self,'actual_cheap_reliability',actual)


def to_nominal_regime(regime: TrustShiftRegime) -> VerifierRegime:
    return VerifierRegime(regime.regime_id, regime.nominal_cheap, regime.strong)


def _latent_uniform(seed: int, regime_id: str, query_id: str, channel_name: str) -> float:
    payload=f'r228:{int(seed)}:{str(regime_id).strip().lower()}:{str(query_id).strip().lower()}:{str(channel_name).strip().lower()}'
    digest=hashlib.sha256(payload.encode()).digest()
    return int.from_bytes(digest[:8],'big') / float(1 << 64)


def simulate_miscalibrated_observation(
    seed: int,
    regime: TrustShiftRegime,
    channel_name: str,
    row,
) -> VerifierObservation:
    qid=str(row[0]).strip().lower()
    truth=bool(row[3])
    channel=str(channel_name).strip().lower()
    if channel == regime.nominal_cheap.name:
        actual=regime.actual_cheap_reliability
        reported=regime.nominal_cheap.reliability
    elif channel == regime.strong.name:
        actual=regime.strong.reliability
        reported=regime.strong.reliability
    else:
        raise ValueError('unknown verifier channel')
    u=_latent_uniform(seed,regime.regime_id,qid,channel)
    observed=truth if u < actual else (not truth)
    return VerifierObservation(qid,observed,reported)
