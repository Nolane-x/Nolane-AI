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


_PUBLIC_SYMBOLS = (
    "BenchmarkDomain",
    "EvidenceProvenanceClass",
    "EvaluationMode",
    "BenchmarkRegime",
    "BenchmarkRegimeRegistry",
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


def test_wave5af_canonical_module_owns_benchmark_regime_authority() -> None:
    import nolane.evaluation.regimes as canonical

    assert canonical.COMPONENT_ID == "evaluation.regimes"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.evaluation_regimes"
    for name in _PUBLIC_SYMBOLS:
        assert getattr(canonical, name).__module__ == "nolane.evaluation.regimes"


def test_wave5af_historical_regimes_module_bridges_exact_canonical_identity() -> None:
    import cogcoder.organization.evaluation_regimes as legacy
    import nolane.evaluation.regimes as canonical

    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5af_canonical_regimes_has_no_reverse_legacy_imports() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "nolane" / "evaluation" / "regimes.py"
    imports = _imported_modules(path.read_text(encoding="utf-8"))

    assert not any(module.startswith("cogcoder.organization") for module in imports)
    assert "nolane.core.canonical_digest" in imports


def test_wave5af_registry_roundtrip_preserves_accepted_semantics() -> None:
    from nolane.evaluation.regimes import (
        BenchmarkDomain,
        BenchmarkRegimeRegistry,
        EvidenceProvenanceClass,
    )

    registry = BenchmarkRegimeRegistry()
    row = registry.register(
        regime_id="regime-1",
        benchmark_id="bench-1",
        domain=BenchmarkDomain.CODING,
        task_set_digest="tasks",
        repository_revision_digest="repo",
        tool_envelope_digest="tools",
        compute_budget_units=10,
        tool_call_budget=5,
        external_core_budget=2,
        wall_clock_budget_ms=1000,
        active_agent_budget=3,
        freshness_epoch=1,
        evaluator_protocol_version="v1",
        provenance_class=EvidenceProvenanceClass.INTERNAL_REAL_REPOSITORY,
        fresh=True,
        heldout=True,
    )
    restored = BenchmarkRegimeRegistry.from_state(registry.to_state())

    assert restored.get("regime-1") == row
    assert restored.to_state() == registry.to_state()


def test_wave5af_authority_version_facade_and_debt_cutover() -> None:
    ledger = build_component_implementation_ledger()
    row = ledger["evaluation.regimes"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.evaluation.regimes"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("evaluation.regimes")) == "0.0.1"
    assert all(binding.component_id != "evaluation.regimes" for binding in build_active_facade_bindings())

    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in state["components"]}
    assert "evaluation.regimes" not in ids
    assert len(state["components"]) == 17

    assert ledger["external.ui_ux"].status is ImplementationStatus.CANONICAL_NATIVE


def test_wave5af_current_status_tracks_native_regime_cutover() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AF" in status
    assert "evaluation.regimes" in status
    assert "17 non-native" in status
