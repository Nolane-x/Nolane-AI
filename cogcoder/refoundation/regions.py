from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.types import AgentRank, canonical_digest

from .versioning import ComponentVersion


@dataclass(frozen=True, slots=True)
class RegionManifest:
    region_id: str
    chief_agent_id: str
    permanent_agent_ids: tuple[str, ...]
    specialist_agent_ids: tuple[str, ...]
    external_core_surface: tuple[str, ...]
    chief_direct_work_capable: bool
    all_agents_direct_work_capable: bool
    all_agents_learning_capable: bool
    region_definition_version: str = "0.0.0"
    digest: str = ""

    def __post_init__(self) -> None:
        if not self.region_id.strip() or not self.chief_agent_id.strip():
            raise ValueError("region id and chief id must be explicit")
        ComponentVersion.parse(self.region_definition_version)
        if len(set(self.permanent_agent_ids)) != len(self.permanent_agent_ids):
            raise ValueError("region contains duplicate permanent agent ids")
        if self.chief_agent_id not in self.permanent_agent_ids:
            raise ValueError("region chief must be a permanent member of the region")
        expected_specialists = set(self.permanent_agent_ids) - {self.chief_agent_id}
        if set(self.specialist_agent_ids) != expected_specialists:
            raise ValueError("region specialist ids must be exactly permanent ids minus chief")
        if not self.specialist_agent_ids:
            raise ValueError("region requires permanent specialists")
        if not self.external_core_surface:
            raise ValueError("region external-core surface must be explicit")
        if len(set(self.external_core_surface)) != len(self.external_core_surface):
            raise ValueError("region external-core surface must be unique")
        if self.digest and canonical_digest(self.payload()) != self.digest:
            raise ValueError("region manifest digest mismatch")

    def payload(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "chief_agent_id": self.chief_agent_id,
            "permanent_agent_ids": list(self.permanent_agent_ids),
            "specialist_agent_ids": list(self.specialist_agent_ids),
            "external_core_surface": list(self.external_core_surface),
            "chief_direct_work_capable": self.chief_direct_work_capable,
            "all_agents_direct_work_capable": self.all_agents_direct_work_capable,
            "all_agents_learning_capable": self.all_agents_learning_capable,
            "region_definition_version": self.region_definition_version,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}


def _finalize(row: RegionManifest) -> RegionManifest:
    return replace(row, digest=canonical_digest(row.payload()))


def build_region_manifests() -> tuple[RegionManifest, ...]:
    identities = build_first_generation_blueprint()
    grouped: dict[str, list[Any]] = {}
    for identity in identities:
        if identity.rank is AgentRank.CENTRAL:
            continue
        grouped.setdefault(identity.region, []).append(identity)

    if len(grouped) != 15:
        raise ValueError(f"expected exactly 15 non-Central regions, got {len(grouped)}")

    rows: list[RegionManifest] = []
    seen_agent_ids: set[str] = set()
    for region_id in sorted(grouped):
        members = grouped[region_id]
        chiefs = [row for row in members if row.rank is AgentRank.CHIEF]
        if len(chiefs) != 1:
            raise ValueError(f"region {region_id} must have exactly one Chief")
        chief = chiefs[0]
        specialists = [row for row in members if row.agent_id != chief.agent_id]
        if len(specialists) < 2:
            raise ValueError(f"region {region_id} must have at least two permanent specialists")

        core_surfaces = {tuple(row.external_core_bindings) for row in members}
        if len(core_surfaces) != 1:
            raise ValueError(f"region {region_id} has divergent external-core bindings")
        core_surface = next(iter(core_surfaces))

        member_ids = tuple(row.agent_id for row in sorted(members, key=lambda value: value.agent_id))
        specialist_ids = tuple(row.agent_id for row in sorted(specialists, key=lambda value: value.agent_id))
        overlap = seen_agent_ids.intersection(member_ids)
        if overlap:
            raise ValueError(f"permanent identities assigned to multiple regions: {sorted(overlap)!r}")
        seen_agent_ids.update(member_ids)

        rows.append(
            _finalize(
                RegionManifest(
                    region_id=region_id,
                    chief_agent_id=chief.agent_id,
                    permanent_agent_ids=member_ids,
                    specialist_agent_ids=specialist_ids,
                    external_core_surface=core_surface,
                    chief_direct_work_capable=bool(chief.direct_work_capable),
                    all_agents_direct_work_capable=all(row.direct_work_capable for row in members),
                    all_agents_learning_capable=all(row.learning_capable for row in members),
                )
            )
        )

    if len(seen_agent_ids) != 66:
        raise ValueError(f"region manifests must cover exactly 66 non-Central identities, got {len(seen_agent_ids)}")
    return tuple(rows)
