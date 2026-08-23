from __future__ import annotations

import inspect
import json
from pathlib import Path

from cogcoder.organization.blueprint import build_first_generation_blueprint


ROOT = Path(__file__).resolve().parents[1]
CURRENT_FILES = (
    "README.md",
    "SYSTEM_DEFINITION.md",
    "TERMINOLOGY.md",
    "ORGANIZATION.md",
    "NEURAL_CORE.md",
    "EXTERNAL_CORE.md",
    "RESEARCH_SCOPE.md",
    "STATUS.md",
)


def test_current_is_explicit_architecture_law() -> None:
    current = ROOT / "CURRENT"
    for name in CURRENT_FILES:
        path = current / name
        assert path.is_file(), name
    text = (current / "README.md").read_text(encoding="utf-8")
    assert "CURRENT/" in text
    assert "wins" in text.lower() or "authoritative" in text.lower()
    terminology = (current / "TERMINOLOGY.md").read_text(encoding="utf-8")
    assert "AI Identity" in terminology
    assert "External Core" in terminology
    assert "Tool" in terminology
    assert "AI Agent" in terminology
    assert "future" in terminology.lower()


def test_ai_first_source_cardinality_and_parameter_invariants() -> None:
    from nolane.ai.catalog import load_profiles, load_regions, load_shared_external, load_shared_neural

    profiles = load_profiles()
    regions = load_regions()
    shared_neural = load_shared_neural()
    shared_external = load_shared_external()

    assert len(profiles) == 67
    assert len({row.agent_id for row in profiles}) == 67
    assert len(regions) == 15
    assert shared_neural.physical_parameters == 56_000_000
    assert shared_external.scope == "global"

    counts: dict[str, int] = {}
    for row in profiles:
        counts[row.rank] = counts.get(row.rank, 0) + 1
        assert shared_neural.physical_parameters + row.local_physical_parameters < 100_000_000
    assert counts == {"central": 1, "chief": 15, "senior_specialist": 20, "specialist": 31}


def test_ai_first_projection_is_lossless_against_accepted_blueprint() -> None:
    from nolane.ai.catalog import build_canonical_identity_states

    expected = {row.agent_id: row.to_state() for row in build_first_generation_blueprint()}
    actual = {row["agent_id"]: row for row in build_canonical_identity_states()}
    assert actual == expected


def test_refoundation_organization_spec_is_a_bridge_into_nolane_ai() -> None:
    import cogcoder.refoundation.organization_spec as legacy_spec
    import nolane.ai.catalog as catalog

    source = inspect.getsource(legacy_spec)
    assert "from nolane.ai.catalog import" in source
    assert "CanonicalRegionSpec(" not in source
    assert legacy_spec.build_canonical_identity_states is catalog.build_canonical_identity_states
    assert legacy_spec.REGION_SPECS is catalog.REGION_SPECS


def test_nolane_ai_does_not_depend_on_refoundation_organization_spec() -> None:
    import nolane.ai.catalog as catalog
    import nolane.ai.resolver as resolver

    forbidden = "cogcoder.refoundation.organization_spec"
    assert forbidden not in inspect.getsource(catalog)
    assert forbidden not in inspect.getsource(resolver)


def test_every_ai_has_source_and_resolved_dossier_and_generated_views_are_fresh() -> None:
    from nolane.ai.catalog import load_profiles
    from nolane.ai.resolver import render_resolved_markdown, resolve_ai

    for profile in load_profiles():
        folder = ROOT / "ai" / profile.agent_id
        assert (folder / "profile.json").is_file(), profile.agent_id
        resolved_json = folder / "RESOLVED.json"
        resolved_md = folder / "RESOLVED.md"
        assert resolved_json.is_file(), profile.agent_id
        assert resolved_md.is_file(), profile.agent_id

        expected = resolve_ai(profile.agent_id).to_state()
        actual = json.loads(resolved_json.read_text(encoding="utf-8"))
        assert actual == expected, profile.agent_id
        assert resolved_md.read_text(encoding="utf-8") == render_resolved_markdown(resolve_ai(profile.agent_id))


def test_global_regional_and_individual_version_scopes_are_isolated() -> None:
    from nolane.ai.catalog import load_profiles
    from nolane.ai.resolver import resolve_all

    baseline = {row.agent_id: row for row in resolve_all()}

    global_changed = {
        row.agent_id: row
        for row in resolve_all(shared_neural_version="NUC-test-global")
    }
    assert all(global_changed[key].resolved_neural_version != baseline[key].resolved_neural_version for key in baseline)

    coding_changed = {
        row.agent_id: row
        for row in resolve_all(region_neural_versions={"core-coding": "CODING-test-regional"})
    }
    coding_ids = {row.agent_id for row in load_profiles() if row.region == "core-coding"}
    changed_ids = {
        key for key in baseline
        if coding_changed[key].resolved_neural_version != baseline[key].resolved_neural_version
    }
    assert changed_ids == coding_ids

    target = "coding.backend.01"
    private_changed = {
        row.agent_id: row
        for row in resolve_all(private_neural_versions={target: "BACKEND-test-private"})
    }
    changed_ids = {
        key for key in baseline
        if private_changed[key].resolved_neural_version != baseline[key].resolved_neural_version
    }
    assert changed_ids == {target}
