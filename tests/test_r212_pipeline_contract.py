import copy
import json
import subprocess
from pathlib import Path

import pytest

from scripts.r212_prepare_public_manifest import prepare_public_rows
from scripts.r212_predict_real_repo import materialize_git_commit, validate_public_manifest
from scripts.r212_score_predictions import score_prediction_rows


def _full_row(instance='org__repo-1', language='Python'):
    return {
        'instance_id': instance,
        'repo': 'org/repo',
        'base_commit': 'a' * 40,
        'problem_statement': 'Fix `FooParser`.',
        'patch': 'diff --git a/src/parser.py b/src/parser.py\n',
        'test_patch': 'diff --git a/tests/test_parser.py b/tests/test_parser.py\n',
        'language': language,
        'FAIL_TO_PASS': ['x'],
        'PASS_TO_PASS': ['y'],
    }


def test_prepare_public_rows_strips_gold_fields():
    public = prepare_public_rows([_full_row()])
    assert public == [{
        'instance_id': 'org__repo-1',
        'repo': 'org/repo',
        'base_commit': 'a' * 40,
        'problem_statement': 'Fix `FooParser`.',
    }]


def test_predict_manifest_rejects_forbidden_gold_fields():
    public = prepare_public_rows([_full_row()])
    public[0]['patch'] = _full_row()['patch']
    with pytest.raises(ValueError, match='forbidden'):
        validate_public_manifest(public)


def test_materialize_git_commit_checks_out_exact_requested_sha(tmp_path):
    origin = tmp_path / 'origin'
    origin.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=origin, check=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=origin, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=origin, check=True)
    (origin / 'a.txt').write_text('one\n')
    subprocess.run(['git', 'add', 'a.txt'], cwd=origin, check=True)
    subprocess.run(['git', 'commit', '-qm', 'one'], cwd=origin, check=True)
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=origin, text=True).strip()

    dest = tmp_path / 'checkout'
    got = materialize_git_commit(origin.as_uri(), sha, dest, timeout_seconds=30)
    assert got == sha
    assert (dest / 'a.txt').read_text() == 'one\n'


def test_scoring_uses_patch_not_test_patch_and_does_not_mutate_predictions():
    predictions = [{
        'instance_id': 'org__repo-1',
        'status': 'ok',
        'deterministic': True,
        'path_top20': ['tests/test_parser.py', 'src/parser.py'],
        'hybrid_top20': ['src/parser.py', 'tests/test_parser.py'],
    }]
    before = copy.deepcopy(predictions)
    rows = [_full_row()]
    result = score_prediction_rows(predictions, rows)
    assert predictions == before
    assert result['materialized_tasks'] == 1
    assert result['hybrid']['hit1'] == 1.0
    assert result['path']['hit1'] == 0.0
    assert result['hybrid']['recall5'] == 1.0


def test_scoring_reports_per_language_and_failed_materialization():
    rows = [_full_row('a', 'Python'), _full_row('b', 'Rust')]
    predictions = [
        {'instance_id': 'a', 'status': 'ok', 'deterministic': True, 'path_top20': ['x'], 'hybrid_top20': ['src/parser.py']},
        {'instance_id': 'b', 'status': 'materialize_failed', 'deterministic': False, 'path_top20': [], 'hybrid_top20': []},
    ]
    result = score_prediction_rows(predictions, rows)
    assert result['tasks'] == 2
    assert result['materialized_tasks'] == 1
    assert result['per_language']['Python']['tasks'] == 1
    assert result['per_language']['Rust']['tasks'] == 1
    assert result['prediction_determinism'] == 0.5
