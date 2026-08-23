from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .types import AIProfile, RegionManifest, SharedExternalManifest, SharedNeuralManifest


ROOT = Path(__file__).resolve().parents[2]
LOCAL_PARAMETER_BANDS: dict[str, int] = {
    "central": 40_000_000,
    "chief": 34_000_000,
    "senior_specialist": 20_000_000,
    "specialist": 8_000_000,
}


@dataclass(frozen=True, slots=True)
class CanonicalRoleSpec:
    agent_id: str
    name: str
    role: str
    senior: bool = False


@dataclass(frozen=True, slots=True)
class CanonicalRegionSpec:
    region_id: str
    chief_id: str
    chief_name: str
    chief_role: str
    external_cores: tuple[str, ...]
    specialists: tuple[CanonicalRoleSpec, ...]


def _json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing canonical AI-first source: {path.relative_to(ROOT)}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"canonical source must be a JSON object: {path.relative_to(ROOT)}")
    return value


def load_shared_neural() -> SharedNeuralManifest:
    row = _json_object(ROOT / "shared" / "neural-core" / "manifest.json")
    return SharedNeuralManifest(
        core_id=str(row["core_id"]),
        version=str(row["version"]),
        physical_parameters=int(row["physical_parameters"]),
        cognitive_capabilities=tuple(str(x) for x in row["cognitive_capabilities"]),
        scope=str(row["scope"]),
    )


def load_shared_external() -> SharedExternalManifest:
    row = _json_object(ROOT / "shared" / "external-core" / "manifest.json")
    capabilities = tuple(str(item["id"]) for item in row["capabilities"])
    kinds = {str(item["id"]): str(item["kind"]) for item in row["capabilities"]}
    return SharedExternalManifest(
        core_id=str(row["core_id"]), version=str(row["version"]), capabilities=capabilities,
        capability_kinds=kinds, scope=str(row["scope"]),
    )


def load_regions() -> tuple[RegionManifest, ...]:
    rows: list[RegionManifest] = []
    for path in (ROOT / "regions").glob("*/manifest.json"):
        row = _json_object(path)
        rows.append(RegionManifest(
            order=int(row["order"]), region_id=str(row["region_id"]), chief_id=str(row["chief_id"]),
            neural_overlay_version=str(row["neural_overlay_version"]),
            neural_overlay_physical_parameters=int(row["neural_overlay_physical_parameters"]),
            external_version=str(row["external_version"]),
            external_core_bindings=tuple(str(x) for x in row["external_core_bindings"]),
            members=tuple(str(x) for x in row["members"]),
        ))
    result = tuple(sorted(rows, key=lambda x: x.order))
    if len(result) != 15 or len({row.region_id for row in result}) != 15:
        raise ValueError("canonical AI-first source must contain exactly 15 regions")
    if tuple(row.order for row in result) != tuple(range(15)):
        raise ValueError("canonical region order must be contiguous 0..14")
    return result


def load_profiles() -> tuple[AIProfile, ...]:
    rows: list[AIProfile] = []
    for path in (ROOT / "ai").glob("*/profile.json"):
        row = _json_object(path)
        rows.append(AIProfile(
            order=int(row["order"]), agent_id=str(row["agent_id"]), name=str(row["name"]),
            region=str(row["region"]), role=str(row["role"]), rank=str(row["rank"]),
            region_chief_id=None if row.get("region_chief_id") is None else str(row["region_chief_id"]),
            local_physical_parameters=int(row["local_physical_parameters"]),
            direct_work_capable=bool(row["direct_work_capable"]), learning_capable=bool(row["learning_capable"]),
            accepted_neural_version=str(row["accepted_neural_version"]),
            private_neural_version=str(row["private_neural_version"]),
            specialization_version=str(row["specialization_version"]),
            private_external_version=str(row["private_external_version"]),
            private_external_core_bindings=tuple(str(x) for x in row.get("private_external_core_bindings", ())),
            private_tool_permissions=tuple(str(x) for x in row.get("private_tool_permissions", ())),
            memory_namespace=str(row["memory_namespace"]), skill_namespace=str(row["skill_namespace"]),
            authority_scope=tuple(str(x) for x in row["authority_scope"]),
            subscriptions=tuple(str(x) for x in row.get("subscriptions", ())), status=str(row["status"]),
            current_task=None if row.get("current_task") is None else str(row["current_task"]),
            checkpoint_id=None if row.get("checkpoint_id") is None else str(row["checkpoint_id"]),
            self_model_version=str(row["self_model_version"]),
        ))
    result = tuple(sorted(rows, key=lambda x: x.order))
    if len(result) != 67 or len({row.agent_id for row in result}) != 67:
        raise ValueError("canonical AI-first source must contain exactly 67 unique profiles")
    if tuple(row.order for row in result) != tuple(range(67)):
        raise ValueError("canonical profile order must be contiguous 0..66")
    counts: dict[str, int] = {}
    for row in result:
        counts[row.rank] = counts.get(row.rank, 0) + 1
    if counts != {"central": 1, "chief": 15, "senior_specialist": 20, "specialist": 31}:
        raise ValueError(f"canonical AI-first rank cardinality mismatch: {counts!r}")

    regions = {row.region_id: row for row in load_regions()}
    for profile in result:
        if profile.rank == "central":
            if profile.agent_id != "nolane.central" or profile.region != "global-command":
                raise ValueError("Central profile identity/region mismatch")
            continue
        try:
            region = regions[profile.region]
        except KeyError as exc:
            raise ValueError(f"profile references unknown region: {profile.agent_id}") from exc
        if profile.agent_id not in region.members or profile.region_chief_id != region.chief_id:
            raise ValueError(f"profile region membership mismatch: {profile.agent_id}")
    member_ids = [agent_id for region in regions.values() for agent_id in region.members]
    if len(member_ids) != 66 or len(set(member_ids)) != 66:
        raise ValueError("regional membership must contain exactly 66 unique non-Central identities")
    return result


def _region_specs() -> tuple[CanonicalRegionSpec, ...]:
    profiles = {row.agent_id: row for row in load_profiles()}
    result: list[CanonicalRegionSpec] = []
    for region in load_regions():
        chief = profiles[region.chief_id]
        specialists = tuple(
            CanonicalRoleSpec(
                agent_id=profiles[agent_id].agent_id,
                name=profiles[agent_id].name,
                role=profiles[agent_id].role,
                senior=profiles[agent_id].rank == "senior_specialist",
            )
            for agent_id in region.members[1:]
        )
        result.append(CanonicalRegionSpec(
            region_id=region.region_id, chief_id=chief.agent_id, chief_name=chief.name,
            chief_role=chief.role, external_cores=region.external_core_bindings, specialists=specialists,
        ))
    return tuple(result)


def build_canonical_identity_states() -> tuple[dict[str, Any], ...]:
    shared_neural = load_shared_neural()
    shared_external = load_shared_external()
    regions = {row.region_id: row for row in load_regions()}
    rows: list[dict[str, Any]] = []
    for profile in load_profiles():
        if profile.rank == "central":
            external_bindings = profile.private_external_core_bindings
            tool_permissions = shared_external.capabilities + profile.private_tool_permissions
        else:
            region = regions[profile.region]
            external_bindings = region.external_core_bindings + profile.private_external_core_bindings
            tool_permissions = shared_external.capabilities + region.external_core_bindings + profile.private_tool_permissions
        rows.append({
            "agent_id": profile.agent_id,
            "name": profile.name,
            "region": profile.region,
            "role": profile.role,
            "rank": profile.rank,
            "neural_version": profile.accepted_neural_version,
            "parameter_accounting": {
                "shared_physical_parameters": shared_neural.physical_parameters,
                "local_physical_parameters": profile.local_physical_parameters,
                "total_physical_parameters": shared_neural.physical_parameters + profile.local_physical_parameters,
            },
            "region_chief_id": profile.region_chief_id,
            "direct_work_capable": profile.direct_work_capable,
            "learning_capable": profile.learning_capable,
            "cognitive_capabilities": list(shared_neural.cognitive_capabilities),
            "memory_namespace": profile.memory_namespace,
            "skill_namespace": profile.skill_namespace,
            "external_core_bindings": list(external_bindings),
            "tool_permissions": list(tool_permissions),
            "status": profile.status,
            "current_task": profile.current_task,
            "specialization_version": profile.specialization_version,
            "authority_scope": list(profile.authority_scope),
            "subscriptions": list(profile.subscriptions),
            "checkpoint_id": profile.checkpoint_id,
            "self_model_version": profile.self_model_version,
        })
    return tuple(rows)


_SHARED_NEURAL = load_shared_neural()
_SHARED_EXTERNAL = load_shared_external()
_PROFILES = load_profiles()
SHARED_CORE_PARAMETERS = _SHARED_NEURAL.physical_parameters
UNIVERSAL_COGNITIVE_CAPABILITIES = _SHARED_NEURAL.cognitive_capabilities
GENERAL_TOOLS = _SHARED_EXTERNAL.capabilities
_CENTRAL_PROFILE = next(row for row in _PROFILES if row.rank == "central")
CENTRAL_TOOLS = GENERAL_TOOLS + _CENTRAL_PROFILE.private_tool_permissions
REGION_SPECS = _region_specs()


__all__ = (
    "CanonicalRoleSpec", "CanonicalRegionSpec", "UNIVERSAL_COGNITIVE_CAPABILITIES",
    "GENERAL_TOOLS", "CENTRAL_TOOLS", "SHARED_CORE_PARAMETERS", "LOCAL_PARAMETER_BANDS",
    "REGION_SPECS", "load_shared_neural", "load_shared_external", "load_regions", "load_profiles",
    "build_canonical_identity_states",
)
