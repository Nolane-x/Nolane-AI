from __future__ import annotations

import inspect

import cogcoder.organization.compatibility as legacy_compatibility
import nolane.external_core.integration as native_integration
from nolane.external_core.architecture import InterfaceStability
from nolane.external_core.compatibility import (
    CompatibilityAssessment,
    CompatibilityClass,
    CompatibilityEngine,
)


def _assess(
    *,
    old_signature: str = "old",
    new_signature: str = "new",
    old_version: str = "1.0.0",
    new_version: str = "1.1.0",
    stability: InterfaceStability = InterfaceStability.INTERNAL,
    adapters: tuple[str, ...] = (),
    migrations: tuple[str, ...] = (),
) -> CompatibilityAssessment:
    return CompatibilityEngine.assess(
        old_signature_digest=old_signature,
        new_signature_digest=new_signature,
        old_semantic_version=old_version,
        new_semantic_version=new_version,
        stability=stability,
        adapter_evidence_refs=adapters,
        migration_evidence_refs=migrations,
    )


def test_legacy_compatibility_path_is_a_true_canonical_bridge() -> None:
    assert legacy_compatibility.CompatibilityClass is CompatibilityClass
    assert legacy_compatibility.CompatibilityAssessment is CompatibilityAssessment
    assert legacy_compatibility.CompatibilityEngine is CompatibilityEngine


def test_compatibility_classification_matrix_is_preserved() -> None:
    missing = _assess(old_signature="")
    assert missing.compatibility is CompatibilityClass.UNKNOWN
    assert missing.integration_safe is False
    assert missing.reason == "missing compatibility input"

    unchanged = _assess(old_signature="same", new_signature="same")
    assert unchanged.compatibility is CompatibilityClass.COMPATIBLE
    assert unchanged.integration_safe is True
    assert unchanged.reason == "interface signature unchanged"

    breaking = _assess(stability=InterfaceStability.PUBLIC)
    assert breaking.compatibility is CompatibilityClass.BREAKING
    assert breaking.integration_safe is False
    assert breaking.reason == "public signature changed without adapter or migration evidence"

    covered = _assess(
        stability=InterfaceStability.PUBLIC,
        adapters=("adapter-1", "shared"),
        migrations=("shared", "migration-1"),
    )
    assert covered.compatibility is CompatibilityClass.BACKWARD_COMPATIBLE_ONLY
    assert covered.integration_safe is True
    assert covered.reason == "changed signature covered by adapter/migration evidence"
    assert covered.evidence_refs == ("adapter-1", "shared", "migration-1")

    unknown = _assess(stability=InterfaceStability.INTERNAL)
    assert unknown.compatibility is CompatibilityClass.UNKNOWN
    assert unknown.integration_safe is False
    assert unknown.reason == "changed contract has insufficient compatibility evidence"


def test_compatibility_state_and_identity_are_deterministic() -> None:
    first = _assess(
        adapters=("adapter-1", "adapter-1"),
        migrations=("migration-1",),
    )
    second = _assess(
        adapters=("adapter-1", "adapter-1"),
        migrations=("migration-1",),
    )

    assert first == second
    assert first.assessment_id == "compat-" + first.digest[:20]
    assert first.evidence_refs == ("adapter-1", "migration-1")
    assert CompatibilityAssessment.from_state(first.to_state()) == first


def test_native_integration_has_no_legacy_compatibility_import() -> None:
    source = inspect.getsource(native_integration)
    assert "cogcoder.organization.compatibility" not in source
    assert "nolane.external_core.compatibility" in source
