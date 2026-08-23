from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from cogcoder.organization.types import canonical_digest


@dataclass(frozen=True, slots=True)
class RuntimeStateBinding:
    legacy_section: str
    canonical_owner: str
    legacy_semantics: bool = False

    def __post_init__(self) -> None:
        if not self.legacy_section.strip() or not self.canonical_owner.strip():
            raise ValueError("runtime state binding requires legacy section and canonical owner")

    def to_state(self) -> dict[str, Any]:
        return {
            "legacy_section": self.legacy_section,
            "canonical_owner": self.canonical_owner,
            "legacy_semantics": self.legacy_semantics,
        }


def build_runtime_state_bindings() -> tuple[RuntimeStateBinding, ...]:
    """Total ownership map for the current OrganizationRuntime.to_state shape.

    Multiple historical sections may be owned by one canonical component, but
    every legacy section has exactly one owner and its raw state is retained.
    """

    return (
        RuntimeStateBinding("registry", "organization.identity"),
        RuntimeStateBinding("ledger", "organization.events"),
        RuntimeStateBinding("authority", "organization.authority"),
        RuntimeStateBinding("memory", "external.memory.fabric"),
        RuntimeStateBinding("tasks", "organization.tasks"),
        RuntimeStateBinding("scheduler", "organization.lifecycle"),
        RuntimeStateBinding("evolution", "external.skills"),
        RuntimeStateBinding("verification", "external.verification"),
        RuntimeStateBinding("artifacts", "external.artifacts"),
        RuntimeStateBinding("external_cores", "external.invokable_cores"),
        RuntimeStateBinding("self_models", "external.self_model"),
        RuntimeStateBinding("requirements", "external.requirements"),
        RuntimeStateBinding("planning", "external.planning"),
        RuntimeStateBinding("architecture", "external.architecture"),
        RuntimeStateBinding("adr", "external.architecture", legacy_semantics=True),
        RuntimeStateBinding("integration", "external.integration"),
        RuntimeStateBinding("coding", "external.coding.control"),
        RuntimeStateBinding("debugging", "external.debugging"),
        RuntimeStateBinding("ui", "external.ui_ux"),
        RuntimeStateBinding("assurance", "external.assurance"),
        RuntimeStateBinding("operations", "external.operations"),
        RuntimeStateBinding("research", "external.research"),
        RuntimeStateBinding("memory_context", "external.context"),
        RuntimeStateBinding("individual_evolution", "external.individual_evolution"),
        RuntimeStateBinding("central", "organization.central"),
        RuntimeStateBinding("coordination", "organization.coordination", legacy_semantics=True),
        RuntimeStateBinding("foundry", "organization.temporary_work_units", legacy_semantics=True),
        RuntimeStateBinding("evaluation_scaling", "evaluation.scaling", legacy_semantics=True),
        RuntimeStateBinding("evaluation_campaign", "evaluation.campaign"),
        RuntimeStateBinding("execution", "external.execution.control"),
    )


@dataclass(frozen=True, slots=True)
class RuntimeStateEnvelope:
    legacy_section_count: int
    mapped_section_count: int
    unmapped_sections: tuple[str, ...]
    legacy_state_digest: str
    sections: Mapping[str, Mapping[str, Any]]
    digest: str

    @property
    def lossless(self) -> bool:
        return (
            not self.unmapped_sections
            and self.legacy_section_count == self.mapped_section_count
            and len(self.sections) == self.mapped_section_count
        )

    def section(self, legacy_section: str) -> Mapping[str, Any]:
        try:
            return self.sections[str(legacy_section)]
        except KeyError as exc:
            raise KeyError(f"runtime envelope has no legacy section: {legacy_section}") from exc

    def payload(self) -> dict[str, Any]:
        return {
            "legacy_section_count": self.legacy_section_count,
            "mapped_section_count": self.mapped_section_count,
            "unmapped_sections": list(self.unmapped_sections),
            "legacy_state_digest": self.legacy_state_digest,
            "sections": {key: dict(self.sections[key]) for key in sorted(self.sections)},
        }

    def __post_init__(self) -> None:
        if canonical_digest(self.payload()) != self.digest:
            raise ValueError("runtime state envelope digest mismatch")


class RuntimeStateMapper:
    def __init__(self, bindings: tuple[RuntimeStateBinding, ...] | None = None) -> None:
        rows = bindings or build_runtime_state_bindings()
        self._bindings: dict[str, RuntimeStateBinding] = {}
        for row in rows:
            if row.legacy_section in self._bindings:
                raise ValueError(f"duplicate runtime state binding: {row.legacy_section}")
            self._bindings[row.legacy_section] = row

    def map_state(self, state: Mapping[str, Any]) -> RuntimeStateEnvelope:
        raw = {str(key): value for key, value in state.items()}
        unknown = tuple(sorted(set(raw) - set(self._bindings)))
        missing = tuple(sorted(set(self._bindings) - set(raw)))
        if unknown or missing:
            details = []
            if unknown:
                details.append(f"unknown={unknown}")
            if missing:
                details.append(f"missing={missing}")
            raise ValueError("unmapped runtime state sections: " + ", ".join(details))

        sections: dict[str, Mapping[str, Any]] = {}
        for key in sorted(raw):
            binding = self._bindings[key]
            sections[key] = {
                "canonical_owner": binding.canonical_owner,
                "legacy_semantics": binding.legacy_semantics,
                "legacy_state": raw[key],
                "legacy_section_digest": canonical_digest(raw[key]),
            }

        payload0 = {
            "legacy_section_count": len(raw),
            "mapped_section_count": len(sections),
            "unmapped_sections": [],
            "legacy_state_digest": canonical_digest(raw),
            "sections": {key: dict(sections[key]) for key in sorted(sections)},
        }
        return RuntimeStateEnvelope(
            legacy_section_count=len(raw),
            mapped_section_count=len(sections),
            unmapped_sections=(),
            legacy_state_digest=payload0["legacy_state_digest"],
            sections=sections,
            digest=canonical_digest(payload0),
        )
