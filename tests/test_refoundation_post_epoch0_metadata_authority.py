from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = ROOT / "nolane"
COMPATIBILITY_ROOT = CANONICAL_ROOT / "compatibility"
HISTORICAL_METADATA_PREFIX = "cogcoder.refoundation"


def _historical_refoundation_imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(HISTORICAL_METADATA_PREFIX):
                modules.append(module)
        elif isinstance(node, ast.Import):
            modules.extend(
                alias.name
                for alias in node.names
                if alias.name.startswith(HISTORICAL_METADATA_PREFIX)
            )
    return tuple(modules)


def test_canonical_metadata_does_not_depend_on_refoundation_namespace() -> None:
    """Post-Epoch canonical metadata authority must live under ``nolane``.

    The explicit compatibility membrane may still import the accepted behavioral
    substrate, but canonical metadata, manifests, component versions, runtime
    descriptors, capability catalogs and repository audit logic must not source
    their authority from ``cogcoder.refoundation``.
    """

    violations: list[str] = []
    for path in sorted(CANONICAL_ROOT.rglob("*.py")):
        if path.is_relative_to(COMPATIBILITY_ROOT):
            continue
        relative = path.relative_to(ROOT).as_posix()
        for module in _historical_refoundation_imports(path):
            violations.append(f"{relative}:{module}")
    assert violations == []
