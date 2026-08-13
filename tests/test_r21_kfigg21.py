from __future__ import annotations


def test_case_is_multihop_and_answer_not_in_question():
    from cogcoder.kfigg21 import make_kfigg21_case
    case=make_kfigg21_case(seed=7,hops=4,distractors=30)
    assert len(case.chain)==4
    assert case.answer not in case.question
    assert case.start in case.question
    assert len(case.documents) >= 34


def test_interleaved_solver_uses_only_question_and_retrieved_evidence():
    from cogcoder.kfigg21 import make_kfigg21_case, solve_interleaved
    case=make_kfigg21_case(seed=9,hops=3,distractors=25)
    result=solve_interleaved(case,top_k=1,max_calls=4)
    assert result.answer == case.answer
    assert result.correct
    assert result.retrieval_calls <= 4
    assert result.retrieved_chunks <= 4
    assert result.provenance_ok


def test_retrieve_once_and_interleaved_have_same_total_chunk_budget():
    from cogcoder.kfigg21 import make_kfigg21_case, solve_interleaved, solve_retrieve_once
    case=make_kfigg21_case(seed=13,hops=4,distractors=40)
    once=solve_retrieve_once(case,top_k=1,max_calls=4)
    inter=solve_interleaved(case,top_k=1,max_calls=4)
    assert once.retrieved_chunks <= 4
    assert inter.retrieved_chunks <= 4
    assert once.chunk_budget == inter.chunk_budget == 4
    assert inter.correct


def test_evaluator_reports_exact_rates_and_provenance():
    from cogcoder.kfigg21 import evaluate_kfigg21
    out=evaluate_kfigg21(seeds=range(20),top_k=1,max_calls=4)
    assert out['cases']==20
    assert 0 <= out['retrieve_once_solve_rate'] <= 1
    assert 0 <= out['interleaved_solve_rate'] <= 1
    assert out['interleaved_solve_rate'] >= out['retrieve_once_solve_rate']
    assert out['provenance_failures']==0
