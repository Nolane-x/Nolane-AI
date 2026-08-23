"""Canonical organization-layer namespace.

Submodules are independently importable so historical compatibility bridges can
point into canonical implementations without triggering the full runtime graph.
The familiar package-root runtime exports remain available through lazy lookup.
"""

from __future__ import annotations

from typing import Any


__all__ = ("OrganizationRuntime", "build_first_generation_runtime")


def __getattr__(name: str) -> Any:
    if name in __all__:
        from .runtime import OrganizationRuntime, build_first_generation_runtime

        exports = {
            "OrganizationRuntime": OrganizationRuntime,
            "build_first_generation_runtime": build_first_generation_runtime,
        }
        globals().update(exports)
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
