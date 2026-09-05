from __future__ import annotations

import pytest

from nolane.metadata.version_discipline import (
    VersionDisciplineCode,
    discover_component_ownership,
    evaluate_revision_delta,
)


def _codes(report) -> set[str]:
    return {finding.code.value for finding in report.findings}


def test_adversarial_revision_bump_cannot_pay_for_unrelated_semantic_change() -> None:
    report = evaluate_revision_delta(
        {"external.integration": 1, "external.planning": 1},
        {"external.integration": 1, "external.planning": 2},
        {"external.integration"},
    )
    assert _codes(report) == {
        VersionDisciplineCode.SEMANTIC_CHANGE_WITHOUT_REVISION.value,
        VersionDisciplineCode.REVISION_WITHOUT_SEMANTIC_CHANGE.value,
    }


def test_adversarial_revision_jump_and_downgrade_stay_fail_closed() -> None:
    jump = evaluate_revision_delta(
        {"external.integration": 1},
        {"external.integration": 3},
        {"external.integration"},
    )
    downgrade = evaluate_revision_delta(
        {"external.integration": 2},
        {"external.integration": 1},
        {"external.integration"},
    )
    assert _codes(jump) == {VersionDisciplineCode.REVISION_JUMP.value}
    assert _codes(downgrade) == {VersionDisciplineCode.REVISION_DOWNGRADE.value}


def test_adversarial_computed_component_identity_cannot_launder_root_authority() -> None:
    sources = {
        "nolane.external_core.integration": "COMPONENT_ID = make_component_id()\n",
    }
    with pytest.raises(ValueError, match=r"nolane\.external_core\.integration.*literal"):
        discover_component_ownership(
            sources,
            {"nolane.external_core.integration"},
            {"external.integration"},
        )


def test_adversarial_independent_duplicate_roots_are_rejected() -> None:
    sources = {
        "nolane.external_core.surface_one": 'COMPONENT_ID = "external.integration"\n',
        "nolane.external_core.surface_two": 'COMPONENT_ID = "external.integration"\n',
    }
    with pytest.raises(ValueError, match="duplicate canonical component root"):
        discover_component_ownership(
            sources,
            {"nolane.external_core.surface_one"},
            {"external.integration"},
        )


def test_adversarial_shared_helper_propagates_to_every_canonical_owner() -> None:
    sources = {
        "nolane.external_core.integration": 'from nolane.external_core._shared import value\nCOMPONENT_ID = "external.integration"\n',
        "nolane.external_core.planning": 'from nolane.external_core._shared import value\nCOMPONENT_ID = "external.planning"\n',
        "nolane.external_core._shared": "value = 1\n",
    }
    ownership = discover_component_ownership(
        sources,
        {"nolane.external_core._shared"},
        {"external.integration", "external.planning"},
    )
    assert ownership == {
        "nolane.external_core._shared": ("external.integration", "external.planning"),
    }
