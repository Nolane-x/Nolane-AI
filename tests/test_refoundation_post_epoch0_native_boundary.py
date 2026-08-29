from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = ROOT / "nolane"
HISTORICAL_IMPLEMENTATION_PREFIXES = (
    "cogcoder.refoundation",
    "cogcoder.organization",
)


def _historical_implementation_imports() -> tuple[str, ...]:
    violations: list[str] = []
    for path in sorted(CANONICAL_ROOT.rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith(HISTORICAL_IMPLEMENTATION_PREFIXES):
                    violations.append(f"{relative}:{node.lineno}:from {module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(HISTORICAL_IMPLEMENTATION_PREFIXES):
                        violations.append(f"{relative}:{node.lineno}:import {alias.name}")
    return tuple(violations)


def test_canonical_source_does_not_reverse_import_historical_implementation() -> None:
    """Canonical implementation ownership must point into ``nolane``, never back out."""

    assert _historical_implementation_imports() == ()
