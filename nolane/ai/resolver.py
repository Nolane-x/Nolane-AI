from __future__ import annotations

from typing import Mapping

from .catalog import load_profiles, load_regions, load_shared_external, load_shared_neural
from .types import AIProfile, RegionManifest, ResolvedAI, SharedExternalManifest, SharedNeuralManifest


def _resolve(
    profile: AIProfile,
    *,
    shared_neural: SharedNeuralManifest,
    shared_external: SharedExternalManifest,
    regions: Mapping[str, RegionManifest],
    shared_neural_version: str | None,
    region_neural_versions: Mapping[str, str],
    private_neural_versions: Mapping[str, str],
) -> ResolvedAI:
    shared_version = shared_neural.version if shared_neural_version is None else str(shared_neural_version)
    private_version = private_neural_versions.get(profile.agent_id, profile.private_neural_version)
    if profile.rank == "central":
        region = None
        regional_neural_version = None
        regional_external_version = None
        regional_external = ()
        effective_external = profile.private_external_core_bindings
        tools = shared_external.capabilities + profile.private_tool_permissions
        resolved_neural_version = f"{shared_version}+{private_version}"
    else:
        region = regions[profile.region]
        regional_neural_version = region_neural_versions.get(profile.region, region.neural_overlay_version)
        regional_external_version = region.external_version
        regional_external = region.external_core_bindings
        effective_external = regional_external + profile.private_external_core_bindings
        tools = shared_external.capabilities + regional_external + profile.private_tool_permissions
        resolved_neural_version = f"{shared_version}+{regional_neural_version}+{private_version}"

    return ResolvedAI(
        agent_id=profile.agent_id, name=profile.name, role=profile.role, rank=profile.rank,
        region=profile.region, region_chief_id=profile.region_chief_id,
        accepted_neural_version=profile.accepted_neural_version,
        shared_neural_version=shared_version, regional_neural_version=regional_neural_version,
        private_neural_version=private_version, resolved_neural_version=resolved_neural_version,
        shared_external_version=shared_external.version, regional_external_version=regional_external_version,
        private_external_version=profile.private_external_version,
        shared_external_capabilities=shared_external.capabilities,
        regional_external_core_bindings=regional_external,
        private_external_core_bindings=profile.private_external_core_bindings,
        effective_external_core_bindings=effective_external, effective_tool_permissions=tools,
        parameter_accounting={
            "shared_physical_parameters": shared_neural.physical_parameters,
            "regional_physical_parameters": 0,
            "local_physical_parameters": profile.local_physical_parameters,
            "total_physical_parameters": shared_neural.physical_parameters + profile.local_physical_parameters,
        },
        memory_namespace=profile.memory_namespace, skill_namespace=profile.skill_namespace,
        authority_scope=profile.authority_scope,
    )


def resolve_ai(
    agent_id: str,
    *,
    shared_neural_version: str | None = None,
    region_neural_versions: Mapping[str, str] | None = None,
    private_neural_versions: Mapping[str, str] | None = None,
) -> ResolvedAI:
    profiles = {row.agent_id: row for row in load_profiles()}
    try:
        profile = profiles[str(agent_id)]
    except KeyError as exc:
        raise KeyError(f"unknown permanent AI identity: {agent_id}") from exc
    return _resolve(
        profile, shared_neural=load_shared_neural(), shared_external=load_shared_external(),
        regions={row.region_id: row for row in load_regions()}, shared_neural_version=shared_neural_version,
        region_neural_versions=dict(region_neural_versions or {}),
        private_neural_versions=dict(private_neural_versions or {}),
    )


def resolve_all(
    *,
    shared_neural_version: str | None = None,
    region_neural_versions: Mapping[str, str] | None = None,
    private_neural_versions: Mapping[str, str] | None = None,
) -> tuple[ResolvedAI, ...]:
    shared_neural = load_shared_neural()
    shared_external = load_shared_external()
    regions = {row.region_id: row for row in load_regions()}
    region_overrides = dict(region_neural_versions or {})
    private_overrides = dict(private_neural_versions or {})
    unknown_regions = set(region_overrides) - set(regions)
    unknown_agents = set(private_overrides) - {row.agent_id for row in load_profiles()}
    if unknown_regions:
        raise KeyError(f"unknown regional Neural override(s): {sorted(unknown_regions)!r}")
    if unknown_agents:
        raise KeyError(f"unknown private Neural override(s): {sorted(unknown_agents)!r}")
    return tuple(
        _resolve(
            profile, shared_neural=shared_neural, shared_external=shared_external, regions=regions,
            shared_neural_version=shared_neural_version, region_neural_versions=region_overrides,
            private_neural_versions=private_overrides,
        )
        for profile in load_profiles()
    )


def render_resolved_markdown(row: ResolvedAI) -> str:
    regional_neural = row.regional_neural_version or "none (Central)"
    regional_external = row.regional_external_version or "none (Central)"
    bindings = ", ".join(row.effective_external_core_bindings) or "none"
    tools = ", ".join(row.effective_tool_permissions) or "none"
    return (
        f"# {row.name}\n\n"
        f"- AI ID: `{row.agent_id}`\n"
        f"- Role: {row.role}\n"
        f"- Rank: `{row.rank}`\n"
        f"- Region: `{row.region}`\n"
        f"- Regional Chief: `{row.region_chief_id}`\n\n"
        "## Neural Core\n\n"
        f"- Shared: `{row.shared_neural_version}`\n"
        f"- Regional: `{regional_neural}`\n"
        f"- Private: `{row.private_neural_version}`\n"
        f"- Resolved composition: `{row.resolved_neural_version}`\n"
        f"- Accepted runtime neural version: `{row.accepted_neural_version}`\n"
        f"- Physical parameters: shared {row.parameter_accounting['shared_physical_parameters']:,} + "
        f"local {row.parameter_accounting['local_physical_parameters']:,} = "
        f"{row.parameter_accounting['total_physical_parameters']:,}\n\n"
        "## External Core\n\n"
        f"- Shared version: `{row.shared_external_version}`\n"
        f"- Regional version: `{regional_external}`\n"
        f"- Private version: `{row.private_external_version}`\n"
        f"- Effective External Core bindings: {bindings}\n"
        f"- Effective tool permissions: {tools}\n\n"
        "## Personal State Namespaces\n\n"
        f"- Memory: `{row.memory_namespace}`\n"
        f"- Skills: `{row.skill_namespace}`\n"
        f"- Authority scope: {', '.join(row.authority_scope)}\n\n"
        "> GENERATED VIEW — edit canonical shared/region/profile source, never this file.\n"
    )


__all__ = ("resolve_ai", "resolve_all", "render_resolved_markdown")
