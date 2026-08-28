from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from nolane.evaluation.regimes import EvaluationMode


_MODULE_OBJECTS = {
    "campaign": (
        "CampaignStatus",
        "EvaluationCampaign",
        "EvaluationCampaignControlPlane",
    ),
    "campaign_repository": (
        "RepositorySnapshot",
        "RepositorySnapshotRegistry",
    ),
    "campaign_tasks": (
        "CampaignPartition",
        "CampaignTaskManifest",
        "CampaignTaskRegistry",
    ),
    "campaign_contamination": (
        "ContaminationKind",
        "ContaminationFinding",
        "CampaignContaminationLedger",
    ),
    "campaign_runner": (
        "CampaignRunSpec",
        "CampaignRunReceipt",
        "CampaignRunLedger",
    ),
    "campaign_reproduction": (
        "CampaignReproductionPackage",
        "CampaignReproductionReceipt",
        "CampaignReproductionLedger",
    ),
    "campaign_ingest": (
        "CampaignIngestReceipt",
        "CampaignIngestor",
    ),
}


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_wave5am_canonical_campaign_cluster_owns_all_public_authority() -> None:
    root = _root()
    canonical = importlib.import_module("nolane.evaluation.campaign")
    assert canonical.COMPONENT_ID == "evaluation.campaign"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.campaign"

    for suffix, names in _MODULE_OBJECTS.items():
        path = root / "nolane" / "evaluation" / f"{suffix}.py"
        assert path.exists(), f"missing canonical campaign module: {suffix}"
        module = importlib.import_module(f"nolane.evaluation.{suffix}")
        for name in names:
            assert getattr(module, name).__module__ == f"nolane.evaluation.{suffix}"


def test_wave5am_historical_campaign_cluster_is_exact_identity_bridge() -> None:
    for suffix, names in _MODULE_OBJECTS.items():
        canonical = importlib.import_module(f"nolane.evaluation.{suffix}")
        legacy = importlib.import_module(f"cogcoder.organization.{suffix}")
        for name in names:
            assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5am_canonical_campaign_cluster_has_no_reverse_legacy_imports() -> None:
    root = _root()
    for suffix in _MODULE_OBJECTS:
        path = root / "nolane" / "evaluation" / f"{suffix}.py"
        assert path.exists(), f"missing canonical campaign module: {suffix}"
        imports = _imports(path)
        assert not any(module.startswith("cogcoder.organization") for module in imports)

    campaign_imports = _imports(root / "nolane" / "evaluation" / "campaign.py")
    assert "nolane.evaluation.campaign_repository" in campaign_imports
    assert "nolane.evaluation.campaign_tasks" in campaign_imports
    assert "nolane.evaluation.regimes" in campaign_imports
    assert "nolane.core.canonical_digest" in campaign_imports


def test_wave5am_campaign_state_roundtrip_semantics_remain_stable() -> None:
    canonical = importlib.import_module("nolane.evaluation.campaign")
    row = canonical.EvaluationCampaign(
        campaign_id="wave5am-roundtrip",
        benchmark_id="heldout-campaign-benchmark",
        task_ids=("task-alpha", "task-beta"),
        modes=(EvaluationMode.SINGLE_AGENT, EvaluationMode.ORGANIZATION),
        freshness_epoch=7,
        runner_protocol_version="runner-v1",
        status=canonical.CampaignStatus.DRAFT,
    )
    state = row.to_state()
    restored = canonical.EvaluationCampaign.from_state(state)
    assert restored == row
    assert restored.to_state() == state


def test_wave5am_campaign_authority_version_facade_and_debt_cutover() -> None:
    row = build_component_implementation_ledger()["evaluation.campaign"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.evaluation.campaign"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("evaluation.campaign")) == "0.0.1"
    assert all(binding.component_id != "evaluation.campaign" for binding in build_active_facade_bindings())

    state = json.loads((_root() / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in state["components"]}
    assert "evaluation.campaign" not in ids
    assert len(state["components"]) <= 10


def test_wave5am_current_status_tracks_native_campaign_cutover() -> None:
    status = (_root() / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AM" in status
    assert "evaluation.campaign" in status
    assert "10 non-native" in status


def test_wave5am_temporary_authority_carrier_is_absent_from_accepted_tree() -> None:
    root = _root()
    assert not (root / ".github" / "workflows" / "refoundation-wave5am-authority-carrier.yml").exists()
    assert not (root / "docs" / "superpowers" / "plans" / ".wave5am-carrier-trigger").exists()
