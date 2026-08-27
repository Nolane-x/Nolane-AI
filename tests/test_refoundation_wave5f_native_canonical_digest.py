from __future__ import annotations

import ast
import hashlib
import importlib
from pathlib import Path

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from cogcoder.refoundation.inventory import GitSnapshotInventory
from cogcoder.refoundation.manifests import FIRST_GENERATION_SNAPSHOT


ROOT = Path(__file__).resolve().parents[1]


def test_wave5f_historical_digest_behavior_is_exact_and_deterministic() -> None:
    from cogcoder.organization.types import canonical_digest, canonical_json

    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    assert canonical_digest({"b": 2, "a": 1}) == "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"

    unicode_value = {"text": "Việt Nam", "items": [3, 2, 1]}
    unicode_json = '{"items":[3,2,1],"text":"Việt Nam"}'
    assert canonical_json(unicode_value) == unicode_json
    assert canonical_digest(unicode_value) == "0fb748f5fde174b906b518f56d32f1a2f8fd38c5f511b18bc756568a853fe86a"
    assert canonical_digest(unicode_value) == hashlib.sha256(unicode_json.encode("utf-8")).hexdigest()

    assert canonical_json({"a": 1, "b": 2}) == canonical_json({"b": 2, "a": 1})
    assert canonical_digest({"a": 1, "b": 2}) == canonical_digest({"b": 2, "a": 1})
    assert canonical_digest([1, 2, 3]) != canonical_digest([3, 2, 1])


def test_wave5f_core_canonical_digest_is_native_and_versioned() -> None:
    ledger = build_component_implementation_ledger()
    row = ledger["core.canonical_digest"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.core.canonical_digest"
    assert row.canonical_write_authority is True
    assert row.component_version == "0.0.1"
    assert "cogcoder/organization/types.py" in row.legacy_sources
    assert str(component_version("core.canonical_digest")) == "0.0.1"


def test_wave5f_canonical_module_owns_both_digest_helpers() -> None:
    canonical = importlib.import_module("nolane.core.canonical_digest")

    assert canonical.COMPONENT_ID == "core.canonical_digest"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.types"
    assert canonical.canonical_json.__module__ == "nolane.core.canonical_digest"
    assert canonical.canonical_digest.__module__ == "nolane.core.canonical_digest"


def test_wave5f_historical_types_bridge_preserves_exact_function_identity() -> None:
    legacy = importlib.import_module("cogcoder.organization.types")
    canonical = importlib.import_module("nolane.core.canonical_digest")

    assert legacy.canonical_json is canonical.canonical_json
    assert legacy.canonical_digest is canonical.canonical_digest


def test_wave5f_active_canonical_and_refoundation_code_has_no_digest_reverse_imports() -> None:
    offenders: list[str] = []
    roots = (ROOT / "nolane", ROOT / "cogcoder" / "refoundation")
    target_names = {"canonical_json", "canonical_digest"}

    for source_root in roots:
        for path in sorted(source_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                if node.module != "cogcoder.organization.types":
                    continue
                imported = target_names.intersection(alias.name for alias in node.names)
                if imported:
                    names = ",".join(sorted(imported))
                    offenders.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno}:{names}")

    assert offenders == [], "active canonical/refoundation reverse imports remain: " + "; ".join(offenders)


def test_wave5f_mixed_types_source_remains_present_without_false_whole_file_destination() -> None:
    from cogcoder.organization import types as legacy_types

    assert (ROOT / "cogcoder" / "organization" / "types.py").exists()
    assert hasattr(legacy_types, "AgentIdentity")
    assert hasattr(legacy_types, "AgentRank")
    assert hasattr(legacy_types, "AgentStatus")
    assert hasattr(legacy_types, "CognitiveEvent")
    assert hasattr(legacy_types, "ContextCapsule")

    census = GitSnapshotInventory.capture(ROOT, FIRST_GENERATION_SNAPSHOT).to_census()
    assert census.get("cogcoder/organization/types.py").canonical_destination is None


def test_wave5f_debt_reduces_only_core_digest_legacy_internal_record() -> None:
    ledger = build_component_implementation_ledger()
    counts: dict[str, int] = {}
    non_native = []
    for row in ledger.values():
        if row.status is ImplementationStatus.CANONICAL_NATIVE:
            continue
        non_native.append(row)
        counts[row.status.value] = counts.get(row.status.value, 0) + 1

    assert len(non_native) <= 39
    assert ledger["core.canonical_digest"].status is ImplementationStatus.CANONICAL_NATIVE
    assert all(row.component_id != "core.canonical_digest" for row in non_native)
