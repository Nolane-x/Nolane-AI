from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Mapping, Sequence

from .r238_probe_language import OPS, ProbeProgram, atom_probe, compose_probe, probe_prediction_row


@dataclass(frozen=True)
class ProbeSynthesisReceipt:
    probe: ProbeProgram
    shortlisted_atoms: tuple[str, ...]
    candidates_evaluated: int
    best_disagreement: float
    best_atomic_disagreement: float


def _posterior(supports) -> dict[str, float]:
    rows = {str(s.operator_id): float(s.posterior) for s in supports}
    total = sum(rows.values())
    if not rows or total <= 0:
        raise ValueError('supports must contain positive posterior mass')
    return {k: v / total for k, v in rows.items()}


def _disagreement(row: Mapping[str, bool], posterior: Mapping[str, float]) -> float:
    if set(map(str, row)) != set(posterior):
        raise ValueError('prediction coverage mismatch')
    p_true = sum(posterior[str(hid)] for hid, label in row.items() if bool(label))
    return 2.0 * p_true * (1.0 - p_true)


def synthesize_compositional_probe(
    atom_query_ids: Sequence[str],
    supports,
    atom_predictions: Mapping[str, Mapping[str, bool]],
    observed_probe_ids,
    *,
    atom_shortlist_size: int = 16,
) -> ProbeSynthesisReceipt:
    posterior = _posterior(supports)
    ids = tuple(sorted({str(q) for q in atom_query_ids}))
    if len(ids) < 2:
        raise ValueError('at least two atomic queries are required')
    if atom_shortlist_size < 2:
        raise ValueError('atom_shortlist_size must be at least 2')
    for qid in ids:
        if qid not in atom_predictions:
            raise ValueError('missing atomic prediction row')
    ranked_atoms = sorted(
        ids,
        key=lambda qid: (-_disagreement(atom_predictions[qid], posterior), qid),
    )
    shortlist = tuple(ranked_atoms[: min(int(atom_shortlist_size), len(ranked_atoms))])
    best_atomic = max(_disagreement(atom_predictions[qid], posterior) for qid in shortlist)
    observed = {str(v) for v in observed_probe_ids}

    scored: list[tuple[float, str, ProbeProgram]] = []
    evaluated = 0
    for left_id, right_id in itertools.combinations(shortlist, 2):
        left = atom_probe(left_id)
        right = atom_probe(right_id)
        for op in sorted(OPS):
            probe = compose_probe(op, left, right)
            if probe.probe_id in observed:
                continue
            row = probe_prediction_row(probe, atom_predictions)
            disagreement = _disagreement(row, posterior)
            evaluated += 1
            scored.append((-disagreement, probe.probe_id, probe))
    if not scored:
        raise ValueError('no legal unobserved compositional probe remains')
    neg, _, probe = min(scored)
    return ProbeSynthesisReceipt(
        probe=probe,
        shortlisted_atoms=shortlist,
        candidates_evaluated=evaluated,
        best_disagreement=-neg,
        best_atomic_disagreement=best_atomic,
    )
