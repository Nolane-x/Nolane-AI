from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ReliabilityPosterior:
    grid: tuple[float, ...]
    weights: tuple[float, ...]
    nominal_reliability: float
    probe_count: int = 0

    def __post_init__(self) -> None:
        grid=tuple(float(x) for x in self.grid); weights=tuple(float(x) for x in self.weights)
        if not grid or len(grid)!=len(weights): raise ValueError('grid/weights mismatch')
        if any(not .5 < x < 1.0 for x in grid): raise ValueError('reliability grid must lie in (0.5,1.0)')
        if any((not math.isfinite(w)) or w<0 for w in weights): raise ValueError('weights must be finite and nonnegative')
        total=sum(weights)
        if total<=0: raise ValueError('posterior weights must have positive mass')
        weights=tuple(w/total for w in weights)
        nominal=float(self.nominal_reliability)
        if not .5 < nominal <= 1.0: raise ValueError('nominal_reliability must lie in (0.5,1.0]')
        if int(self.probe_count)<0: raise ValueError('probe_count must be nonnegative')
        object.__setattr__(self,'grid',grid); object.__setattr__(self,'weights',weights)
        object.__setattr__(self,'nominal_reliability',nominal); object.__setattr__(self,'probe_count',int(self.probe_count))

    def posterior_mean(self) -> float:
        return sum(q*w for q,w in zip(self.grid,self.weights))

    def posterior_entropy(self) -> float:
        return -sum(w*math.log(max(w,1e-300)) for w in self.weights)

    def canonical_digest(self) -> str:
        payload={'grid':self.grid,'weights':self.weights,'nominal_reliability':self.nominal_reliability,'probe_count':self.probe_count}
        raw=json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        return hashlib.sha256(raw).hexdigest()


def make_reliability_prior(nominal_reliability: float, *, concentration: float = 8.0, grid_size: int = 49) -> ReliabilityPosterior:
    nominal=float(nominal_reliability); concentration=float(concentration); grid_size=int(grid_size)
    if not .5 < nominal <= 1.0: raise ValueError('nominal_reliability must lie in (0.5,1.0]')
    if concentration<=0 or not math.isfinite(concentration): raise ValueError('concentration must be positive and finite')
    if grid_size<5: raise ValueError('grid_size must be at least 5')
    lo,hi=.501,.999
    grid=tuple(lo+(hi-lo)*i/(grid_size-1) for i in range(grid_size))
    sigma=max(.02, math.sqrt(max(nominal*(1.0-nominal),.01)/(concentration+1.0)))
    logw=tuple(-.5*((q-min(nominal,.999))/sigma)**2 for q in grid)
    m=max(logw); weights=tuple(math.exp(x-m) for x in logw)
    return ReliabilityPosterior(grid,weights,nominal,0)


def update_reliability_from_agreement(posterior: ReliabilityPosterior, *, agrees: bool, strong_reliability: float) -> ReliabilityPosterior:
    s=float(strong_reliability)
    if not .5 < s <= 1.0: raise ValueError('strong_reliability must lie in (0.5,1.0]')
    new=[]
    for q,w in zip(posterior.grid,posterior.weights):
        p_agree=q*s+(1.0-q)*(1.0-s)
        likelihood=p_agree if bool(agrees) else (1.0-p_agree)
        new.append(w*max(likelihood,1e-300))
    return ReliabilityPosterior(posterior.grid,tuple(new),posterior.nominal_reliability,posterior.probe_count+1)
