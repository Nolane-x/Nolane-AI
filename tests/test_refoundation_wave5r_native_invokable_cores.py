from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)


_PUBLIC_SYMBOLS = (
    "ExternalCoreSpec",
    "ExternalCoreRegistry",
    "build_default_external_core_registry",
)


def test_wave5r_canonical_invokable_core_owns_complete_public_implementation() -> None:
    import nolane.external_core.invokable as canonical

    assert all(getattr(canonical, name).__module__ == "nolane.external_core.invokable" for name in _PUBLIC_SYMBOLS)
    assert canonical.COMPONENT_ID == "external.invokable_cores"
    assert canonical.COMPONENT_VERSION == "0.0.2"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.external_core"


def test_wave5r_historical_external_core_is_exact_public_object_bridge() -> None:
    import cogcoder.organization.external_core as legacy
    import nolane.external_core.invokable as canonical

    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5r_canonical_invokable_core_has_no_reverse_authority_import() -> None:
    import nolane.external_core.invokable as canonical

    source_path = Path(canonical.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    offenders: list[str] = []
    has_native_identity_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "cogcoder.organization.external_core" or alias.name.startswith(
                    "cogcoder.organization.external_core."
                ):
                    offenders.append(f"import:{node.lineno}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "cogcoder.organization.external_core" or module.startswith(
                "cogcoder.organization.external_core."
            ):
                offenders.append(f"from:{node.lineno}:{module}")
            if module == "nolane.organization.identity" and any(alias.name == "AgentRegistry" for alias in node.names):
                has_native_identity_import = True

    assert offenders == [], "canonical invokable-core authority reverse-imports historical implementation: " + "; ".join(offenders)
    assert has_native_identity_import, "canonical invokable-core implementation must depend on native AgentRegistry authority"


def _spec(*, version: str = "0.1"):
    from nolane.external_core.invokable import ExternalCoreSpec

    return ExternalCoreSpec(
        core_id="tool.search",
        owner_agent_or_region="research",
        capabilities=("search",),
        input_schema="canonical_mapping_v1",
        output_schema="canonical_mapping_v1",
        side_effects=(),
        required_permissions=("external_core.invoke",),
        cost_model="bounded",
        failure_modes=("unavailable",),
        verification_hooks=("output_receipt",),
        version=version,
    )


def test_wave5r_registry_round_trip_and_conflicting_reregistration_remain_fail_closed() -> None:
    from nolane.external_core.invokable import ExternalCoreRegistry

    registry = ExternalCoreRegistry()
    spec = _spec()
    registry.register(spec)
    registry.register(spec)

    assert registry.get(spec.core_id) == spec
    assert registry.specs() == (spec,)
    assert ExternalCoreRegistry.from_state(registry.to_state()).to_state() == registry.to_state()

    with pytest.raises(ValueError, match="already registered differently"):
        registry.register(_spec(version="0.2"))


def test_wave5r_invokable_core_component_version_and_authority_cutover() -> None:
    implementation = build_component_implementation_ledger()
    row = implementation["external.invokable_cores"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.invokable"
    assert row.legacy_sources == ("cogcoder/organization/external_core.py",)
    assert row.canonical_write_authority
    assert row.component_version == "0.0.2"
    assert str(component_version("external.invokable_cores")) == "0.0.2"

    facade_ids = {binding.component_id for binding in build_active_facade_bindings()}
    assert "external.invokable_cores" not in facade_ids


def test_wave5r_generated_native_debt_no_longer_contains_invokable_cores() -> None:
    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    serialized = json.dumps(state, sort_keys=True)
    assert "external.invokable_cores" not in serialized

    implementation = build_component_implementation_ledger()
    non_native = [row for row in implementation.values() if row.status is not ImplementationStatus.CANONICAL_NATIVE]
    assert len(non_native) <= 28


def test_wave5r_current_status_tracks_invokable_core_cutover() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")

    assert "Wave 5R" in status
    assert "`external.invokable_cores` -> native `nolane.external_core.invokable`" in status
