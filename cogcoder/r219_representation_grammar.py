from __future__ import annotations

import itertools

from .r219_representation_types import RepresentationHypothesis


def enumerate_hypotheses(width: int) -> tuple[RepresentationHypothesis, ...]:
    width = int(width)
    if width <= 0:
        raise ValueError('width must be positive')
    rows = []
    for permutation in itertools.permutations(range(width)):
        for complement in itertools.product((0, 1), repeat=width):
            for reverse_direction in (False, True):
                rows.append(RepresentationHypothesis(width, permutation, complement, reverse_direction))
    return tuple(sorted(rows, key=lambda row: row.representation_id))


def apply_representation(hypothesis: RepresentationHypothesis, state: tuple[int, ...]) -> tuple[int, ...]:
    state = tuple(int(v) for v in tuple(state))
    if len(state) != hypothesis.width or any(v not in (0, 1) for v in state):
        raise ValueError('state must be binary and match hypothesis width')
    return tuple(state[hypothesis.permutation[i]] ^ hypothesis.complement[i] for i in range(hypothesis.width))


def invert_representation(hypothesis: RepresentationHypothesis, latent_state: tuple[int, ...]) -> tuple[int, ...]:
    latent_state = tuple(int(v) for v in tuple(latent_state))
    if len(latent_state) != hypothesis.width or any(v not in (0, 1) for v in latent_state):
        raise ValueError('latent_state must be binary and match hypothesis width')
    raw = [0] * hypothesis.width
    for latent_index, raw_index in enumerate(hypothesis.permutation):
        raw[raw_index] = latent_state[latent_index] ^ hypothesis.complement[latent_index]
    return tuple(raw)
