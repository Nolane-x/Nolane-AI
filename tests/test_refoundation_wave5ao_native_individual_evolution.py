from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)


_MODULE_OBJECTS = {
    "individual_evolution": (
        "EvolutionLineageEntry",
        "BenchmarkObservation",
        "LongitudinalAssessment",
        "IndividualEvolutionControlPlane",
    ),
    "evolution_profiles": (
        "EvolutionProfile",
        "EvolutionProfileRegistry",
    ),
}


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_wave5ao_canonical_individual_evolution_cluster_owns_public_authority() -> None:
    canonical = importlib.import_module("nolane.external_core.individual_evolution")
    assert canonical.COMPONENT_ID == "external.individual_evolution"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.individual_evolution"

    for suffix, names in _MODULE_OBJECTS.items():
        path = _root() / "nolane" / "external_core" / f"{suffix}.py"
        assert path.exists(), f"missing canonical individual-evolution module: {suffix}"
        module = importlib.import_module(f"nolane.external_core.{suffix}")
        for name in names:
            assert getattr(module, name).__module__ == f"nolane.external_core.{suffix}"


def test_wave5ao_historical_individual_evolution_cluster_is_exact_identity_bridge() -> None:
    for suffix, names in _MODULE_OBJECTS.items():
        canonical = importlib.import_module(f"nolane.external_core.{suffix}")
        legacy = importlib.import_module(f"cogcoder.organization.{suffix}")
        for name in names:
            assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5ao_canonical_individual_evolution_has_no_reverse_legacy_imports() -> None:
    root = _root()
    for suffix in _MODULE_OBJECTS:
        path = root / "nolane" / "external_core" / f"{suffix}.py"
        assert path.exists(), f"missing canonical individual-evolution module: {suffix}"
        imports = _imports(path)
        assert not any(module.startswith("cogcoder.organization") for module in imports)

    control_imports = _imports(root / "nolane" / "external_core" / "individual_evolution.py")
    assert "nolane.external_core.assurance" in control_imports
    assert "nolane.external_core.evolution_profiles" in control_imports
    assert "nolane.memory.experience" in control_imports
    assert "nolane.memory.skills" in control_imports
    assert "nolane.organization.identity" in control_imports
    assert "nolane.external_core.self_model" in control_imports
    assert "nolane.external_core.evidence" in control_imports
    assert "nolane.core.canonical_digest" in control_imports
    assert "nolane.external_core.verification" in control_imports


def test_wave5ao_lineage_state_roundtrip_remains_stable() -> None:
    module = importlib.import_module("cogcoder.organization.individual_evolution")
    row = module.EvolutionLineageEntry(
        sequence=7,
        entry_id="wave5ao-lineage",
        agent_id="coding.unit-test.01",
        transition="skill_promoted",
        neural_version="r2.3",
        self_model_version="3",
        specialization_signature="wave5ao-signature",
        evidence_ids=("evidence-b", "evidence-a"),
        predecessor_version="r2.2",
    )
    state = row.to_state()
    restored = module.EvolutionLineageEntry.from_state(state)
    assert restored == row
    assert restored.to_state() == state


def test_wave5ao_individual_evolution_authority_version_facade_and_debt_cutover() -> None:
    row = build_component_implementation_ledger()["external.individual_evolution"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.individual_evolution"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert "cogcoder/organization/individual_evolution.py" in row.legacy_sources
    assert "cogcoder/organization/evolution_profiles.py" in row.legacy_sources
    assert str(component_version("external.individual_evolution")) == "0.0.1"
    assert all(binding.component_id != "external.individual_evolution" for binding in build_active_facade_bindings())

    state = json.loads((_root() / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in state["components"]}
    assert "external.individual_evolution" not in ids
    assert len(state["components"]) <= 8


def test_wave5ao_current_status_tracks_native_individual_evolution_cutover() -> None:
    status = (_root() / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AO" in status
    assert "external.individual_evolution" in status
    assert "8 non-native" in status
