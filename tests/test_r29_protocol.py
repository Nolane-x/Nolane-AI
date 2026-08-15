from benchmarks.codeworld.r29_patch_cases import locked_r29_cases
from cogcoder.r29_patch_model import patch_fingerprint
from cogcoder.r29_patch_search import VerifierGuidedPatchSearch


def _run(case):
    return VerifierGuidedPatchSearch(budget=case.budget).search(
        case.snapshot,
        case.initial_candidates,
        case.evaluator,
        refine=case.refine,
        graph=case.graph,
    )


def test_locked_protocol_has_exactly_four_executable_cases_and_hard_budget():
    cases = locked_r29_cases()

    assert len(cases) == 4
    assert all(case.budget <= 8 for case in cases)
    assert {case.language for case in cases} == {'python', 'javascript'}


def test_all_locked_cases_are_solved_by_verified_patch_without_false_terminal_acceptance():
    for case in locked_r29_cases():
        outcome = _run(case)
        assert outcome.success, case.name
        assert outcome.best_result.success
        assert outcome.best_result.full_tests_passed is True
        assert outcome.evaluations <= case.budget
        assert len({step.fingerprint for step in outcome.trace}) == len(outcome.trace)
        assert patch_fingerprint(outcome.candidate) == case.expected_patch_fingerprint


def test_candidate_id_renaming_preserves_content_fingerprint_trace_and_result():
    original_cases = locked_r29_cases(id_prefix='orig-')
    renamed_cases = locked_r29_cases(id_prefix='renamed-')

    for original, renamed in zip(original_cases, renamed_cases):
        a = _run(original)
        b = _run(renamed)
        assert a.success == b.success
        assert [step.fingerprint for step in a.trace] == [step.fingerprint for step in b.trace]
        assert patch_fingerprint(a.candidate) == patch_fingerprint(b.candidate)


def test_protocol_metadata_contains_no_expected_source_text_or_answer_field():
    for case in locked_r29_cases():
        record = case.public_record()
        lowered = repr(record).lower()
        assert 'expected_source' not in lowered
        assert 'gold_patch' not in lowered
        assert 'answer' not in lowered
        assert 'candidate_id' not in lowered
