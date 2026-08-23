from __future__ import annotations

import json

from cogcoder.refoundation.agent_manifest_export import write_agent_manifest_set
from cogcoder.refoundation.manifests import FIRST_GENERATION_SNAPSHOT, build_bootstrap_agent_manifests


def test_export_creates_exactly_67_independent_agent_manifest_files(tmp_path) -> None:
    index_path = write_agent_manifest_set(tmp_path)
    manifest_files = sorted((tmp_path / "agents").glob("*.json"))

    assert len(manifest_files) == 67
    assert index_path == tmp_path / "agents.index.json"
    assert len({path.name for path in manifest_files}) == 67


def test_exported_agent_file_names_are_stable_agent_ids(tmp_path) -> None:
    write_agent_manifest_set(tmp_path)
    expected = {f"{row.agent_id}.json" for row in build_bootstrap_agent_manifests()}
    actual = {path.name for path in (tmp_path / "agents").glob("*.json")}
    assert actual == expected


def test_each_exported_manifest_retains_orthogonal_agent_and_neural_versions(tmp_path) -> None:
    write_agent_manifest_set(tmp_path)
    for source in build_bootstrap_agent_manifests():
        state = json.loads((tmp_path / "agents" / f"{source.agent_id}.json").read_text(encoding="utf-8"))
        assert state["agent_id"] == source.agent_id
        assert state["agent_definition_version"] == "0.0.0"
        assert state["neural_version"] == source.neural_version
        assert state["parameter_accounting"] == dict(source.parameter_accounting)
        assert state["memory_namespace"] == source.memory_namespace
        assert state["skill_namespace"] == source.skill_namespace


def test_agent_index_binds_snapshot_manifest_hashes_and_cardinality(tmp_path) -> None:
    index_path = write_agent_manifest_set(tmp_path)
    index = json.loads(index_path.read_text(encoding="utf-8"))

    assert index["source_snapshot_sha"] == FIRST_GENERATION_SNAPSHOT
    assert index["permanent_identity_count"] == 67
    assert len(index["manifests"]) == 67
    assert all(len(row["digest"]) == 64 for row in index["manifests"])
    assert len(index["index_digest"]) == 64
