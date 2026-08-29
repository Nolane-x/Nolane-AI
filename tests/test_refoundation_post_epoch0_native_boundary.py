from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = ROOT / "nolane"
COMPATIBILITY_ROOT = CANONICAL_ROOT / "compatibility"

# These are behavioral compatibility shims over the accepted Epoch-0 runtime
# substrate.  Metadata/provenance dependencies are hardened separately; this
# contract prevents behavioral authority from leaking back across the boundary.
HISTORICAL_BEHAVIORAL_PREFIXES = ("cogcoder.organization",)
HISTORICAL_BEHAVIORAL_MODULES = {
    "cogcoder.refoundation.canonical_runtime",
    "cogcoder.refoundation.temporary_work_units",
    "cogcoder.refoundation.work_units",
}


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
    return tuple(modules)


def _is_historical_behavior(module: str) -> bool:
    return module in HISTORICAL_BEHAVIORAL_MODULES or module.startswith(HISTORICAL_BEHAVIORAL_PREFIXES)


def test_historical_behavior_is_isolated_to_explicit_compatibility_membrane() -> None:
    violations: list[str] = []
    for path in sorted(CANONICAL_ROOT.rglob("*.py")):
        if path.is_relative_to(COMPATIBILITY_ROOT):
            continue
        relative = path.relative_to(ROOT).as_posix()
        for module in _imports(path):
            if _is_historical_behavior(module):
                violations.append(f"{relative}:{module}")
    assert violations == []


def test_compatibility_membrane_has_exact_non_authoritative_behavioral_allowlist() -> None:
    direct_historical = {
        module
        for path in sorted(COMPATIBILITY_ROOT.rglob("*.py"))
        for module in _imports(path)
        if _is_historical_behavior(module)
    }
    assert direct_historical == HISTORICAL_BEHAVIORAL_MODULES

    membrane = import_module("nolane.compatibility.refoundation")
    assert membrane.COMPATIBILITY_ONLY is True
    assert membrane.CANONICAL_WRITE_AUTHORITY is False
    assert set(membrane.APPROVED_BEHAVIORAL_SOURCES) == HISTORICAL_BEHAVIORAL_MODULES


def test_native_memory_surfaces_do_not_round_trip_through_historical_modules() -> None:
    expected = {
        "nolane/external_core/memory.py": "nolane.memory.fabric",
        "nolane/external_core/memory_lifecycle.py": "nolane.memory.lifecycle",
        "nolane/external_core/memory_retrieval.py": "nolane.memory.retrieval",
        "nolane/external_core/skills.py": "nolane.memory.skills",
    }
    for relative, native_module in expected.items():
        modules = _imports(ROOT / relative)
        assert native_module in modules
        assert not any(module.startswith("cogcoder.") for module in modules)
