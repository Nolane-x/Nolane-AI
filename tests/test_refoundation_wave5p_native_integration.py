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
    "ChangeCandidateStatus",
    "ChangeCandidate",
    "IntegrationReceipt",
    "IntegrationGraph",
    "IntegrationControlPlane",
)


def test_wave5p_canonical_integration_owns_complete_public_implementation() -> None:
    import nolane.external_core.integration as canonical

    assert all(getattr(canonical, name).__module__ == "nolane.external_core.integration" for name in _PUBLIC_SYMBOLS)
    assert canonical.COMPONENT_ID == "external.integration"
    assert canonical.COMPONENT_VERSION == "0.0.2"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.integration"


def test_wave5p_historical_integration_is_exact_public_object_bridge() -> None:
    import cogcoder.organization.integration as legacy
    import nolane.external_core.integration as canonical

    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5p_canonical_integration_has_no_reverse_authority_import() -> None:
    import nolane.external_core.integration as canonical

    source_path = Path(canonical.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    offenders: list[str] = []
    has_native_digest_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "cogcoder.organization.integration" or alias.name.startswith(
                    "cogcoder.organization.integration."
                ):
                    offenders.append(f"import:{node.lineno}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "cogcoder.organization.integration" or module.startswith(
                "cogcoder.organization.integration."
            ):
                offenders.append(f"from:{node.lineno}:{module}")
            if module == "nolane.core.canonical_digest" and any(
                alias.name == "canonical_digest" for alias in node.names
            ):
                has_native_digest_import = True

    assert offenders == [], "canonical Integration reverse-imports historical Integration authority: " + "; ".join(offenders)
    assert has_native_digest_import, "canonical Integration must use native canonical-digest authority"


def _candidate(candidate_id: str, *, dependencies: tuple[str, ...] = ()):
    from nolane.external_core.integration import ChangeCandidate

    return ChangeCandidate(
        candidate_id=candidate_id,
        producer_agent_id="integration.worker",
        task_refs=("task-1",),
        plan_refs=("plan-1",),
        requirement_refs=("req-1",),
        architecture_version_expected=1,
        changed_component_refs=("service.api",),
        changed_interface_refs=("service.api.public",),
        dependency_candidate_ids=dependencies,
    )


def test_wave5p_dependency_cycle_rejection_remains_atomic() -> None:
    from nolane.external_core.integration import IntegrationGraph

    graph = IntegrationGraph()
    graph.add(_candidate("candidate-a"))
    graph.add(_candidate("candidate-b", dependencies=("candidate-a",)))
    before = graph.to_state()

    with pytest.raises(ValueError, match="cycle"):
        graph.update(_candidate("candidate-a", dependencies=("candidate-b",)))

    assert graph.to_state() == before


def test_wave5p_integration_order_and_snapshot_round_trip_are_deterministic() -> None:
    from nolane.external_core.integration import IntegrationGraph

    graph = IntegrationGraph()
    graph.add(_candidate("candidate-root"))
    graph.add(_candidate("candidate-leaf", dependencies=("candidate-root",)))

    assert graph.integration_order() == ("candidate-root", "candidate-leaf")
    restored = IntegrationGraph.from_state(graph.to_state())
    assert restored.to_state() == graph.to_state()
    assert restored.version == graph.version == 2


def test_wave5p_integration_component_version_and_authority_cutover() -> None:
    implementation = build_component_implementation_ledger()
    row = implementation["external.integration"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.integration"
    assert row.legacy_sources == ("cogcoder/organization/integration.py",)
    assert row.canonical_write_authority
    assert row.component_version == "0.0.2"
    assert str(component_version("external.integration")) == "0.0.2"

    facade_ids = {binding.component_id for binding in build_active_facade_bindings()}
    assert "external.integration" not in facade_ids


def test_wave5p_generated_native_debt_no_longer_contains_integration() -> None:
    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    serialized = json.dumps(state, sort_keys=True)
    assert "external.integration" not in serialized

    implementation = build_component_implementation_ledger()
    non_native = [row for row in implementation.values() if row.status is not ImplementationStatus.CANONICAL_NATIVE]
    # Wave 5P established a ceiling of 29. Later extraction waves are allowed
    # to reduce debt further; a historical contract must never force regression.
    assert len(non_native) <= 29


def test_wave5p_current_status_tracks_actual_refoundation_head() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")

    assert "Wave 5P" in status
    assert "`external.integration` -> native `nolane.external_core.integration`" in status
    assert "Active work:\n- Wave 4" not in status
