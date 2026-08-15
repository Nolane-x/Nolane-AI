from pathlib import Path

from cogcoder.r212_real_repo_localizer import (
    extract_issue_anchors,
    rank_repository_files,
)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def test_exact_symbol_anchor_ranks_definition_first(tmp_path):
    _write(tmp_path, 'src/parser.py', 'class FooParser:\n    def parse(self, text):\n        return text\n')
    _write(tmp_path, 'src/cache.py', 'class Cache:\n    pass\n')
    _write(tmp_path, 'docs/notes.md', 'FooParser is documented here but not implemented.\n')

    ranked = rank_repository_files(tmp_path, 'FooParser fails while parsing invalid tokens.', mode='hybrid')
    assert ranked[0].path == 'src/parser.py'
    assert ranked[0].symbol_score > 0


def test_explicit_path_anchor_dominates_path_baseline(tmp_path):
    _write(tmp_path, 'src/cache/store.go', 'package cache\nfunc Put() {}\n')
    _write(tmp_path, 'src/cache/other.go', 'package cache\nfunc PutOther() {}\n')

    ranked = rank_repository_files(tmp_path, 'The bug is around `src/cache/store.go` when Put is called.', mode='path')
    assert ranked[0].path == 'src/cache/store.go'


def test_vendor_and_generated_trees_are_excluded(tmp_path):
    _write(tmp_path, 'vendor/FooParser.py', 'class FooParser: pass\n')
    _write(tmp_path, 'node_modules/pkg/FooParser.js', 'class FooParser {}\n')
    _write(tmp_path, 'src/parser.py', 'class FooParser: pass\n')

    ranked = rank_repository_files(tmp_path, 'FooParser crashes.', mode='hybrid')
    paths = [row.path for row in ranked]
    assert 'src/parser.py' in paths
    assert 'vendor/FooParser.py' not in paths
    assert 'node_modules/pkg/FooParser.js' not in paths


def test_local_dependency_propagation_boosts_referenced_peer(tmp_path):
    _write(
        tmp_path,
        'src/entry.py',
        'from .engine import run_engine\n\ndef EntryPoint(x):\n    return run_engine(x)\n',
    )
    _write(tmp_path, 'src/engine.py', 'def run_engine(x):\n    return x + 1\n')
    _write(tmp_path, 'src/unrelated.py', 'def helper(x):\n    return x\n')

    ranked = rank_repository_files(tmp_path, 'EntryPoint returns the wrong result through the engine.', mode='hybrid')
    by_path = {row.path: row for row in ranked}
    assert by_path['src/engine.py'].graph_score > 0
    assert by_path['src/engine.py'].total_score > by_path['src/unrelated.py'].total_score


def test_ranking_is_deterministic_and_ties_use_canonical_path(tmp_path):
    _write(tmp_path, 'zeta.py', 'def helper(): return 1\n')
    _write(tmp_path, 'alpha.py', 'def helper(): return 1\n')

    first = rank_repository_files(tmp_path, 'unrelated wording with no useful anchor', mode='hybrid')
    second = rank_repository_files(tmp_path, 'unrelated wording with no useful anchor', mode='hybrid')
    assert [(x.path, x.total_score) for x in first] == [(x.path, x.total_score) for x in second]
    assert [x.path for x in first[:2]] == ['alpha.py', 'zeta.py']


def test_anchor_extraction_weights_code_and_path_spans_more_than_common_words():
    anchors = extract_issue_anchors('Fix `FooParser` in `src/foo/parser.py` because parser rejects invalid input.')
    weights = {a.term: a.weight for a in anchors}
    assert weights['fooparser'] > weights['parser']
    assert weights['src/foo/parser.py'] > weights['invalid']
