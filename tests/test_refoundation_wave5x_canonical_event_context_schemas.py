from __future__ import annotations

import ast
import json
from pathlib import Path

from cogcoder.refoundation.component_versions import component_version, next_component_version
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)


_EVENT_SYMBOLS = ("EventKind", "CognitiveEvent")
_CONTEXT_SCHEMA_SYMBOLS = ("ContextCapsule",)
_FORBIDDEN_LEGACY_SYMBOLS = frozenset((*_EVENT_SYMBOLS, *_CONTEXT_SCHEMA_SYMBOLS))


def test_wave5x_event_schemas_are_owned_by_canonical_events() -> None:
    import nolane.organization.events as canonical

    for name in _EVENT_SYMBOLS:
        assert getattr(canonical, name).__module__ == "nolane.organization.events"


def test_wave5x_context_capsule_is_owned_by_canonical_context() -> None:
    import nolane.external_core.context as canonical

    assert canonical.ContextCapsule.__module__ == "nolane.external_core.context"


def test_wave5x_historical_mixed_types_are_exact_schema_bridge() -> None:
    import cogcoder.organization.types as legacy
    import nolane.external_core.context as canonical_context
    import nolane.organization.events as canonical_events

    for name in _EVENT_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical_events, name)
    assert legacy.ContextCapsule is canonical_context.ContextCapsule


def test_wave5x_canonical_tree_has_no_reverse_authority_for_event_context_schemas() -> None:
    root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []

    for source_path in sorted((root / "nolane").rglob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        relative = source_path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if (node.module or "") != "cogcoder.organization.types":
                continue
            imported = {alias.name for alias in node.names}
            bad = sorted(imported & _FORBIDDEN_LEGACY_SYMBOLS)
            if bad:
                offenders.append(f"{relative}:{node.lineno}:{','.join(bad)}")

    assert offenders == [], "canonical modules still reverse-import historical event/context schemas: " + "; ".join(offenders)


def test_wave5x_event_component_revision_records_schema_authority_hardening() -> None:
    assert str(component_version("organization.events")) == "0.0.2"
    assert str(next_component_version("organization.events")) == "0.0.3"


def test_wave5x_is_prerequisite_only_and_does_not_falsely_retire_context_debt() -> None:
    ledger = build_component_implementation_ledger()
    assert ledger["organization.events"].status is ImplementationStatus.CANONICAL_NATIVE
    assert ledger["neural.inference_bridge"].status is ImplementationStatus.COMPATIBILITY_FACADE
    assert ledger["external.execution.control"].status is ImplementationStatus.COMPATIBILITY_FACADE

    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {row["component_id"] for row in state["components"]}
    assert "neural.inference_bridge" in ids
    assert "external.execution.control" in ids
    assert len(state["components"]) <= 24


def test_wave5x_current_status_tracks_event_context_schema_prerequisite() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")

    assert "Wave 5X" in status
    lowered = status.lower()
    assert "event" in lowered and "context" in lowered and "schema" in lowered
