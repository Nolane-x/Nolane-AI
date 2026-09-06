from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one replacement target, found {count}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_count(path: str, old: str, new: str, expected_count: int) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected_count:
        raise RuntimeError(f"{path}: expected {expected_count} targets, found {count}: {old[:100]!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")


# Current Integration hardening revision only. Frozen admission-v2 remains untouched.
replace_once(
    "nolane/external_core/integration.py",
    'COMPONENT_VERSION = "0.0.7"',
    'COMPONENT_VERSION = "0.0.8"',
)
replace_once(
    "nolane/external_core/compatibility.py",
    'SEMANTIC_SURFACE_VERSION = "0.0.7"',
    'SEMANTIC_SURFACE_VERSION = "0.0.8"',
)
replace_once(
    "nolane/external_core/integration_admission_bundle.py",
    'COMPONENT_VERSION = "0.0.7"',
    'COMPONENT_VERSION = "0.0.8"',
)
replace_once(
    "nolane/metadata/component_versions.py",
    '"external.integration": 7,',
    '"external.integration": 8,',
)

# A8: current observation must distinguish unavailable from explicitly empty.
replace_once(
    "nolane/external_core/integration_admission_bundle.py",
    '''def _frontier(value: Mapping[str, str] | None) -> Mapping[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("frontier must be an object")
    return dict(value.items())
''',
    '''def _frontier(value: Mapping[str, str] | None) -> Mapping[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("frontier must be an object")
    return dict(value.items())


def _current_observation_frontier(
    value: Mapping[str, str] | None,
    label: str,
) -> Mapping[str, str]:
    if value is None:
        raise ValueError(f"current observation {label} surface unavailable")
    return _frontier(value)
''',
)
replace_once(
    "nolane/external_core/integration_admission_bundle.py",
    '''    source = _frontier(current_source_state_digests)
    evidence = _frontier(current_evidence_digests)
    artifact = _frontier(current_artifact_digests)
    freshness = _frontier(current_freshness_fences)
    handoffs = _frontier(known_handoff_digests)
    traces = _frontier(current_work_trace_digests)
    registry, profile = _strict_current_objects()
    return build_observation_from_snapshot(
''',
    '''    source = _current_observation_frontier(current_source_state_digests, "source-state")
    evidence = _current_observation_frontier(current_evidence_digests, "evidence")
    artifact = _current_observation_frontier(current_artifact_digests, "artifact")
    freshness = _current_observation_frontier(current_freshness_fences, "freshness")
    handoffs = _current_observation_frontier(known_handoff_digests, "handoff")
    traces = _current_observation_frontier(current_work_trace_digests, "work-trace")
    registry, profile = _strict_current_objects()
    return build_observation_from_snapshot(
''',
)

# A9: a forged nested receipt is a categorical provenance finding. Preserve
# the prior fail-closed exception for unrelated envelope-integrity failures.
replace_once(
    "nolane/external_core/observation.py",
    '''    envelope.validate_integrity()
    committed_digests = _surface_digest_map(envelope)
    findings: list[ObservationFinding] = []

    for kind in REQUIRED_SURFACE_KINDS:
''',
    '''    envelope_integrity_error: Exception | None = None
    try:
        envelope.validate_integrity()
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        envelope_integrity_error = exc

    committed_digests = _surface_digest_map(envelope)
    findings: list[ObservationFinding] = []

    for kind in REQUIRED_SURFACE_KINDS:
''',
)
replace_once(
    "nolane/external_core/observation.py",
    '''                )

    return tuple(sorted(findings, key=lambda row: (row.code, row.subject_id, row.detail)))


def validate_observation_transition(
''',
    '''                )

    if envelope_integrity_error is not None and not any(
        row.code == "OBSERVATION_RECEIPT_FORGED" for row in findings
    ):
        raise envelope_integrity_error

    return tuple(sorted(findings, key=lambda row: (row.code, row.subject_id, row.detail)))


def validate_observation_transition(
''',
)

# A10: a clean v4 report cannot exist without an exact observation witness.
replace_once(
    "nolane/external_core/integration_admission_bundle.py",
    '''        rows = tuple(sorted(findings, key=lambda row: (row.code, row.subject_id, row.detail)))
        protocol = ADMISSION_AUDIT_PROTOCOL if current_observation else HISTORICAL_ADMISSION_AUDIT_PROTOCOL
''',
    '''        rows = tuple(sorted(findings, key=lambda row: (row.code, row.subject_id, row.detail)))
        if current_observation:
            if observation_digest is not None and (
                type(observation_digest) is not str or not observation_digest.strip()
            ):
                raise ValueError("current observation audit observation digest must be an exact non-empty string")
            if not rows and observation_digest is None:
                raise ValueError("clean current observation audit requires an exact observation digest")
        protocol = ADMISSION_AUDIT_PROTOCOL if current_observation else HISTORICAL_ADMISSION_AUDIT_PROTOCOL
''',
)

# Remove the incidental deduplication introduced during the A8/A9 fix; findings
# retain the original deterministic multiset semantics unless a separate RED
# proves deduplication is required.
replace_once(
    "nolane/external_core/observation_integration.py",
    'return tuple(sorted(set(findings), key=lambda row: (row.code, row.subject_id, row.detail)))',
    'return tuple(sorted(findings, key=lambda row: (row.code, row.subject_id, row.detail)))',
)

# Current projections move once with the semantic hardening revision.
replace_once(
    "tests/test_refoundation_component_versions.py",
    '"external.integration": 7,',
    '"external.integration": 8,',
)
replace_once(
    "tests/test_refoundation_component_versions.py",
    'assert str(component_version("external.integration")) == "0.0.7"\n    assert str(next_component_version("external.integration")) == "0.0.8"',
    'assert str(component_version("external.integration")) == "0.0.8"\n    assert str(next_component_version("external.integration")) == "0.0.9"',
)
replace_count(
    "tests/test_refoundation_wave5p_native_integration.py",
    '"0.0.7"',
    '"0.0.8"',
    3,
)
replace_count(
    "tests/test_external_core_a10_v1_byte_exact_contract.py",
    '"0.0.7"',
    '"0.0.8"',
    3,
)
replace_once(
    "tests/test_external_core_a10_observation_audit.py",
    'assert admission_bundle.COMPONENT_VERSION == "0.0.7"',
    'assert admission_bundle.COMPONENT_VERSION == "0.0.8"',
)
replace_once(
    "tests/test_external_core_a10_v1_document_contract.py",
    'The current `external.integration` owner, compatibility semantic surface and admission-audit owner projection are `0.0.7`; metadata revision is `7`',
    'The current `external.integration` owner, compatibility semantic surface and admission-audit owner projection are `0.0.8`; metadata revision is `8`',
)
replace_once(
    "tests/test_external_core_a10_v1_document_contract.py",
    'assert admission_bundle.COMPONENT_VERSION == "0.0.7"',
    'assert admission_bundle.COMPONENT_VERSION == "0.0.8"',
)

# Older A4-A7 and integration/revalidation tests project the current owner and
# must move with the same revision; frozen admission-v2 assertions stay 0.0.4.
replace_count(
    "tests/test_external_core_integration_evolution_public_contract.py",
    '"0.0.7"',
    '"0.0.8"',
    2,
)
replace_once(
    "tests/test_external_core_integration_revalidation.py",
    "test_integration_component_current_version_is_v007",
    "test_integration_component_current_version_is_v008",
)
replace_count(
    "tests/test_external_core_integration_revalidation.py",
    '"0.0.7"',
    '"0.0.8"',
    2,
)
replace_count(
    "tests/test_external_core_scoped_revalidation_public_contract.py",
    '"0.0.7"',
    '"0.0.8"',
    3,
)
replace_once(
    "tests/test_external_core_a5_public_contract.py",
    "test_current_integration_owner_contract_projects_final_a10_revision_seven",
    "test_current_integration_owner_contract_projects_v1_hardening_revision_eight",
)
replace_once(
    "tests/test_external_core_a5_public_contract.py",
    'assert integration.COMPONENT_VERSION == "0.0.7"',
    'assert integration.COMPONENT_VERSION == "0.0.8"',
)
replace_once(
    "tests/test_external_core_a5_public_contract.py",
    'assert component_revision_map()["external.integration"] == 7',
    'assert component_revision_map()["external.integration"] == 8',
)
replace_once(
    "tests/test_external_core_a6_temporal_reattestation.py",
    "test_a6_temporal_contract_survives_a10_current_lane_advance_without_rewriting_a5_admission_artifacts",
    "test_a6_temporal_contract_survives_v1_hardening_without_rewriting_a5_admission_artifacts",
)
replace_count(
    "tests/test_external_core_a6_temporal_reattestation.py",
    '"0.0.7"',
    '"0.0.8"',
    3,
)
replace_once(
    "tests/test_external_core_a6_temporal_reattestation.py",
    'assert component_revision_map()["external.integration"] == 7',
    'assert component_revision_map()["external.integration"] == 8',
)
replace_once(
    "tests/test_external_core_a7_atomic_observation.py",
    "test_a7_atomic_contract_survives_a10_current_lane_advance",
    "test_a7_atomic_contract_survives_v1_hardening",
)
replace_count(
    "tests/test_external_core_a7_atomic_observation.py",
    '"0.0.7"',
    '"0.0.8"',
    3,
)
replace_once(
    "tests/test_external_core_a7_atomic_observation.py",
    'assert component_revision_map()["external.integration"] == 7',
    'assert component_revision_map()["external.integration"] == 8',
)

# Seal the already-verified A10 production architecture fact, then describe this
# bounded v1 hardening as a conformance revision rather than a new architecture.
replace_once(
    "CURRENT/EXTERNAL_CORE.md",
    '''The current `external.integration` owner, compatibility semantic surface and admission-audit owner projection are `0.0.7`; metadata revision is `7`. There is still no global External Core version. A clean v4 audit remains structural-currentness evidence only and cannot mint Truth, Verification, Assurance, authorization, promotion, execution, learning, repair, migration, release or deployment authority.

This A10 section is the repository architecture seal for the External Core v1 design boundary. The **production freeze declaration is withheld until Task 10 verifies the exact merge and post-merge production head**; until then this text describes the intended sealed architecture, not evidence that production merge acceptance has already occurred.''',
    '''The current `external.integration` owner, compatibility semantic surface and admission-audit owner projection are `0.0.8`; metadata revision is `8`. There is still no global External Core version. A clean v4 audit remains structural-currentness evidence only and cannot mint Truth, Verification, Assurance, authorization, promotion, execution, learning, repair, migration, release or deployment authority.

The A10 architecture production freeze was verified on `main@99de2ff334d5a0cafa25e4f76f02e974fa391f0f`. The subsequent `0.0.8` / revision-8 change is a bounded External Core v1 hardening revision discovered by destructive post-freeze audit: expected adapter population is now independent of the observed registry/profile population; registry and authority-graph receipts use their exact sealed provider identities and source locators; unavailable current frontiers cannot be laundered into observed-empty frontiers; forged nested receipts can reach their categorical provenance finding; and a clean v4 report requires an exact observation digest. None of these corrections adds an A11 architecture generation, new capability family, governor, invoker, runtime registration path or mutable chain head.

The frozen `external-integration-admission-v2` issuer remains at component version `0.0.4`; `external-integration-admission-bundle-v2`, `external-canonical-observation-v1`, historical audit-v3 evidence and current audit-v4 identities remain unchanged.''',
)

print("External Core v1 hardening patch applied with all exact replacement guards satisfied")
