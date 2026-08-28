from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import ImplementationStatus, build_component_implementation_ledger


_MODULE_OBJECTS = {
    "operations": ("OperationalReadinessDisposition", "OperationalReadinessReceipt", "OperationsControlPlane"),
    "operations_profiles": (
        "OperationsDomain", "OperationsProfile", "OperationsWorkRequest",
        "OperationsCandidateScore", "OperationsAssignmentReceipt", "OperationsProfileRegistry",
    ),
    "data_operations": ("MigrationPlan", "MigrationReadinessReceipt", "PersistenceInvariant", "ConsistencyExercise", "DataOperationsLedger"),
    "infrastructure_operations": (
        "BuildManifest", "BuildReproductionReceipt", "ObservabilityBundle",
        "ReleaseCandidate", "ReleaseReadinessReceipt", "InfrastructureOperationsLedger",
    ),
    "reliability_operations": (
        "FailureScenarioKind", "FailureExercise", "ReliabilityMatrixReceipt",
        "PerformanceMeasurement", "PerformanceClaimReceipt", "ReliabilityOperationsLedger",
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


def test_wave5ap_canonical_operations_cluster_owns_public_authority() -> None:
    control = importlib.import_module("nolane.external_core.operations")
    assert control.COMPONENT_ID == "external.operations"
    assert control.COMPONENT_VERSION == "0.0.1"
    assert control.MIGRATED_FROM == "cogcoder.organization.operations"
    for suffix, names in _MODULE_OBJECTS.items():
        path = _root() / "nolane" / "external_core" / f"{suffix}.py"
        assert path.exists(), f"missing canonical Operations module: {suffix}"
        module = importlib.import_module(f"nolane.external_core.{suffix}")
        for name in names:
            assert getattr(module, name).__module__ == f"nolane.external_core.{suffix}"


def test_wave5ap_historical_operations_cluster_is_exact_identity_bridge() -> None:
    for suffix, names in _MODULE_OBJECTS.items():
        canonical = importlib.import_module(f"nolane.external_core.{suffix}")
        legacy = importlib.import_module(f"cogcoder.organization.{suffix}")
        for name in names:
            assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5ap_canonical_operations_has_only_canonical_dependencies() -> None:
    root = _root()
    for suffix in _MODULE_OBJECTS:
        imports = _imports(root / "nolane" / "external_core" / f"{suffix}.py")
        assert not any(module.startswith("cogcoder.organization") for module in imports)
    control_imports = _imports(root / "nolane" / "external_core" / "operations.py")
    assert "nolane.external_core.artifacts" in control_imports
    assert "nolane.external_core.assurance" in control_imports
    assert "nolane.external_core.data_operations" in control_imports
    assert "nolane.memory.skills" in control_imports
    assert "nolane.external_core.infrastructure_operations" in control_imports
    assert "nolane.external_core.operations_profiles" in control_imports
    assert "nolane.organization.identity" in control_imports
    assert "nolane.external_core.reliability_operations" in control_imports
    assert "nolane.core.canonical_digest" in control_imports


def test_wave5ap_operations_authority_version_facade_and_debt_cutover() -> None:
    row = build_component_implementation_ledger()["external.operations"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.operations"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    for source in (
        "cogcoder/organization/operations.py",
        "cogcoder/organization/operations_profiles.py",
        "cogcoder/organization/data_operations.py",
        "cogcoder/organization/infrastructure_operations.py",
        "cogcoder/organization/reliability_operations.py",
    ):
        assert source in row.legacy_sources
    assert str(component_version("external.operations")) == "0.0.1"
    assert all(binding.component_id != "external.operations" for binding in build_active_facade_bindings())
    state = json.loads((_root() / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in state["components"]}
    assert "external.operations" not in ids
    assert len(state["components"]) == 7


def test_wave5ap_current_status_tracks_operations_cutover() -> None:
    status = (_root() / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AP" in status
    assert "external.operations" in status
    assert "7 non-native" in status
