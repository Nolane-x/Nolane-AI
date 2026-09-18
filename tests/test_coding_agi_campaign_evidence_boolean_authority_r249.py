from __future__ import annotations

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.evaluation.evidence import (
    AblationAssessment,
    MatchedBudgetComparison,
    OrganizationSuperiorityAssessment,
)
from nolane.evaluation.regimes import EvaluationMode


_BOOL_ALIASES = (0, 0.0, 1, 1.0, "", "false", "true")
_DIGEST_PRESERVING = ((False, 0), (False, 0.0), (True, 1), (True, 1.0))


def _comparison(*, comparable: object = False, improved: object = False) -> MatchedBudgetComparison:
    return MatchedBudgetComparison(
        comparison_id="comparison-r249",
        organization_observation_id="org-r249",
        baseline_observation_id="baseline-r249",
        baseline_mode=EvaluationMode.SINGLE_AGENT,
        comparable=comparable,
        improved=improved,
        score_delta=0.125,
        reason="r249",
        digest="digest-r249",
    )


def _comparison_state(*, comparable: bool, improved: bool) -> dict[str, object]:
    row = _comparison(comparable=comparable, improved=improved)
    payload = row.payload()
    return {**payload, "digest": canonical_digest(payload)}


@pytest.mark.parametrize("field", ("comparable", "improved"))
@pytest.mark.parametrize("alias", _BOOL_ALIASES)
def test_comparison_constructor_rejects_non_bool_authority_aliases(field: str, alias: object) -> None:
    kwargs = {"comparable": False, "improved": False}
    kwargs[field] = alias

    with pytest.raises(ValueError, match=rf"{field}.*exact bool"):
        _comparison(**kwargs)


@pytest.mark.parametrize("field", ("comparable", "improved"))
@pytest.mark.parametrize(("canonical", "alias"), _DIGEST_PRESERVING)
def test_comparison_restore_rejects_digest_preserving_bool_aliases(
    field: str,
    canonical: bool,
    alias: object,
) -> None:
    state = _comparison_state(comparable=False, improved=False)
    state[field] = alias
    if canonical:
        canonical_state = _comparison_state(
            comparable=field == "comparable",
            improved=field == "improved",
        )
        state = canonical_state
        state[field] = alias

    with pytest.raises(ValueError, match=rf"{field}.*exact bool"):
        MatchedBudgetComparison.from_state(state)


@pytest.mark.parametrize(("comparable", "improved"), ((False, False), (True, False), (True, True)))
def test_comparison_preserves_canonical_bool_round_trip(comparable: bool, improved: bool) -> None:
    state = _comparison_state(comparable=comparable, improved=improved)
    restored = MatchedBudgetComparison.from_state(state)

    assert restored.to_state() == state
    assert type(restored.comparable) is bool
    assert type(restored.improved) is bool


@pytest.mark.parametrize("alias", _BOOL_ALIASES)
def test_superiority_constructor_rejects_non_bool_supported_aliases(alias: object) -> None:
    with pytest.raises(ValueError, match="supported.*exact bool"):
        OrganizationSuperiorityAssessment(
            organization_observation_id="org-r249",
            comparison_ids=("comparison-r249",),
            supported=alias,
            reason="r249",
            digest="digest-r249",
        )


@pytest.mark.parametrize("supported", (False, True))
def test_superiority_preserves_canonical_bool(supported: bool) -> None:
    row = OrganizationSuperiorityAssessment(
        organization_observation_id="org-r249",
        comparison_ids=("comparison-r249",),
        supported=supported,
        reason="r249",
        digest="digest-r249",
    )

    assert row.to_state()["supported"] is supported
    assert type(row.supported) is bool


def _ablation(*, comparable: object) -> AblationAssessment:
    return AblationAssessment(
        assessment_id="ablation-r249",
        full_observation_id="org-r249",
        ablation_observation_id="ablation-observation-r249",
        ablation_mode=EvaluationMode.ORGANIZATION_NO_MEMORY,
        comparable=comparable,
        score_delta=0.1,
        false_accept_delta=0,
        regression_delta=0,
        compute_delta=1,
        reason="r249",
        digest="digest-r249",
    )


def _ablation_state(*, comparable: bool) -> dict[str, object]:
    row = _ablation(comparable=comparable)
    payload = row.payload()
    return {**payload, "digest": canonical_digest(payload)}


@pytest.mark.parametrize("alias", _BOOL_ALIASES)
def test_ablation_constructor_rejects_non_bool_comparable_aliases(alias: object) -> None:
    with pytest.raises(ValueError, match="comparable.*exact bool"):
        _ablation(comparable=alias)


@pytest.mark.parametrize(("canonical", "alias"), _DIGEST_PRESERVING)
def test_ablation_restore_rejects_digest_preserving_comparable_aliases(
    canonical: bool,
    alias: object,
) -> None:
    state = _ablation_state(comparable=canonical)
    state["comparable"] = alias

    with pytest.raises(ValueError, match="comparable.*exact bool"):
        AblationAssessment.from_state(state)


@pytest.mark.parametrize("comparable", (False, True))
def test_ablation_preserves_canonical_bool_round_trip(comparable: bool) -> None:
    state = _ablation_state(comparable=comparable)
    restored = AblationAssessment.from_state(state)

    assert restored.to_state() == state
    assert type(restored.comparable) is bool
