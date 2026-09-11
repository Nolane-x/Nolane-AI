from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: str, old: str, new: str, *, expected: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{path}: expected {expected} occurrences, found {count}: {old!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")


def insert_before(path: str, marker: str, addition: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if addition.strip() in text:
        raise RuntimeError(f"{path}: addition already present")
    count = text.count(marker)
    if count != 1:
        raise RuntimeError(f"{path}: expected one insertion marker, found {count}")
    target.write_text(text.replace(marker, addition + marker), encoding="utf-8")


# The receipt's provenance claim must cover the exact full request authority
# already captured by ContextCapsule, not only the historical three planning
# authorities. Preserve deterministic ordering from the capsule.
replace_exact(
    "nolane/memory/context_intelligence.py",
    "_RECEIPT_FRONTIER_NAMES = ('master-plan', 'requirements', 'architecture-graph')\n",
    "",
)
replace_exact(
    "nolane/memory/context_intelligence.py",
    """    @staticmethod\n    def _receipt_frontier_from_capsule(capsule: ContextCapsule) -> tuple[tuple[str, str], ...]:\n        return tuple(\n            (str(name), str(value))\n            for name, value in capsule.authoritative_artifacts\n            if str(name) in _RECEIPT_FRONTIER_NAMES\n        )\n""",
    """    @staticmethod\n    def _receipt_frontier_from_capsule(capsule: ContextCapsule) -> tuple[tuple[str, str], ...]:\n        return tuple((str(name), str(value)) for name, value in capsule.authoritative_artifacts)\n""",
)

# Public context typing must describe the real authority value domain: graph
# revisions are integers while scoped runtime authorities are digest strings.
replace_exact(
    "nolane/external_core/context.py",
    'COMPONENT_VERSION = "0.0.3"',
    'COMPONENT_VERSION = "0.0.4"',
)
replace_exact(
    "nolane/external_core/context.py",
    "    authoritative_artifacts: tuple[tuple[str, int], ...] = ()",
    "    authoritative_artifacts: tuple[tuple[str, int | str], ...] = ()",
)
replace_exact(
    "nolane/memory/context.py",
    'COMPONENT_VERSION = "0.0.3"',
    'COMPONENT_VERSION = "0.0.4"',
)

# Shared helper ownership discovered and enforced by repository version
# discipline: context + execution control + integration all reach the changed
# semantic helper. Advance each implementation revision exactly once.
replace_exact("nolane/metadata/component_versions.py", '        "external.integration": 11,', '        "external.integration": 12,')
replace_exact("nolane/metadata/component_versions.py", '        "external.context": 3,', '        "external.context": 4,')
replace_exact("nolane/metadata/component_versions.py", '        "external.execution.control": 18,', '        "external.execution.control": 19,')

# Canonical revision registry projections.
replace_exact("tests/test_refoundation_component_versions.py", '    "external.integration": 11,', '    "external.integration": 12,')
replace_exact("tests/test_refoundation_component_versions.py", '    "external.context": 3,', '    "external.context": 4,')
replace_exact("tests/test_refoundation_component_versions.py", '    "external.execution.control": 18,', '    "external.execution.control": 19,')
replace_exact("tests/test_refoundation_component_versions.py", 'assert str(component_version("external.context")) == "0.0.3"', 'assert str(component_version("external.context")) == "0.0.4"')
replace_exact("tests/test_refoundation_component_versions.py", 'assert str(next_component_version("external.context")) == "0.0.4"', 'assert str(next_component_version("external.context")) == "0.0.5"')
replace_exact("tests/test_refoundation_component_versions.py", 'assert str(component_version("external.integration")) == "0.0.11"', 'assert str(component_version("external.integration")) == "0.0.12"')
replace_exact("tests/test_refoundation_component_versions.py", 'assert str(next_component_version("external.integration")) == "0.0.12"', 'assert str(next_component_version("external.integration")) == "0.0.13"')
replace_exact("tests/test_refoundation_component_versions.py", 'assert str(component_version("external.execution.control")) == "0.0.18"', 'assert str(component_version("external.execution.control")) == "0.0.19"')
replace_exact("tests/test_refoundation_component_versions.py", 'assert str(next_component_version("external.execution.control")) == "0.0.19"', 'assert str(next_component_version("external.execution.control")) == "0.0.20"')

replace_exact(
    "tests/test_refoundation_memory_public_layout.py",
    '        context: ("external.context", "0.0.3"),',
    '        context: ("external.context", "0.0.4"),',
)
replace_exact("tests/test_refoundation_wave5y_native_context.py", 'assert str(component_version("external.context")) == "0.0.3"', 'assert str(component_version("external.context")) == "0.0.4"')
replace_exact("tests/test_refoundation_wave5y_native_context.py", 'assert str(next_component_version("external.context")) == "0.0.4"', 'assert str(next_component_version("external.context")) == "0.0.5"')
replace_exact("tests/test_refoundation_wave5y_native_context.py", '    assert row.component_version == "0.0.3"', '    assert row.component_version == "0.0.4"')

replace_exact("tests/test_refoundation_wave5aa_native_execution_control.py", '    assert row.component_version == "0.0.18"', '    assert row.component_version == "0.0.19"')
replace_exact("tests/test_refoundation_wave5aa_native_execution_control.py", 'assert str(component_version("external.execution.control")) == "0.0.18"', 'assert str(component_version("external.execution.control")) == "0.0.19"')

replace_exact("tests/test_refoundation_wave5p_native_integration.py", '    assert row.component_version == "0.0.11"', '    assert row.component_version == "0.0.12"')
replace_exact("tests/test_refoundation_wave5p_native_integration.py", 'assert str(component_version("external.integration")) == "0.0.11"', 'assert str(component_version("external.integration")) == "0.0.12"')
replace_exact("tests/test_external_core_scoped_revalidation_public_contract.py", 'assert str(component_version("external.integration")) == "0.0.11"', 'assert str(component_version("external.integration")) == "0.0.12"')
replace_exact("tests/test_external_core_integration_revalidation.py", 'def test_integration_surface_v008_projects_canonical_dependency_revision_v011() -> None:', 'def test_integration_surface_v008_projects_canonical_dependency_revision_v012() -> None:')
replace_exact("tests/test_external_core_integration_revalidation.py", 'assert str(component_version("external.integration")) == "0.0.11"', 'assert str(component_version("external.integration")) == "0.0.12"')
replace_exact("tests/test_external_core_a5_public_contract.py", 'def test_current_integration_owner_contract_preserves_v008_surface_at_revision_eleven() -> None:', 'def test_current_integration_owner_contract_preserves_v008_surface_at_revision_twelve() -> None:')
replace_exact("tests/test_external_core_a5_public_contract.py", 'assert component_revision_map()["external.integration"] == 11', 'assert component_revision_map()["external.integration"] == 12')
replace_exact("tests/test_external_core_a6_temporal_reattestation.py", 'assert component_revision_map()["external.integration"] == 11', 'assert component_revision_map()["external.integration"] == 12')
replace_exact("tests/test_external_core_a7_atomic_observation.py", 'assert component_revision_map()["external.integration"] == 11', 'assert component_revision_map()["external.integration"] == 12')

# A redigested receipt that merely drops a scoped/non-legacy authority must
# fail closed, proving verification binds claim scope rather than only digest
# integrity or the historical three-entry subset.
insert_before(
    "tests/test_coding_agi_context_intelligence.py",
    "\ndef test_context_verifier_rejects_redigested_receipt_with_conflicting_capsule_frontier():\n",
    """

def test_context_verifier_rejects_redigested_receipt_missing_nonlegacy_authority():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task(
        'T-CONTEXT-SCOPED-TAMPER', title='Reject incomplete scoped provenance', plan_node_id='P-CONTEXT-SCOPED-TAMPER',
    )
    runtime.tasks.lease('T-CONTEXT-SCOPED-TAMPER', 'coding.backend.01')
    result = runtime.memory_context.compile_context(
        'coding.backend.01',
        task_id='T-CONTEXT-SCOPED-TAMPER',
        budget=ContextBudget(max_memories=8, max_events=8, max_estimated_units=2048),
    )

    assert 'integration-state' in {name for name, _ in result.receipt.authoritative_frontier}
    tampered_frontier = tuple(
        (name, value) for name, value in result.receipt.authoritative_frontier
        if name != 'integration-state'
    )
    tampered = replace(result.receipt, authoritative_frontier=tampered_frontier)
    tampered = replace(tampered, digest=canonical_digest(tampered.payload()))
    runtime.memory_context.context_intelligence._receipts[tampered.receipt_id] = tampered

    with pytest.raises(ValueError, match='authority provenance'):
        runtime.memory_context.verify_context_capsule(result.capsule)

""",
)

print("NEURAL_R25_FULL_AUTHORITY_GREEN_PATCH_APPLIED")
