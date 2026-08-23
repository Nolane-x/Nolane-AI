from __future__ import annotations

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.refoundation.assembly import CanonicalRuntimeAssembly


def test_canonical_assembly_wraps_exact_accepted_runtime_without_copying_it() -> None:
    runtime = OrganizationRuntime.first_generation()
    assembly = CanonicalRuntimeAssembly.from_accepted_runtime(runtime)

    assert assembly.legacy_runtime is runtime
    assert len(assembly.agent_manifests) == 67
    assert len(assembly.region_manifests) == 15
    assert assembly.state_envelope.lossless
    assert assembly.state_bundle.lossless
    assert assembly.state_bundle.restore_legacy_state() == runtime.to_state()
    assert assembly.destructive_cutover_allowed is False


def test_canonical_assembly_binds_component_graph_state_and_authority_audit() -> None:
    runtime = OrganizationRuntime.first_generation()
    assembly = CanonicalRuntimeAssembly.from_accepted_runtime(runtime)

    assert assembly.composition_lock.source_snapshot_sha == assembly.source_snapshot_sha
    assert assembly.state_envelope.legacy_state_digest
    assert assembly.state_bundle.legacy_state_digest == assembly.state_envelope.legacy_state_digest
    assert assembly.authority_reconciliation.plan_target.value == "master_plan_graph"
    assert assembly.authority_reconciliation.lease_target.value == "lease_coordinator"
    assert assembly.bootstrap_parity.clean
    assert assembly.facade_parity.clean
    assert len(assembly.digest) == 64


def test_canonical_assembly_does_not_create_more_permanent_identities() -> None:
    runtime = OrganizationRuntime.first_generation()
    assembly = CanonicalRuntimeAssembly.from_accepted_runtime(runtime)
    registry_ids = {row.agent_id for row in runtime.registry.identities()}
    manifest_ids = {row.agent_id for row in assembly.agent_manifests}
    region_ids = {agent_id for region in assembly.region_manifests for agent_id in region.permanent_agent_ids}

    assert registry_ids == manifest_ids
    assert region_ids == registry_ids - {"nolane.central"}
    assert len(registry_ids) == 67


def test_canonical_assembly_is_evidence_view_not_runtime_mutation() -> None:
    runtime = OrganizationRuntime.first_generation()
    before = runtime.to_state()
    first = CanonicalRuntimeAssembly.from_accepted_runtime(runtime)
    second = CanonicalRuntimeAssembly.from_accepted_runtime(runtime)

    assert runtime.to_state() == before
    assert first.digest == second.digest
