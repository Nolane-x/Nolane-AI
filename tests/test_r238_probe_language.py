import dataclasses
import pytest

from cogcoder.r238_probe_language import (
    ProbeProgram,
    atom_probe,
    compose_probe,
    evaluate_probe,
    probe_prediction_row,
)


def test_atom_and_composite_ids_are_canonical_and_commutative():
    a = atom_probe('q:a')
    b = atom_probe('q:b')
    assert a.probe_id == atom_probe('q:a').probe_id
    for op in ('xor', 'equiv', 'and', 'or'):
        left = compose_probe(op, a, b)
        right = compose_probe(op, b, a)
        assert left == right
        assert left.probe_id == right.probe_id
        assert left.is_composite
        assert left.mdl_cost == 3


def test_probe_language_truth_tables_and_prediction_row():
    a = atom_probe('a')
    b = atom_probe('b')
    labels = {'a': True, 'b': False}
    assert evaluate_probe(a, labels) is True
    assert evaluate_probe(compose_probe('xor', a, b), labels) is True
    assert evaluate_probe(compose_probe('equiv', a, b), labels) is False
    assert evaluate_probe(compose_probe('and', a, b), labels) is False
    assert evaluate_probe(compose_probe('or', a, b), labels) is True

    atom_predictions = {
        'a': {'h1': True, 'h2': False},
        'b': {'h1': False, 'h2': False},
    }
    row = probe_prediction_row(compose_probe('xor', a, b), atom_predictions)
    assert row == {'h1': True, 'h2': False}


def test_probe_program_rejects_illegal_shape_and_has_no_hidden_inference_fields():
    with pytest.raises(ValueError):
        compose_probe('not-a-real-op', atom_probe('a'), atom_probe('b'))
    with pytest.raises(ValueError):
        atom_probe('')
    names = {f.name for f in dataclasses.fields(ProbeProgram)}
    forbidden = {'seed', 'domain', 'task_family', 'target', 'truth', 'heldout', 'actual_reliability', 'evaluator_reliability'}
    assert names.isdisjoint(forbidden)
