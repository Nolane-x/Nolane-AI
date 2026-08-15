from benchmarks.codeworld.r210_copy_edit_curriculum import (
    build_r210_heldout_cases,
    build_r210_training_rows,
)


def test_training_is_python_only_and_heldout_is_javascript_only():
    train = build_r210_training_rows(seed=210, rows_per_family=16)
    heldout = build_r210_heldout_cases(seed=9210, cases_per_family=24)
    assert train
    assert {row.language for row in train} == {'python'}
    assert len(heldout) == 48
    assert {case.language for case in heldout} == {'javascript'}


def test_training_and_heldout_identifiers_and_seeds_are_disjoint():
    train = build_r210_training_rows(seed=210, rows_per_family=16)
    heldout = build_r210_heldout_cases(seed=9210, cases_per_family=24)
    train_names = {row.function_name for row in train}
    heldout_names = {case.function_name for case in heldout}
    assert train_names.isdisjoint(heldout_names)
    assert {row.template_seed for row in train}.isdisjoint({case.template_seed for case in heldout})


def test_public_records_do_not_expose_gold_candidate_or_language_task_ids():
    train = build_r210_training_rows(seed=210, rows_per_family=4)
    heldout = build_r210_heldout_cases(seed=9210, cases_per_family=2)
    for record in [*(row.public_record() for row in train), *(case.public_record() for case in heldout)]:
        lowered = repr(record).lower()
        assert 'gold' not in lowered
        assert 'answer' not in lowered
        assert 'language_id' not in lowered
        assert 'task_type_id' not in lowered
        assert 'candidate_id' not in lowered


def test_every_row_has_four_candidates_and_two_public_failure_probes():
    rows = build_r210_training_rows(seed=210, rows_per_family=12)
    assert all(len(row.candidates) == 4 for row in rows)
    assert all(len(row.probes) == 2 for row in rows)
    assert all(0 <= row.gold_index < 4 for row in rows)


def test_renamed_heldout_variant_changes_surface_identifiers_but_not_gold_indices():
    base = build_r210_heldout_cases(seed=9210, cases_per_family=2, identifier_variant='base')
    renamed = build_r210_heldout_cases(seed=9210, cases_per_family=2, identifier_variant='renamed')
    assert [case.gold_index for case in base] == [case.gold_index for case in renamed]
    assert all(a.source != b.source for a, b in zip(base, renamed))
