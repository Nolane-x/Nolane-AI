from __future__ import annotations

from cogcoder.organization.runtime import OrganizationRuntime as LegacyOrganizationRuntime
from cogcoder.refoundation.identity_source import build_manifest_driven_runtime
from nolane.organization.runtime import OrganizationRuntime, build_first_generation_runtime


def test_legacy_runtime_class_identity_remains_compatible() -> None:
    assert OrganizationRuntime is LegacyOrganizationRuntime


def test_public_nolane_runtime_factory_is_manifest_driven_and_authority_wrapped() -> None:
    public = build_first_generation_runtime()
    direct = build_manifest_driven_runtime()
    legacy = LegacyOrganizationRuntime.first_generation()

    assert public.to_state() == direct.to_state()
    assert public.to_state() == legacy.to_state()
    assert len(public.identities()) == 67
    assert public.identity_source == "canonical-manifests"
    assert not hasattr(public, "tasks")
    assert not hasattr(public, "planning")
