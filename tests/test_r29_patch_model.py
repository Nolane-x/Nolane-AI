import pytest

from cogcoder.r29_patch_model import (
    PatchCandidate,
    RepositorySnapshot,
    TextEdit,
    apply_candidate,
    patch_fingerprint,
)


def test_apply_candidate_replaces_and_inserts_lines_without_mutating_snapshot():
    snapshot = RepositorySnapshot({'a.py': 'x = 1\ny = 2\n'})
    candidate = PatchCandidate(
        candidate_id='c1',
        edits=(
            TextEdit('a.py', 1, 2, 'x = 3\n'),
            TextEdit('a.py', 3, 3, 'z = x + y\n'),
        ),
    )

    patched = apply_candidate(snapshot, candidate)

    assert snapshot.files['a.py'] == 'x = 1\ny = 2\n'
    assert patched.files['a.py'] == 'x = 3\ny = 2\nz = x + y\n'


def test_apply_candidate_rejects_overlapping_edits():
    snapshot = RepositorySnapshot({'a.py': 'a\nb\nc\n'})
    candidate = PatchCandidate(
        candidate_id='c1',
        edits=(
            TextEdit('a.py', 1, 3, 'x\n'),
            TextEdit('a.py', 2, 3, 'y\n'),
        ),
    )

    with pytest.raises(ValueError, match='overlap'):
        apply_candidate(snapshot, candidate)


def test_apply_candidate_rejects_invalid_span_and_missing_file():
    snapshot = RepositorySnapshot({'a.py': 'a\nb\n'})

    with pytest.raises(ValueError, match='span'):
        apply_candidate(snapshot, PatchCandidate('bad', (TextEdit('a.py', 0, 1, ''),)))

    with pytest.raises(KeyError):
        apply_candidate(snapshot, PatchCandidate('bad2', (TextEdit('missing.py', 1, 2, ''),)))


def test_patch_fingerprint_is_content_derived_and_candidate_id_invariant():
    edits = (
        TextEdit('a.py', 1, 2, 'x = 3\n'),
        TextEdit('b.py', 2, 2, 'extra\n'),
    )
    first = PatchCandidate('alpha', edits, parent_candidate_id='p1', provenance='one')
    renamed = PatchCandidate('beta', tuple(reversed(edits)), parent_candidate_id='p2', provenance='two')

    assert patch_fingerprint(first) == patch_fingerprint(renamed)


def test_patch_fingerprint_changes_when_replacement_changes():
    first = PatchCandidate('a', (TextEdit('a.py', 1, 2, 'x = 3\n'),))
    second = PatchCandidate('b', (TextEdit('a.py', 1, 2, 'x = 4\n'),))

    assert patch_fingerprint(first) != patch_fingerprint(second)
