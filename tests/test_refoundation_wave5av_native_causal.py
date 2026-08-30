from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.implementation_status import ImplementationStatus, build_component_implementation_ledger
from nolane.external_core.evidence import EvidenceRecord


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


def _deadzone(context):
    x = float(context["x"])
    low = float(context["low"])
    high = float(context["high"])
    if low > high:
        raise ValueError("low must be <= high")
    if x < low:
        return x - low
    if x > high:
        return x - high
    return 0.0


def _valid_deadzone(context):
    return float(context["low"]) <= float(context["high"])


def _contexts():
    rows = []
    for low, high in ((-3.0, 2.0), (-1.0, 4.0), (-4.0, 1.0), (-5.0, 5.0)):
        for x in (-7.0, -4.0, -2.0, 0.0, 3.0, 6.0, 8.0):
            rows.append({"x": x, "low": low, "high": high})
    return tuple(rows)


def test_wave5av_native_causal_public_boundary_and_metadata() -> None:
    module = importlib.import_module("nolane.external_core.causal")
    assert module.COMPONENT_ID == "external.causal"
    assert module.COMPONENT_VERSION == "0.0.2"
    assert module.MIGRATED_FROM == "cogcoder R2.58/R2.62 bounded causal-program lineage"
    for name in (
        "PositionalSchema",
        "InterventionSpec",
        "enumerate_interventions",
        "ComplementaryExperimentProgram",
        "ComplementaryStructureReceipt",
        "discover_complementary_experiment_structure",
        "CausalProgramLedger",
    ):
        assert hasattr(module, name), name


def test_wave5av_native_causal_has_no_reverse_historical_imports() -> None:
    imports = _imports(_root() / "nolane" / "external_core" / "causal.py")
    assert not any(name.startswith("cogcoder.r") for name in imports)
    assert not any(name.startswith("cogcoder.organization") for name in imports)


def test_wave5av_structure_discovery_matches_r262_historical_oracle() -> None:
    native = importlib.import_module("nolane.external_core.causal")
    legacy = importlib.import_module("cogcoder.r262_complementary_experiment_program")
    rows = _contexts()
    native_receipt = native.discover_complementary_experiment_structure(
        _deadzone,
        ("x", "low", "high"),
        (-10.0, 10.0),
        rows[:18],
        rows[18:],
        context_validator=_valid_deadzone,
        intervention_arity=1,
    )
    legacy_receipt = legacy.discover_complementary_experiment_structure(
        _deadzone,
        ("x", "low", "high"),
        (-10.0, 10.0),
        rows[:18],
        rows[18:],
        context_validator=_valid_deadzone,
        intervention_arity=1,
    )
    assert native_receipt.passed and legacy_receipt.passed
    assert native_receipt.selected is not None and legacy_receipt.selected is not None
    assert native_receipt.selected.program.program_id == legacy_receipt.selected.program.program_id
    assert native_receipt.selected.program.composition_op == legacy_receipt.selected.program.composition_op == "add"
    assert tuple(spec.bindings for spec in native_receipt.selected.program.interventions) == tuple(
        spec.bindings for spec in legacy_receipt.selected.program.interventions
    )
    assert native_receipt.passing_programs == legacy_receipt.passing_programs == 1
    assert native_receipt.invalid_interventions_rejected == legacy_receipt.invalid_interventions_rejected
    assert native_receipt.degenerate_interventions_rejected == legacy_receipt.degenerate_interventions_rejected
    assert native_receipt.trainable_parameter_count == 0


def test_wave5av_interventions_are_identity_stable_and_fail_closed() -> None:
    native = importlib.import_module("nolane.external_core.causal")
    first = native.InterventionSpec(((1, -10.0),))
    second = native.InterventionSpec(((1, -10),))
    assert first == second
    assert first.intervention_id == second.intervention_id
    assert first.bind(("x", "low", "high")) == (("low", -10.0),)
    assert first.apply({"x": 1.0, "low": -1.0, "high": 2.0}, ("x", "low", "high"))["low"] == -10.0
    with pytest.raises(ValueError):
        native.InterventionSpec(((0, 1.0), (0, 2.0)))
    with pytest.raises(ValueError):
        native.InterventionSpec(((-1, 1.0),))
    with pytest.raises(ValueError):
        native.InterventionSpec(((0, float("inf")),))


def test_wave5av_causal_ledger_binds_programs_to_passing_evidence_and_roundtrips() -> None:
    native = importlib.import_module("nolane.external_core.causal")
    rows = _contexts()
    receipt = native.discover_complementary_experiment_structure(
        _deadzone,
        ("x", "low", "high"),
        (-10.0, 10.0),
        rows[:18],
        rows[18:],
        context_validator=_valid_deadzone,
        intervention_arity=1,
    )
    assert receipt.selected is not None
    library = importlib.import_module("nolane.external_core.cognitive_library").CognitiveLibrary.with_defaults()
    ledger = native.CausalProgramLedger(library.digest)
    evidence = EvidenceRecord("r262-parity", "ai.research.1", True, 0, 0, "bounded parity receipt")
    ledger.register(receipt.selected.program, evidence)
    state = ledger.to_state()
    restored = native.CausalProgramLedger.from_state(state)
    assert restored.to_state() == state
    assert restored.digest == ledger.digest
    assert json.loads(json.dumps(state, sort_keys=True)) == state

    with pytest.raises(ValueError, match="passing evidence"):
        native.CausalProgramLedger(library.digest).register(
            receipt.selected.program,
            EvidenceRecord("bad", "ai.research.1", False),
        )
    with pytest.raises(ValueError, match="clean evidence"):
        native.CausalProgramLedger(library.digest).register(
            receipt.selected.program,
            EvidenceRecord("false-accept", "ai.research.1", True, false_accepts=1),
        )


def test_wave5av_authority_version_debt_and_readme_cutover() -> None:
    row = build_component_implementation_ledger()["external.causal"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.causal"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.2"
    assert str(component_version("external.causal")) == "0.0.2"
    assert "cogcoder/r258_intervention_discovery.py" in row.legacy_sources
    assert "cogcoder/r262_complementary_experiment_program.py" in row.legacy_sources

    # Forward-stable migration invariant: later waves may legitimately reduce the
    # global debt count, but Causal must never regress into the debt projection.
    debt = json.loads((_root() / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in debt["components"]}
    assert "external.causal" not in ids
    assert sum(debt["counts_by_status"].values()) == len(debt["components"])

    status = (_root() / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AV" in status
    assert "external.causal" in status

    readme = (_root() / "README.md").read_text(encoding="utf-8")
    assert "CURRENT/STATUS.md" in readme
    assert "CURRENT/NATIVE_DEBT.md" in readme
