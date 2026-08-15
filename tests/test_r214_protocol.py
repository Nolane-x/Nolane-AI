from collections import Counter


def test_r214_suite_has_four_families_sparse_ambiguity_and_disjoint_seeded_tasks():
    from benchmarks.kfigg.r214_program_identification import build_suite

    a = build_suite(seed=21401, cases_per_family=8)
    b = build_suite(seed=31401, cases_per_family=8)
    assert len(a) == 32
    assert Counter(task.family for task in a) == {
        'xor_add_alias': 8,
        'add_mod_wrap': 8,
        'mul_mod_wrap': 8,
        'xor_mod_wrap': 8,
    }
    assert all(len(task.initial_demos) == 2 for task in a)
    assert {task.task_id for task in a}.isdisjoint({task.task_id for task in b})
    assert all(task.target_signature in {c.signature for c in task.initial_space.classes} for task in a)
    assert all(len(task.initial_space.classes) >= 2 for task in a)


def test_budget_matched_modes_never_exceed_three_oracle_calls():
    from benchmarks.kfigg.r214_program_identification import build_suite, evaluate_task

    for task in build_suite(seed=21402, cases_per_family=4):
        rows = {mode: evaluate_task(task, mode=mode, oracle_budget=3, random_seed=77)
                for mode in ('active', 'passive_fixed', 'random_budgeted')}
        assert all(row.oracle_calls <= 3 for row in rows.values())
        assert rows['active'].initial_demonstrations == rows['passive_fixed'].initial_demonstrations
        assert rows['active'].initial_demonstrations == rows['random_budgeted'].initial_demonstrations


def test_out_of_class_suite_requires_abstention_not_false_resolution():
    from benchmarks.kfigg.r214_program_identification import build_out_of_class_suite, evaluate_task

    tasks = build_out_of_class_suite(seed=21403, count=12)
    assert tasks
    for task in tasks:
        row = evaluate_task(task, mode='active', oracle_budget=3, random_seed=91)
        assert not row.correct
        assert not row.false_resolved_accept
        assert row.abstained


def test_old_regime_suite_is_in_hypothesis_class():
    from benchmarks.kfigg.r214_program_identification import build_old_regime_suite

    tasks = build_old_regime_suite(seed=21404, count=20)
    assert len(tasks) == 20
    assert all(task.target_signature in {c.signature for c in task.initial_space.classes} for task in tasks)


def test_depth3_stress_suite_is_complete_ambiguous_and_resolvable_without_truncation():
    from benchmarks.kfigg.r214_program_identification import build_depth3_stress_suite, evaluate_task

    tasks = build_depth3_stress_suite(seed=21405, cases_per_family=6)
    assert len(tasks) == 24
    assert {task.family for task in tasks} == {
        'xor_add_mod_depth3', 'mul_add_mod_depth3', 'add_xor_mod_depth3', 'mul_xor_mod_depth3'
    }
    assert all(task.initial_space.enumeration_complete for task in tasks)
    assert all(len(task.initial_space.classes) >= 2 for task in tasks)
    rows = [evaluate_task(task, mode='active', oracle_budget=3, random_seed=13) for task in tasks]
    assert sum(row.correct for row in rows) / len(rows) >= 0.85
    assert sum(row.false_resolved_accept for row in rows) == 0


def test_measure_seed_reports_all_gate_dimensions_and_budget_curve():
    from benchmarks.kfigg.r214_program_identification import measure_seed

    result = measure_seed(seed=21406, cases_per_family=2, depth3_cases_per_family=1, old_count=8, out_of_class_count=4)
    assert result['main_cases'] == 8
    assert result['depth3_cases'] == 4
    assert set(result['main_accuracy']) == {'active', 'shortest_consistent', 'passive_fixed', 'random_budgeted'}
    assert set(result['budget_curve']) == {'0', '1', '2', '3'}
    assert 0.0 <= result['retention_accuracy'] <= 1.0
    assert 0.0 <= result['out_of_class_abstention'] <= 1.0
    assert result['max_active_oracle_calls'] <= 3
    assert 0.0 <= result['identity_permutation_invariance'] <= 1.0
