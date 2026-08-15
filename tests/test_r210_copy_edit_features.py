import torch

from cogcoder.r210_copy_edit_features import (
    FailureProbe,
    canonicalize_source,
    encode_evidence,
    enumerate_copy_edit_candidates,
)
from cogcoder.r29_patch_model import patch_fingerprint


def test_python_and_javascript_surface_forms_share_canonical_tokens():
    py = 'def combine(alpha, beta):\n    return alpha + beta\n'
    js = 'function combine(left, right) {\n  return left + right;\n}\n'
    assert canonicalize_source(py, language='python') == canonicalize_source(js, language='javascript')


def test_identifier_renaming_is_invariant():
    a = 'def f(left, right):\n    return left * right\n'
    b = 'def f(foo, bar):\n    return foo * bar\n'
    assert canonicalize_source(a, language='python') == canonicalize_source(b, language='python')


def test_evidence_encoding_has_fixed_shape_and_no_language_or_task_id():
    probes = (
        FailureProbe((3.0, 2.0), observed=1.0, expected=5.0),
        FailureProbe((-1.0, 4.0), observed=-5.0, expected=3.0),
    )
    features = encode_evidence(probes)
    assert features.shape == (16,)
    assert features.dtype == torch.float32
    assert torch.isfinite(features).all()


def test_operator_candidate_enumeration_is_content_based_not_candidate_id_based():
    src = 'def f(a, b):\n    return a - b\n'
    first = enumerate_copy_edit_candidates(src, language='python', target_path='app.py', candidate_prefix='one-')
    renamed = enumerate_copy_edit_candidates(src, language='python', target_path='app.py', candidate_prefix='two-')

    assert len(first) >= 4
    assert [patch_fingerprint(item) for item in first] == [patch_fingerprint(item) for item in renamed]
    assert all(item.candidate_id != other.candidate_id for item, other in zip(first, renamed))
