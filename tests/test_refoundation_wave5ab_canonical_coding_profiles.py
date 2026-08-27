from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

import pytest

from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from nolane.core.canonical_digest import canonical_digest


_PUBLIC_SYMBOLS = (
    "CodingDomain",
    "CodingProfile",
    "CodingWorkRequest",
    "CodingCandidateScore",
    "CodingAssignmentReceipt",
    "CodingProfileRegistry",
)


def test_wave5ab_canonical_coding_profiles_own_semantic_public_implementation() -> None:
    canonical = importlib.import_module("nolane.external_core.coding_profiles")
    failures: list[str] = []
    for name in _PUBLIC_SYMBOLS:
        value = getattr(canonical, name, None)
        if value is None:
            failures.append(f"missing {name}")
        elif value.__module__ != "nolane.external_core.coding_profiles":
            failures.append(f"{name} owned by {value.__module__}")
    assert failures == [], "; ".join(failures)


def test_wave5ab_historical_coding_profiles_are_exact_public_object_bridge() -> None:
    canonical = importlib.import_module("nolane.external_core.coding_profiles")
    legacy = importlib.import_module("cogcoder.organization.coding_profiles")
    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5ab_canonical_coding_profiles_have_no_reverse_historical_authority() -> None:
    root = Path(__file__).resolve().parents[1]
    source_path = root / "nolane" / "external_core" / "coding_profiles.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    offenders: list[str] = []
    has_native_identity = False
    has_native_digest = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("cogcoder.organization"):
                    offenders.append(f"{node.lineno}:import:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("cogcoder.organization"):
                offenders.append(f"{node.lineno}:from:{module}")
            if module == "nolane.organization.identity":
                has_native_identity = any(alias.name == "AgentRegistry" for alias in node.names)
            if module == "nolane.core.canonical_digest":
                has_native_digest = any(alias.name == "canonical_digest" for alias in node.names)
    assert offenders == [], "canonical coding profiles reverse-import historical authority: " + "; ".join(offenders)
    assert has_native_identity
    assert has_native_digest


def test_wave5ab_coding_profile_value_objects_preserve_validation_and_fail_closed_digest() -> None:
    profiles = importlib.import_module("nolane.external_core.coding_profiles")

    request = profiles.CodingWorkRequest(
        work_id="coding-work-5ab",
        task_id="task-5ab",
        plan_node_id="plan-node-5ab",
        requirement_refs=("REQ-5AB",),
        architecture_version=3,
        plan_version=4,
        requested_domains=(profiles.CodingDomain.BACKEND,),
        scope_hints=("backend",),
        acceptance_refs=("ACC-5AB",),
        priority=80,
        requester_agent_id="coding.chief",
        evidence_refs=("EV-5AB",),
    )
    assert profiles.CodingWorkRequest.from_state(request.to_state()) == request

    with pytest.raises(ValueError, match="priority"):
        profiles.CodingWorkRequest(
            work_id="coding-work-bad",
            task_id="task-5ab",
            plan_node_id="plan-node-5ab",
            requirement_refs=(),
            architecture_version=0,
            plan_version=0,
            requested_domains=(profiles.CodingDomain.BACKEND,),
            scope_hints=(),
            acceptance_refs=(),
            priority=101,
            requester_agent_id="coding.chief",
            evidence_refs=("EV-5AB",),
        )

    score = profiles.CodingCandidateScore("coding.backend.01", 111, ("domain:backend", "available"))
    payload = {
        "work_id": request.work_id,
        "selected_agent_id": score.agent_id,
        "ranked_candidates": [score.to_state()],
        "architecture_version": request.architecture_version,
        "plan_version": request.plan_version,
        "override_actor_id": None,
    }
    state = {**payload, "digest": canonical_digest(payload)}
    receipt = profiles.CodingAssignmentReceipt.from_state(state)
    assert receipt.to_state() == state
    corrupt = dict(state)
    corrupt["digest"] = "0" * 64
    with pytest.raises(ValueError, match="coding assignment receipt digest mismatch"):
        profiles.CodingAssignmentReceipt.from_state(corrupt)


def test_wave5ab_prerequisite_does_not_pin_later_coding_control_authority() -> None:
    ledger = build_component_implementation_ledger()
    control_status = ledger["external.coding.control"].status
    assert control_status in {
        ImplementationStatus.COMPATIBILITY_FACADE,
        ImplementationStatus.CANONICAL_NATIVE,
    }

    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {row["component_id"] for row in state["components"]}
    if control_status is ImplementationStatus.CANONICAL_NATIVE:
        assert "external.coding.control" not in ids
        assert ledger["external.coding.control"].canonical_write_authority
    else:
        assert "external.coding.control" in ids
        assert not ledger["external.coding.control"].canonical_write_authority

    # Wave 5AB established the 21-record ceiling; accepted downstream native
    # cutovers may only reduce that debt and must never force it back upward.
    assert len(state["components"]) <= 21


def test_wave5ab_current_status_tracks_canonical_coding_profile_prerequisite() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AB" in status
    lowered = status.lower()
    assert "coding" in lowered and "profile" in lowered and "canonical" in lowered
