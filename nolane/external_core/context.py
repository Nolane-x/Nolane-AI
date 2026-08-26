from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nolane.memory.fabric import MemoryEntry
from nolane.organization.events import CognitiveEvent

COMPONENT_ID = "external.context"
COMPONENT_VERSION = "0.0.0"
MIGRATED_FROM = "cogcoder.organization.context + cogcoder.organization.types"


@dataclass(frozen=True, slots=True)
class ContextCapsule:
    """Canonical immutable context boundary shared by context and inference layers."""

    agent_id: str
    task_id: str | None
    plan_version: int
    since_event_id: str | None
    memories: tuple[MemoryEntry, ...]
    event_delta: tuple[CognitiveEvent, ...]
    authoritative_artifacts: tuple[tuple[str, int], ...] = ()
    tools: tuple[str, ...] = ()
    external_cores: tuple[str, ...] = ()
    applicable_skill_ids: tuple[str, ...] = ()
    identity_summary: tuple[tuple[str, str], ...] = ()
    authority_boundary: tuple[str, ...] = ()
    semantic_delta_digest: str | None = None
    context_compilation_receipt_id: str | None = None
    context_budget_units: int = 0
    context_overload_ratio: float = 0.0
    stale_context_warnings: tuple[str, ...] = ()


def __getattr__(name: str) -> Any:
    # Wave 5X owns only the shared ContextCapsule schema.  Keep the accepted
    # ContextCompiler facade lazy so importing the schema cannot create a
    # canonical -> historical -> mixed-types cycle.  The compiler itself is
    # scheduled for the native external.context cutover in the next wave.
    if name == "ContextCompiler":
        from cogcoder.organization.context import ContextCompiler

        return ContextCompiler
    raise AttributeError(name)


__all__ = (
    "ContextCapsule",
    "ContextCompiler",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
