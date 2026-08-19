from __future__ import annotations

from cogcoder.r269_experience_compiler import compile_meta_learning_experience
from cogcoder.r269_meta_learning_kernel import PublicTaskSignature, match_portable_experiences
from tests.test_r269_sequential_experience_compilation import DOMAIN, PARENT, _accepted_add_episode


def _target_signature(*, domain: tuple[int, ...] = DOMAIN, numeric_domain: str = "finite_integer"):
    return PublicTaskSignature(
        role_names=("p", "q"),
        numeric_domain=numeric_domain,
        allowed_binary_ops=("add", "sub", "mul", "min", "max"),
        query_space_digest="r269.sequential.domain-scope-target",
        budget_contract="diagnostic<=4;candidate<=256",
        finite_integer_values=domain if numeric_domain == "finite_integer" else (),
    )


def test_verified_meta_episode_matches_only_the_semantic_domain_it_was_verified_on():
    source_signature, source_receipt = _accepted_add_episode(("alpha", "beta"))
    learned = compile_meta_learning_experience(
        source_receipt,
        signature=source_signature,
        accepted_parent_sha=PARENT,
    )

    same = match_portable_experiences((learned,), _target_signature())[0]
    different_grid = match_portable_experiences(
        (learned,),
        _target_signature(domain=(-2, 0, 3, 7)),
    )[0]
    widened = match_portable_experiences(
        (learned,),
        _target_signature(numeric_domain="finite_numeric"),
    )[0]

    assert same.compatible is True
    assert different_grid.compatible is False
    assert different_grid.reason == "verified_meta_domain_mismatch"
    assert widened.compatible is False
    assert widened.reason == "verified_meta_domain_mismatch"
