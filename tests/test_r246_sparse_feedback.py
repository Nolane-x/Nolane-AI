from cogcoder.r239_typed_probe_dsl import and_probe, bool_atom
from cogcoder.r246_sparse_feedback import _default_initial_test_ids, _rank_sparse_aliases


def test_initial_sparse_anchor_selection_is_target_independent_and_bounded():
    ids = tuple(f't{i:03d}' for i in range(256))
    anchors = _default_initial_test_ids(ids)
    assert len(anchors) == 8
    assert len(set(anchors)) == 8
    assert set(anchors) <= set(ids)
    assert anchors == _default_initial_test_ids(tuple(reversed(ids)))


def test_small_suite_uses_each_available_test_once():
    ids = ('a', 'b', 'c')
    assert _default_initial_test_ids(ids) == ids


def test_sparse_semantic_aliases_with_different_atom_footprints_are_both_retained():
    programs = (
        and_probe(bool_atom('a'), bool_atom('b')),
        and_probe(bool_atom('c'), bool_atom('d')),
    )
    # On the only observed test both programs are False. Sparse evidence cannot
    # justify treating them as the same hypothesis because future composition
    # legality depends on which atoms each program consumes.
    values = {'t0': {'a': False, 'b': True, 'c': True, 'd': False}}
    target = {'t0': False}
    apps = _rank_sparse_aliases(
        'm', 0, programs,
        hypothesis_ids=('t0',),
        posterior={'t0': 1.0},
        atom_values_by_hypothesis=values,
        target=target,
        representatives_per_footprint=1,
    )
    assert len(apps) == 2
    assert {app.semantic_key for app in apps} == {(False,)}
    assert {app.atom_footprint for app in apps} == {('a', 'b'), ('c', 'd')}
