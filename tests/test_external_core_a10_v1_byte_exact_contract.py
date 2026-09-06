from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import nolane.external_core.audit as external_audit
import nolane.external_core.compatibility as compatibility
import nolane.external_core.integration as integration
import nolane.external_core.integration_admission as admission_protocol
import nolane.external_core.integration_admission_bundle as admission_bundle
import nolane.external_core.observation as observation
import nolane.external_core.observation_integration as observation_integration


ROOT = Path(__file__).resolve().parents[1]


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def _string_literals(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def test_frozen_admission_protocol_owner_is_byte_exact() -> None:
    path = ROOT / "nolane" / "external_core" / "integration_admission.py"
    assert _git_blob_sha(path) == "2c18472c972d68a05a8c3f1127b61b6b8078feec"
    assert admission_protocol.COMPONENT_ID == "external.integration"
    assert admission_protocol.COMPONENT_VERSION == "0.0.4"
    assert admission_protocol.ADMISSION_PROTOCOL == "external-integration-admission-v2"


def test_current_external_core_v1_literal_identity_matrix_is_exact() -> None:
    assert integration.COMPONENT_ID == "external.integration"
    assert integration.COMPONENT_VERSION == "0.0.7"
    assert compatibility.SEMANTIC_SURFACE_ID == "external.integration.compatibility"
    assert compatibility.SEMANTIC_SURFACE_VERSION == "0.0.7"

    assert admission_bundle.COMPONENT_ID == "external.integration"
    assert admission_bundle.COMPONENT_VERSION == "0.0.7"
    assert admission_bundle.ADMISSION_BUNDLE_PROTOCOL == "external-integration-admission-bundle-v2"
    assert admission_bundle.HISTORICAL_ADMISSION_AUDIT_PROTOCOL == "external-integration-admission-audit-v3"
    assert admission_bundle.ADMISSION_AUDIT_PROTOCOL == "external-integration-admission-audit-v4"
    assert admission_bundle.CURRENT_ADMISSION_AUDIT_PROTOCOL == admission_bundle.ADMISSION_AUDIT_PROTOCOL

    assert observation.OBSERVATION_SURFACE_PROTOCOL == "external-canonical-observation-surface-v1"
    assert observation.SURFACE_RECEIPT_PROTOCOL == "external-surface-observation-receipt-v1"
    assert observation.OBSERVATION_PROTOCOL == "external-canonical-observation-v1"
    assert observation_integration.CANONICAL_OBSERVATION_CHAIN_ID == "external-core:canonical-observation"
    assert observation_integration.CANONICAL_OBSERVER_PROVIDER_VERSION == "1"


def test_required_observation_surface_vocabulary_is_exact_and_closed() -> None:
    assert observation.REQUIRED_SURFACE_KINDS == (
        "artifact",
        "authority-graph",
        "evidence",
        "freshness",
        "handoff",
        "registry",
        "source-state",
        "work-trace",
    )
    assert len(set(observation.REQUIRED_SURFACE_KINDS)) == 8


def test_observation_public_export_surface_is_exact() -> None:
    assert observation.__all__ == (
        "CanonicalObservationEnvelope",
        "CanonicalObservationSurfaceContract",
        "CanonicalSurfaceProviderExpectation",
        "OBSERVATION_PROTOCOL",
        "OBSERVATION_SURFACE_PROTOCOL",
        "ObservationFinding",
        "REQUIRED_SURFACE_KINDS",
        "SURFACE_RECEIPT_PROTOCOL",
        "SurfaceObservationReceipt",
        "detect_observation_forks",
        "validate_observation_completeness",
        "validate_observation_provenance",
        "validate_observation_transition",
    )


def test_observation_finding_code_lexicon_is_exact() -> None:
    literals = _string_literals(ROOT / "nolane" / "external_core" / "observation.py")
    non_finding_observation_constants = {
        "OBSERVATION_PROTOCOL",
        "OBSERVATION_SURFACE_PROTOCOL",
    }
    codes = {
        value
        for value in literals
        if value.startswith("OBSERVATION_")
        and value not in non_finding_observation_constants
    }
    assert codes == {
        "OBSERVATION_CHAIN_ID_MISMATCH",
        "OBSERVATION_ENUMERATION_INCOMPLETE",
        "OBSERVATION_EPOCH_NOT_MONOTONIC",
        "OBSERVATION_FORK_DETECTED",
        "OBSERVATION_GENESIS_CONTEXT_INVALID",
        "OBSERVATION_PREDECESSOR_DIGEST_MISMATCH",
        "OBSERVATION_PREDECESSOR_UNAVAILABLE",
        "OBSERVATION_PROVENANCE_CONTENT_MISMATCH",
        "OBSERVATION_PROVENANCE_EPOCH_MISMATCH",
        "OBSERVATION_PROVENANCE_SCOPE_MISMATCH",
        "OBSERVATION_PROVIDER_ID_MISMATCH",
        "OBSERVATION_PROVIDER_VERSION_MISMATCH",
        "OBSERVATION_RECEIPT_FORGED",
        "OBSERVATION_REQUIRED_COMPONENT_MISSING",
        "OBSERVATION_REQUIRED_SURFACE_MISSING",
        "OBSERVATION_SOURCE_LOCATOR_MISMATCH",
        "OBSERVATION_SURFACE_DUPLICATE",
        "OBSERVATION_SURFACE_EPOCH_MISMATCH",
        "OBSERVATION_SURFACE_SCOPE_MISMATCH",
        "OBSERVATION_SURFACE_STATE_DIGEST_MISMATCH",
        "OBSERVATION_SURFACE_UNEXPECTED",
        "OBSERVATION_UNEXPECTED_COMPONENT",
    }

    population_literals = _string_literals(ROOT / "nolane" / "external_core" / "observation_population.py")
    population_codes = {value for value in population_literals if value.startswith("OBSERVATION_")}
    assert population_codes == {
        "OBSERVATION_REQUIRED_COMPONENT_UNOBSERVED",
        "OBSERVATION_UNEXPECTED_COMPONENT_OBSERVED",
    }


def test_observation_layer_is_pure_and_owns_no_mutable_chain_head() -> None:
    paths = (
        ROOT / "nolane" / "external_core" / "observation.py",
        ROOT / "nolane" / "external_core" / "observation_integration.py",
        ROOT / "nolane" / "external_core" / "observation_population.py",
    )
    banned_import_roots = {
        "asyncio",
        "datetime",
        "http",
        "multiprocessing",
        "os",
        "pathlib",
        "random",
        "requests",
        "secrets",
        "socket",
        "subprocess",
        "threading",
        "time",
        "urllib",
    }
    banned_calls = {"eval", "exec", "open"}
    banned_state_tokens = ("CHAIN_HEAD", "GLOBAL_HISTORY", "LATEST_OBSERVATION", "CURRENT_HEAD")

    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        import_roots: set[str] = set()
        assigned_names: set[str] = set()
        called_names: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                import_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    import_roots.add(node.module.split(".", 1)[0])
            elif isinstance(node, (ast.Global, ast.Nonlocal)):
                raise AssertionError(f"{path.name} contains mutable scope declaration: {ast.dump(node)}")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                called_names.add(node.func.id)

        for node in tree.body:
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets.extend(node.targets)
            elif isinstance(node, ast.AnnAssign):
                targets.append(node.target)
            for target in targets:
                if isinstance(target, ast.Name):
                    assigned_names.add(target.id)

        assert not (import_roots & banned_import_roots), (
            path.name,
            sorted(import_roots & banned_import_roots),
        )
        assert not (called_names & banned_calls), (path.name, sorted(called_names & banned_calls))
        assert not any(token in name for name in assigned_names for token in banned_state_tokens), (
            path.name,
            sorted(assigned_names),
        )


def test_canonical_registry_population_matches_independent_adapter_sources_and_profile() -> None:
    specs = external_audit._canonical_adapter_specs()
    registry = external_audit.build_canonical_registry()
    profile = external_audit.build_canonical_fabric_profile()

    source_ids = tuple(sorted(spec.source.COMPONENT_ID for spec in specs))
    registry_ids = tuple(sorted(row.component_id for row in registry.manifests))
    profile_ids = tuple(sorted(row.component_id for row in profile.manifests))

    assert len(specs) == 10
    assert len(source_ids) == len(set(source_ids)) == 10
    assert source_ids == registry_ids == profile_ids
    assert profile.manifests == registry.manifests


def test_provider_expectation_vocabulary_is_exact_for_every_surface() -> None:
    expectations = observation_integration.canonical_observation_provider_expectations()
    assert tuple(sorted(expectations)) == tuple(sorted(observation.REQUIRED_SURFACE_KINDS))

    registry = expectations["registry"]
    assert registry.surface_kind == "registry"
    assert registry.provider_id == "external-core:canonical-registry"
    assert registry.provider_version == "1"
    assert registry.source_locator == "nolane.external_core.audit:build_canonical_registry"

    graph = expectations["authority-graph"]
    assert graph.surface_kind == "authority-graph"
    assert graph.provider_id == "external-core:canonical-authority-graph"
    assert graph.provider_version == "1"
    assert graph.source_locator == "nolane.external_core.audit:build_canonical_fabric_profile"

    for kind in (
        "artifact",
        "evidence",
        "freshness",
        "handoff",
        "source-state",
        "work-trace",
    ):
        row = expectations[kind]
        assert row.surface_kind == kind
        assert row.provider_id == f"external-core:canonical-observer:{kind}"
        assert row.provider_version == "1"
        assert row.source_locator == f"nolane.external_core.observation_integration:{kind}"
