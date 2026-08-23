from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .canonical_runtime import CanonicalOrganization
from .capabilities import build_external_core_catalog, build_tool_catalog
from .compatibility import build_bootstrap_parity_report
from .component_versions import component_revision_map
from .composition import build_wave1_composition_lock
from .facades import build_active_facade_bindings, validate_active_facades
from .implementation_status import build_component_implementation_ledger
from .manifests import (
    FIRST_GENERATION_SNAPSHOT,
    REFUNDATION_EPOCH,
    build_bootstrap_agent_manifests,
    build_component_manifests,
)
from .regions import build_region_manifests
from .runtime_composition import build_semantic_runtime_composition
from .runtime_state_map import RuntimeStateMapper


def build_bootstrap_report() -> dict[str, object]:
    parity = build_bootstrap_parity_report()
    facade_parity = validate_active_facades()
    facades = build_active_facade_bindings()
    lock = build_wave1_composition_lock()
    agents = build_bootstrap_agent_manifests()
    regions = build_region_manifests()
    components = build_component_manifests()
    tools = build_tool_catalog()
    external_cores = build_external_core_catalog()
    implementations = build_component_implementation_ledger()
    semantic_composition = build_semantic_runtime_composition()
    runtime = CanonicalOrganization.first_generation()
    state_bundle = RuntimeStateMapper().bundle_state(runtime.to_state())

    rank_counts = Counter(row.rank for row in agents)
    implementation_counts = Counter(row.status.value for row in implementations.values())
    return {
        "refoundation_epoch": REFUNDATION_EPOCH,
        "canonical_bootstrap_version": "0.0.0",
        "source_snapshot_sha": FIRST_GENERATION_SNAPSHOT,
        "destructive_migration_enabled": False,
        "identity_summary": {
            "source": "canonical-organization-spec",
            "count": len(agents),
            "rank_counts": dict(sorted(rank_counts.items())),
            "bootstrap_parity_clean": parity.clean,
            "bootstrap_parity_digest": parity.digest,
        },
        "region_summary": {
            "count": len(regions),
            "covered_noncentral_identities": sum(len(row.permanent_agent_ids) for row in regions),
        },
        "capability_summary": {
            "base_tool_count": len(tools),
            "central_external_core_count": sum(row.scope == "central" for row in external_cores),
            "regional_external_core_binding_count": sum(row.scope == "regional" for row in external_cores),
            "external_core_binding_count": len(external_cores),
        },
        "component_summary": {
            "count": len(components),
            "revision_map": component_revision_map(),
            "implementation_status_counts": dict(sorted(implementation_counts.items())),
        },
        "semantic_runtime_composition": {
            "lossless": semantic_composition.lossless,
            "component_count": len(semantic_composition.nodes),
            "state_section_count": len(semantic_composition.section_owners),
            "unresolved_dependencies": list(semantic_composition.unresolved_dependencies()),
            "unowned_state_sections": list(semantic_composition.unowned_state_sections),
            "duplicate_state_sections": list(semantic_composition.duplicate_state_sections),
            "topological_order": list(semantic_composition.topological_order()),
            "digest": semantic_composition.digest,
        },
        "active_facade_summary": {
            "count": len(facades),
            "clean": facade_parity.clean,
            "parity_digest": facade_parity.digest,
        },
        "runtime_authority": runtime.canonical_metadata(),
        "runtime_state_migration": {
            "lossless": state_bundle.lossless,
            "legacy_state_digest": state_bundle.legacy_state_digest,
            "canonical_bundle_digest": state_bundle.digest,
            "owner_count": len(state_bundle.owners),
        },
        "agents": [row.to_state() for row in agents],
        "regions": [row.to_state() for row in regions],
        "tools": [row.__dict__ if hasattr(row, "__dict__") else {
            "tool_id": row.tool_id,
            "availability": row.availability,
            "component_version": row.component_version,
        } for row in tools],
        "external_cores": [{
            "core_id": row.core_id,
            "scope": row.scope,
            "owner_region": row.owner_region,
            "component_version": row.component_version,
        } for row in external_cores],
        "components": [row.to_state() for row in components],
        "implementation_ledger": [implementations[key].to_state() for key in sorted(implementations)],
        "active_facades": [row.to_state() for row in facades],
        "composition_lock": lock.to_state(),
        "semantic_runtime_graph": semantic_composition.to_state(),
        "bootstrap_parity": {
            **parity.payload(),
            "clean": parity.clean,
            "digest": parity.digest,
        },
        "active_facade_parity": {
            **facade_parity.payload(),
            "clean": facade_parity.clean,
            "digest": facade_parity.digest,
        },
    }


def write_bootstrap_report(output: str | Path) -> Path:
    target = Path(output)
    target.write_text(
        json.dumps(build_bootstrap_report(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Refoundation Epoch-0 architecture, manifests and parity evidence")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    target = write_bootstrap_report(args.output)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
