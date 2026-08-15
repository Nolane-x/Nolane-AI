from benchmarks.codeworld.r211_multifile_cases import build_r211_cases
from cogcoder.r210_copy_edit_features import enumerate_copy_edit_candidates
from cogcoder.r29_patch_model import apply_candidate, patch_fingerprint


def test_protocol_builds_multifile_js_repos_with_hidden_random_identity():
    cases = build_r211_cases(seed=21100, count=8, providers=8, offpath=2)
    assert len(cases) == 8
    assert {case.family for case in cases} == {'arithmetic','comparison'}
    for case in cases:
        assert len(case.symbols) == 10
        assert case.provider_count == 8
        assert case.gold_path in case.snapshot.files
        assert case.gold_node_id in {symbol.node_id for symbol in case.symbols}
        public = repr(case.public_record()).lower()
        assert 'gold' not in public
        assert case.gold_path not in public
        assert case.gold_node_id not in public


def test_only_gold_location_contains_a_candidate_that_verifies_full_contract():
    case = build_r211_cases(seed=21100, count=1, providers=6, offpath=1)[0]
    successes = []
    for symbol in case.symbols:
        # off-path and reachable provider slices use the same constrained family.
        candidates = enumerate_copy_edit_candidates(symbol.source, language='javascript', target_path=symbol.path)
        for candidate in candidates:
            patched = apply_candidate(case.snapshot, candidate)
            result = case.evaluator(patched, candidate)
            if result.success:
                successes.append((symbol.node_id, patch_fingerprint(candidate)))
    assert successes == [(case.gold_node_id, case.gold_patch_fingerprint)]
