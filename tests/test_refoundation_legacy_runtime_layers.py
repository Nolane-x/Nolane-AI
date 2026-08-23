from __future__ import annotations

from cogcoder.refoundation.legacy_runtime_layers import (
    LegacyRuntimeDisposition,
    build_legacy_runtime_layer_map,
)


def test_historical_part_runtime_chain_has_semantic_replacement_map() -> None:
    layers = build_legacy_runtime_layer_map()
    by_path = {row.legacy_path: row for row in layers}
    assert set(by_path) == {
        "cogcoder/organization/runtime_core.py",
        "cogcoder/organization/runtime_part13.py",
        "cogcoder/organization/runtime_part14.py",
        "cogcoder/organization/runtime_part15.py",
        "cogcoder/organization/runtime.py",
    }
    assert by_path["cogcoder/organization/runtime_part13.py"].semantic_components == ("organization.coordination",)
    assert by_path["cogcoder/organization/runtime_part14.py"].semantic_components == ("organization.temporary_work_units",)
    assert by_path["cogcoder/organization/runtime_part15.py"].semantic_components == ("evaluation.scaling",)
    assert by_path["cogcoder/organization/runtime.py"].semantic_components == (
        "evaluation.campaign",
        "external.execution.control",
    )


def test_no_part_layer_is_declared_canonical_source() -> None:
    for row in build_legacy_runtime_layer_map():
        assert row.disposition is LegacyRuntimeDisposition.COMPATIBILITY
        assert row.canonical_source is False
        assert row.delete_allowed is False
        assert row.replacement_modules


def test_canonical_replacement_paths_have_no_part_or_release_number_identity() -> None:
    for row in build_legacy_runtime_layer_map():
        for module in row.replacement_modules:
            assert "part13" not in module.lower()
            assert "part14" not in module.lower()
            assert "part15" not in module.lower()
            assert not module.startswith("cogcoder.organization.runtime_part")
