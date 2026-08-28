from __future__ import annotations

import ast
import json
from pathlib import Path

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_wave5al_canonical_module_owns_evaluation_scaling_authority() -> None:
    import nolane.evaluation.scaling as canonical

    assert canonical.COMPONENT_ID == "evaluation.scaling"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.evaluation"
    assert canonical.EvaluationScalingControlPlane.__module__ == "nolane.evaluation.scaling"


def test_wave5al_historical_scaling_module_bridges_exact_canonical_identity() -> None:
    import cogcoder.organization.evaluation as legacy
    import nolane.evaluation.scaling as canonical

    assert legacy.EvaluationScalingControlPlane is canonical.EvaluationScalingControlPlane


def test_wave5al_canonical_scaling_has_no_reverse_legacy_imports() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "nolane" / "evaluation" / "scaling.py"
    imports = _imported_modules(path.read_text(encoding="utf-8"))

    assert not any(module.startswith("cogcoder.organization") for module in imports)
    assert "nolane.external_core.artifacts" in imports
    assert "nolane.evaluation.claims" in imports
    assert "nolane.evaluation.evidence" in imports
    assert "nolane.evaluation.parameters" in imports
    assert "nolane.evaluation.regimes" in imports
    assert "nolane.evaluation.release" in imports
    assert "nolane.evaluation.stress" in imports
    assert "nolane.organization.identity" in imports


def test_wave5al_empty_scaling_state_roundtrip_behavior() -> None:
    from nolane.evaluation.scaling import EvaluationScalingControlPlane
    from nolane.external_core.artifacts import ArtifactStore
    from nolane.organization.identity import AgentRegistry

    registry = AgentRegistry()
    artifacts = ArtifactStore()
    plane = EvaluationScalingControlPlane(registry=registry, artifacts=artifacts)
    assert plane.is_empty()

    state = plane.to_state()
    restored = EvaluationScalingControlPlane.from_state(
        registry=registry,
        artifacts=artifacts,
        state=state,
    )
    assert restored.is_empty()
    assert restored.to_state() == state


def test_wave5al_authority_version_facade_and_debt_cutover() -> None:
    ledger = build_component_implementation_ledger()
    row = ledger["evaluation.scaling"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.evaluation.scaling"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("evaluation.scaling")) == "0.0.1"
    assert all(binding.component_id != "evaluation.scaling" for binding in build_active_facade_bindings())

    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in state["components"]}
    assert "evaluation.scaling" not in ids
    assert len(state["components"]) <= 11
