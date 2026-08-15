from cogcoder.r28_repo_world import RepoEdge, RepoNode, RepoWorldGraph
from cogcoder.r29_patch_model import PatchCandidate, RepositorySnapshot, TextEdit, patch_fingerprint
from cogcoder.r29_patch_search import VerificationResult, VerifierGuidedPatchSearch


def _candidate(candidate_id: str, replacement: str, *, node='core', score=0.0):
    return PatchCandidate(
        candidate_id,
        (TextEdit('app.py', 1, 2, replacement),),
        targeted_nodes=frozenset({node}),
        proposal_score=score,
    )


def _graph():
    graph = RepoWorldGraph()
    for node in ('core', 'leaf', 'api', 'test'):
        graph.add_node(RepoNode(node, 'symbol'))
    graph.add_edge(RepoEdge('api', 'core', 'depends_on'))
    graph.add_edge(RepoEdge('test', 'api', 'tests'))
    return graph


def test_duplicate_equivalent_candidates_are_evaluated_once():
    snapshot = RepositorySnapshot({'app.py': 'x = 1\n'})
    first = _candidate('first', 'x = 2\n')
    duplicate = _candidate('renamed', 'x = 2\n')
    calls = []

    def evaluator(patched, candidate):
        calls.append(candidate.candidate_id)
        return VerificationResult(0, 1, None, 0.1, False)

    outcome = VerifierGuidedPatchSearch(budget=4).search(
        snapshot, [first, duplicate], evaluator
    )

    assert not outcome.success
    assert calls == ['first']
    assert outcome.duplicate_candidates == 1


def test_search_never_accepts_high_score_without_verified_success():
    snapshot = RepositorySnapshot({'app.py': 'x = 1\n'})
    candidate = _candidate('looks-good', 'x = 2\n', score=10.0)

    def evaluator(patched, candidate):
        return VerificationResult(1, 1, False, 1.0, False, regression_detected=True)

    outcome = VerifierGuidedPatchSearch(budget=2).search(snapshot, [candidate], evaluator)

    assert not outcome.success
    assert outcome.best_result.verifier_score == 1.0
    assert outcome.best_result.full_tests_passed is False


def test_search_enforces_hard_evaluation_budget():
    snapshot = RepositorySnapshot({'app.py': 'x = 1\n'})
    candidates = [_candidate(f'c{i}', f'x = {i}\n') for i in range(1, 6)]
    calls = 0

    def evaluator(patched, candidate):
        nonlocal calls
        calls += 1
        return VerificationResult(0, 1, None, 0.0, False)

    outcome = VerifierGuidedPatchSearch(budget=3).search(snapshot, candidates, evaluator)

    assert calls == 3
    assert outcome.evaluations == 3
    assert outcome.budget_exhausted


def test_lower_blast_radius_verified_patch_is_evaluated_first():
    snapshot = RepositorySnapshot({'app.py': 'x = 1\n'})
    high_risk = _candidate('high', 'x = 2\n', node='core')
    low_risk = _candidate('low', 'x = 3\n', node='leaf')
    order = []

    def evaluator(patched, candidate):
        order.append(candidate.candidate_id)
        return VerificationResult(1, 1, True, 1.0, True)

    outcome = VerifierGuidedPatchSearch(budget=3).search(
        snapshot, [high_risk, low_risk], evaluator, graph=_graph()
    )

    assert outcome.success
    assert outcome.candidate.candidate_id == 'low'
    assert order == ['low']


def test_failed_patch_can_refine_into_verified_child_using_execution_evidence():
    snapshot = RepositorySnapshot({'app.py': 'x = 1\n'})
    initial = _candidate('initial', 'x = 2\n')

    def evaluator(patched, candidate):
        if '2' in patched.files['app.py']:
            return VerificationResult(1, 2, None, 0.6, False, observations=('edge-case-failed',))
        return VerificationResult(2, 2, True, 1.0, True)

    def refine(candidate, result):
        assert result.observations == ('edge-case-failed',)
        return [_candidate('child', 'x = 3\n', score=0.2)]

    outcome = VerifierGuidedPatchSearch(budget=3).search(
        snapshot, [initial], evaluator, refine=refine
    )

    assert outcome.success
    assert outcome.candidate.candidate_id == 'child'
    assert [step.candidate_id for step in outcome.trace] == ['initial', 'child']


def test_candidate_id_renaming_does_not_change_fingerprint_trace():
    snapshot = RepositorySnapshot({'app.py': 'x = 1\n'})

    def evaluator(patched, candidate):
        return VerificationResult(0, 1, None, 0.0, False)

    a = [_candidate('a', 'x = 2\n'), _candidate('b', 'x = 3\n')]
    b = [_candidate('renamed-1', 'x = 2\n'), _candidate('renamed-2', 'x = 3\n')]
    first = VerifierGuidedPatchSearch(budget=2).search(snapshot, a, evaluator)
    second = VerifierGuidedPatchSearch(budget=2).search(snapshot, b, evaluator)

    assert [step.fingerprint for step in first.trace] == [step.fingerprint for step in second.trace]
    assert [patch_fingerprint(item) for item in a] == [patch_fingerprint(item) for item in b]
