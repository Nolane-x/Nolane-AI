from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


COMPONENT_ID = "external.evidence"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.types.EvidenceRecord"


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    verifier_agent_id: str
    passed: bool
    false_accepts: int = 0
    regressions: int = 0
    notes: str = ""

    def __post_init__(self) -> None:
        if self.false_accepts < 0 or self.regressions < 0:
            raise ValueError("evidence counters must be non-negative")
        if not self.evidence_id or not self.verifier_agent_id:
            raise ValueError("evidence identity must be explicit")

    def to_state(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "verifier_agent_id": self.verifier_agent_id,
            "passed": self.passed,
            "false_accepts": self.false_accepts,
            "regressions": self.regressions,
            "notes": self.notes,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EvidenceRecord":
        return cls(
            str(state["evidence_id"]),
            str(state["verifier_agent_id"]),
            bool(state["passed"]),
            int(state.get("false_accepts", 0)),
            int(state.get("regressions", 0)),
            str(state.get("notes", "")),
        )


__all__ = (
    "EvidenceRecord",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
