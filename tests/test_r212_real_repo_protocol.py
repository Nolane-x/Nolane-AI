import pytest

from cogcoder.r212_real_repo_protocol import (
    FORBIDDEN_PREDICTOR_FIELDS,
    PublicRepoTask,
    extract_gold_patch_files,
    redact_dataset_row,
    validate_predictor_payload,
)


def _row():
    return {
        'instance_id': 'org__repo-123',
        'repo': 'org/repo',
        'base_commit': 'a' * 40,
        'problem_statement': 'Fix FooParser when reading .foo files.',
        'patch': 'diff --git a/src/foo.c b/src/foo.c\n--- a/src/foo.c\n+++ b/src/foo.c\n',
        'test_patch': 'diff --git a/tests/test_foo.c b/tests/test_foo.c\n',
        'FAIL_TO_PASS': ['test_foo'],
        'PASS_TO_PASS': ['test_bar'],
        'pr_description': 'gold-adjacent description',
        'interface': 'FooParser',
        'meta': {'num_modified_files': 1},
        'language': 'C',
    }


def test_redaction_keeps_only_public_predictor_fields():
    public = redact_dataset_row(_row())
    assert public == {
        'instance_id': 'org__repo-123',
        'repo': 'org/repo',
        'base_commit': 'a' * 40,
        'problem_statement': 'Fix FooParser when reading .foo files.',
    }
    assert not (set(public) & FORBIDDEN_PREDICTOR_FIELDS)


def test_redaction_refuses_missing_required_field():
    row = _row()
    del row['base_commit']
    with pytest.raises(ValueError, match='base_commit'):
        redact_dataset_row(row)


def test_predictor_payload_rejects_gold_or_metadata_fields():
    payload = redact_dataset_row(_row())
    payload['patch'] = _row()['patch']
    with pytest.raises(ValueError, match='forbidden'):
        validate_predictor_payload(payload)


def test_public_task_validates_repo_and_commit_shape():
    with pytest.raises(ValueError):
        PublicRepoTask('x', 'not-a-repo', 'a' * 40, 'issue')
    with pytest.raises(ValueError):
        PublicRepoTask('x', 'org/repo', 'short', 'issue')


def test_extract_gold_patch_files_handles_add_delete_and_rename_headers():
    patch = '''diff --git a/src/a.py b/src/a.py
--- a/src/a.py
+++ b/src/a.py
@@ -1 +1 @@
-a
+b
diff --git a/old/name.c b/new/name.c
similarity index 90%
rename from old/name.c
rename to new/name.c
diff --git a/gone.txt b/gone.txt
deleted file mode 100644
--- a/gone.txt
+++ /dev/null
'''
    assert extract_gold_patch_files(patch) == ('src/a.py', 'new/name.c', 'gone.txt')


def test_gold_parser_deduplicates_paths_in_first_seen_order():
    patch = 'diff --git a/a.py b/a.py\ndiff --git a/a.py b/a.py\ndiff --git a/b.py b/b.py\n'
    assert extract_gold_patch_files(patch) == ('a.py', 'b.py')
