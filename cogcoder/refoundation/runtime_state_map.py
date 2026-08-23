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
    """Total ownership map for the current OrganizationRuntime.to_state shape."""

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


@dataclass(frozen=True, slots=True)
class CanonicalStateBundle:
    """Canonical owner projection with exact legacy rollback material."""

    owners: Mapping[str, Mapping[str, Any]]
    section_owners: Mapping[str, str]
    legacy_state_digest: str
    digest: str

    @property
    def lossless(self) -> bool:
        sections = [section for payload in self.owners.values() for section in payload]
        return len(sections) == len(set(sections)) == len(self.section_owners) and set(sections) == set(self.section_owners)

    def owner_state(self, canonical_owner: str) -> Mapping[str, Any]:
        try:
            return self.owners[str(canonical_owner)]
        except KeyError as exc:
            raise KeyError(f"canonical state bundle has no owner: {canonical_owner}") from exc

    def restore_legacy_state(self) -> dict[str, Any]:
        if not self.lossless:
            raise ValueError("cannot restore a non-lossless canonical state bundle")
        restored: dict[str, Any] = {}
        for owner in sorted(self.owners):
            for legacy_section, state in self.owners[owner].items():
                if legacy_section in restored:
                    raise ValueError(f"duplicate legacy section in canonical state bundle: {legacy_section}")
                restored[legacy_section] = state
        if canonical_digest(restored) != self.legacy_state_digest:
            raise ValueError("restored legacy state digest mismatch")
        return restored

    def payload(self) -> dict[str, Any]:
        return {
            "owners": {
                owner: {section: self.owners[owner][section] for section in sorted(self.owners[owner])}
                for owner in sorted(self.owners)
            },
            "section_owners": dict(sorted(self.section_owners.items())),
            "legacy_state_digest": self.legacy_state_digest,
        }

    def __post_init__(self) -> None:
        if not self.lossless:
            raise ValueError("canonical state bundle must cover every section exactly once")
        if canonical_digest(self.payload()) != self.digest:
            raise ValueError("canonical state bundle digest mismatch")
        self.restore_legacy_state()


class RuntimeStateMapper:
    def __init__(self, bindings: tuple[RuntimeStateBinding, ...] | None = None) -> None:
        rows = bindings or build_runtime_state_bindings()
        self._bindings: dict[str, RuntimeStateBinding] = {}
        for row in rows:
            if row.legacy_section in self._bindings:
                raise ValueError(f"duplicate runtime state binding: {row.legacy_section}")
            self._bindings[row.legacy_section] = row

    def _validate_total_map(self, state: Mapping[str, Any]) -> dict[str, Any]:
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
        return raw

    def map_state(self, state: Mapping[str, Any]) -> RuntimeStateEnvelope:
        raw = self._validate_total_map(state)
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

    def bundle_state(self, state: Mapping[str, Any]) -> CanonicalStateBundle:
        raw = self._validate_total_map(state)
        owners: dict[str, dict[str, Any]] = {}
        section_owners: dict[str, str] = {}
        for section in sorted(raw):
            owner = self._bindings[section].canonical_owner
            owners.setdefault(owner, {})[section] = raw[section]
            section_owners[section] = owner
        payload = {
            "owners": {
                owner: {section: owners[owner][section] for section in sorted(owners[owner])}
                for owner in sorted(owners)
            },
            "section_owners": dict(sorted(section_owners.items())),
            "legacy_state_digest": canonical_digest(raw),
        }
        return CanonicalStateBundle(
            owners=owners,
            section_owners=section_owners,
            legacy_state_digest=payload["legacy_state_digest"],
            digest=canonical_digest(payload),
        )
