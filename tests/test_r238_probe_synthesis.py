from dataclasses import dataclass

from cogcoder.r238_probe_language import evaluate_probe
from cogcoder.r238_probe_synthesis import synthesize_compositional_probe


@dataclass(frozen=True)
class S:
    operator_id: str
    posterior: float


def _supports():
    return tuple(S(f'h{i}', .25) for i in range(1, 5))


def test_composition_can_create_more_balanced_partition_than_any_shortlisted_atom():
    predictions = {
        'a': {'h1': True, 'h2': True, 'h3': True, 'h4': False},
        'b': {'h1': True, 'h2': True, 'h3': False, 'h4': True},
        'c': {'h1': True, 'h2': False, 'h3': True, 'h4': True},
    }
    receipt = synthesize_compositional_probe(
        tuple(predictions), _supports(), predictions, observed_probe_ids=(), atom_shortlist_size=3,
    )
    assert receipt.probe.is_composite
    assert receipt.best_disagreement == .5
    assert receipt.best_atomic_disagreement < receipt.best_disagreement
    assert receipt.candidates_evaluated <= 3 * 2 // 2 * 4


def test_synthesis_is_deterministic_and_bounded():
    predictions = {
        f'q{i}': {f'h{j}': bool((i + j) % 3) for j in range(1, 5)}
        for i in range(8)
    }
    r1 = synthesize_compositional_probe(tuple(predictions), _supports(), predictions, (), atom_shortlist_size=4)
    r2 = synthesize_compositional_probe(tuple(reversed(tuple(predictions))), _supports(), predictions, (), atom_shortlist_size=4)
    assert r1 == r2
    assert len(r1.shortlisted_atoms) == 4
    assert r1.candidates_evaluated <= 4 * 3 // 2 * 4


def test_observed_probe_is_not_selected_again():
    predictions = {
        'a': {'h1': True, 'h2': True, 'h3': True, 'h4': False},
        'b': {'h1': True, 'h2': True, 'h3': False, 'h4': True},
        'c': {'h1': True, 'h2': False, 'h3': True, 'h4': True},
    }
    first = synthesize_compositional_probe(tuple(predictions), _supports(), predictions, (), atom_shortlist_size=3)
    second = synthesize_compositional_probe(
        tuple(predictions), _supports(), predictions, (first.probe.probe_id,), atom_shortlist_size=3,
    )
    assert second.probe.probe_id != first.probe.probe_id
