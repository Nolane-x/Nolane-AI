from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from nolane.metadata.version_discipline import (
    VersionDisciplineCode,
    discover_component_ownership,
    evaluate_revision_delta,
)


def _codes(report) -> tuple[str, ...]:
    return tuple(f.code.value for f in report.findings)


def test_semantic_change_requires_exactly_one_local_revision() -> None:
    report = evaluate_revision_delta(
        {"external.integration": 1, "external.planning": 1},
        {"external.integration": 1, "external.planning": 1},
        {"external.integration"},
    )
    assert _codes(report) == (VersionDisciplineCode.SEMANTIC_CHANGE_WITHOUT_REVISION.value,)


def test_unrelated_revision_bump_is_rejected() -> None:
    report = evaluate_revision_delta(
        {"external.integration": 1, "external.planning": 1},
        {"external.integration": 1, "external.planning": 2},
        {"external.integration"},
    )
    assert set(_codes(report)) == {
        VersionDisciplineCode.SEMANTIC_CHANGE_WITHOUT_REVISION.value,
        VersionDisciplineCode.REVISION_WITHOUT_SEMANTIC_CHANGE.value,
    }


def test_revision_jump_and_downgrade_are_categorical() -> None:
    jump = evaluate_revision_delta({"external.integration": 1}, {"external.integration": 3}, {"external.integration"})
    down = evaluate_revision_delta({"external.integration": 2}, {"external.integration": 1}, {"external.integration"})
    assert _codes(jump) == (VersionDisciplineCode.REVISION_JUMP.value,)
    assert _codes(down) == (VersionDisciplineCode.REVISION_DOWNGRADE.value,)


def test_exact_single_revision_for_exact_changed_component_is_clean() -> None:
    report = evaluate_revision_delta(
        {"external.integration": 1, "external.planning": 1},
        {"external.integration": 2, "external.planning": 1},
        {"external.integration"},
    )
    assert report.clean
    assert report.findings == ()


def test_new_component_must_bootstrap_at_zero() -> None:
    bad = evaluate_revision_delta({}, {"external.new": 1}, {"external.new"}, new_component_roots={"external.new"})
    good = evaluate_revision_delta({}, {"external.new": 0}, {"external.new"}, new_component_roots={"external.new"})
    assert _codes(bad) == (VersionDisciplineCode.NEW_COMPONENT_NOT_BOOTSTRAP.value,)
    assert good.clean


def test_removed_component_is_blocking() -> None:
    report = evaluate_revision_delta({"external.integration": 1}, {}, set())
    assert _codes(report) == (VersionDisciplineCode.REMOVED_COMPONENT.value,)


def test_findings_have_deterministic_order() -> None:
    report = evaluate_revision_delta(
        {"external.a": 2, "external.b": 4, "external.c": 1},
        {"external.a": 1, "external.b": 6, "external.c": 1},
        {"external.a", "external.b", "external.c"},
    )
    assert tuple((f.code.value, f.component_id) for f in report.findings) == tuple(
        sorted((f.code.value, f.component_id) for f in report.findings)
    )


def test_direct_component_root_owns_its_changed_module() -> None:
    sources = {
        "nolane.external_core.integration": 'COMPONENT_ID = "external.integration"\n',
        "nolane.external_core.planning": 'COMPONENT_ID = "external.planning"\n',
    }
    ownership = discover_component_ownership(sources, {"nolane.external_core.integration"}, {"external.integration", "external.planning"})
    assert ownership == {"nolane.external_core.integration": ("external.integration",)}


def test_transitive_helper_change_is_owned_by_importing_component() -> None:
    sources = {
        "nolane.external_core.integration": 'from nolane.external_core._integration_helper import run\nCOMPONENT_ID = "external.integration"\n',
        "nolane.external_core._integration_helper": 'from nolane.external_core._shared_leaf import leaf\ndef run(): return leaf()\n',
        "nolane.external_core._shared_leaf": 'def leaf(): return 1\n',
    }
    ownership = discover_component_ownership(sources, {"nolane.external_core._shared_leaf"}, {"external.integration"})
    assert ownership == {"nolane.external_core._shared_leaf": ("external.integration",)}


def test_shared_helper_change_affects_every_reachable_component() -> None:
    sources = {
        "nolane.external_core.integration": 'from nolane.external_core._shared import value\nCOMPONENT_ID = "external.integration"\n',
        "nolane.external_core.planning": 'from nolane.external_core._shared import value\nCOMPONENT_ID = "external.planning"\n',
        "nolane.external_core._shared": 'value = 1\n',
    }
    ownership = discover_component_ownership(
        sources,
        {"nolane.external_core._shared"},
        {"external.integration", "external.planning"},
    )
    assert ownership == {"nolane.external_core._shared": ("external.integration", "external.planning")}


def test_unowned_structural_module_does_not_fabricate_component_owner() -> None:
    sources = {
        "nolane.external_core.integration": 'COMPONENT_ID = "external.integration"\n',
        "nolane.external_core.structural_audit": 'VALUE = 1\n',
    }
    ownership = discover_component_ownership(sources, {"nolane.external_core.structural_audit"}, {"external.integration"})
    assert ownership == {"nolane.external_core.structural_audit": ()}


def test_duplicate_component_roots_fail_closed() -> None:
    sources = {
        "nolane.external_core.one": 'COMPONENT_ID = "external.integration"\n',
        "nolane.external_core.two": 'COMPONENT_ID = "external.integration"\n',
    }
    with pytest.raises(ValueError, match="duplicate canonical component root"):
        discover_component_ownership(sources, {"nolane.external_core.one"}, {"external.integration"})


def test_same_component_public_surface_can_depend_on_one_canonical_root() -> None:
    sources = {
        "nolane.external_core.capability_acquisition": 'COMPONENT_ID = "external.capability_acquisition"\nROOT_VALUE = 1\n',
        "nolane.external_core.capability_probation": 'from nolane.external_core.capability_acquisition import ROOT_VALUE\nCOMPONENT_ID = "external.capability_acquisition"\nSURFACE_VALUE = ROOT_VALUE\n',
    }
    ownership = discover_component_ownership(
        sources,
        {"nolane.external_core.capability_probation", "nolane.external_core.capability_acquisition"},
        {"external.capability_acquisition"},
    )
    assert ownership == {
        "nolane.external_core.capability_acquisition": ("external.capability_acquisition",),
        "nolane.external_core.capability_probation": ("external.capability_acquisition",),
    }


def test_canonical_named_root_anchors_independent_same_component_surfaces() -> None:
    sources = {
        "nolane.external_core.reasoning_invention": 'COMPONENT_ID = "external.reasoning_invention"\nROOT_VALUE = 1\n',
        "nolane.external_core.reasoning_frontier": 'COMPONENT_ID = "external.reasoning_invention"\nFRONTIER_VALUE = 2\n',
        "nolane.external_core.reasoning_review": 'COMPONENT_ID = "external.reasoning_invention"\nREVIEW_VALUE = 3\n',
    }
    ownership = discover_component_ownership(
        sources,
        {"nolane.external_core.reasoning_frontier", "nolane.external_core.reasoning_review"},
        {"external.reasoning_invention"},
    )
    assert ownership == {
        "nolane.external_core.reasoning_frontier": ("external.reasoning_invention",),
        "nolane.external_core.reasoning_review": ("external.reasoning_invention",),
    }


def test_public_component_id_can_be_exact_imported_alias_of_literal_identity() -> None:
    sources = {
        "nolane.external_core.integration_base": 'COMPONENT_ID = "external.integration"\nROOT_VALUE = 1\n',
        "nolane.external_core.integration": 'from nolane.external_core.integration_base import COMPONENT_ID as BASE_COMPONENT_ID, ROOT_VALUE\nCOMPONENT_ID = BASE_COMPONENT_ID\nSURFACE_VALUE = ROOT_VALUE\n',
    }
    ownership = discover_component_ownership(
        sources,
        {"nolane.external_core.integration"},
        {"external.integration"},
    )
    assert ownership == {"nolane.external_core.integration": ("external.integration",)}


def test_public_component_id_imported_alias_can_resolve_through_frozen_chain() -> None:
    sources = {
        "nolane.external_core._f_v09": 'COMPONENT_ID = "external.f-control"\n',
        "nolane.external_core._f_v10": 'from nolane.external_core._f_v09 import COMPONENT_ID\n',
        "nolane.external_core.software_engineering_control": 'from nolane.external_core._f_v10 import COMPONENT_ID as BASE_COMPONENT_ID\nCOMPONENT_ID = BASE_COMPONENT_ID\n',
    }
    ownership = discover_component_ownership(
        sources,
        {"nolane.external_core.software_engineering_control"},
        {"external.f-control"},
    )
    assert ownership == {"nolane.external_core.software_engineering_control": ("external.f-control",)}


def test_nonliteral_component_id_diagnostic_names_exact_module() -> None:
    sources = {
        "nolane.external_core.integration": 'COMPONENT_ID = component_id()\n',
    }
    with pytest.raises(ValueError, match=r"nolane\.external_core\.integration.*literal"):
        discover_component_ownership(sources, {"nolane.external_core.integration"}, {"external.integration"})


def test_private_component_id_alias_is_not_a_canonical_root_but_remains_reachable() -> None:
    sources = {
        "nolane.external_core.integration": 'from nolane.external_core._integration_v2 import VALUE\nCOMPONENT_ID = "external.integration"\n',
        "nolane.external_core._integration_v2": 'from nolane.external_core.integration_base import COMPONENT_ID as BASE_COMPONENT_ID\nCOMPONENT_ID = BASE_COMPONENT_ID\nVALUE = 2\n',
        "nolane.external_core.integration_base": 'COMPONENT_ID = "external.base"\n',
    }
    ownership = discover_component_ownership(
        sources,
        {"nolane.external_core._integration_v2"},
        {"external.integration", "external.base"},
    )
    assert ownership == {"nolane.external_core._integration_v2": ("external.integration",)}
