from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.implementation_status import ImplementationStatus, build_component_implementation_ledger
from nolane.external_core.causal import InterventionSpec
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


def _native():
    return importlib.import_module("nolane.external_core.experimentation")


def _probe_grid(native, values=(-1, 0, 1, 2)):
    return tuple(native.ExperimentProbe((x, y)) for x in values for y in values)


def _hypothesis(native, probes, fn, *, display_name: str):
    return native.ExperimentHypothesis(
        tuple((probe.probe_id, fn(*probe.args)) for probe in probes),
        display_name=display_name,
    )


def test_wave5aw_native_experimentation_public_boundary_and_no_reverse_imports() -> None:
    native = _native()
    assert native.COMPONENT_ID == "external.experimentation"
    assert native.COMPONENT_VERSION == "0.0.1"
    assert native.MIGRATED_FROM == "cogcoder R2.60 active-probe lineage"
    for name in (
        "ExperimentProbe",
        "ExperimentHypothesis",
        "VersionSpace",
        "ProbeSelectionReceipt",
        "ShadowExperimentReceipt",
        "select_informative_probe",
        "run_shadow_experiment",
        "ExperimentLedger",
    ):
        assert hasattr(native, name), name

    imports = _imports(_root() / "nolane" / "external_core" / "experimentation.py")
    assert not any(name.startswith("cogcoder.r") for name in imports)
    assert not any(name.startswith("cogcoder.organization") for name in imports)
    assert not any(name.startswith("research") or name.startswith("ai") for name in imports)


def test_wave5aw_probe_and_hypothesis_identity_are_content_addressed_and_rename_stable() -> None:
    native = _native()
    intervention = InterventionSpec(((1, -10.0),))
    first = native.ExperimentProbe((1, -1), intervention=intervention)
    second = native.ExperimentProbe((1, -1), intervention=InterventionSpec(((1, -10),)))
    assert first.probe_id == second.probe_id
    assert first.to_state() == second.to_state()

    plain = native.ExperimentProbe((1, -1))
    assert plain.probe_id != first.probe_id

    probes = _probe_grid(native, (-1, 0, 1))
    a = _hypothesis(native, probes, lambda x, y: x + y, display_name="add")
    b = _hypothesis(native, probes, lambda x, y: x + y, display_name="renamed-human-label")
    assert a.hypothesis_id == b.hypothesis_id
    assert a.semantic_state() == b.semantic_state()

    with pytest.raises(ValueError):
        native.ExperimentProbe(())
    with pytest.raises((TypeError, ValueError)):
        native.ExperimentProbe((float("nan"),))
    with pytest.raises(ValueError):
        native.VersionSpace(())
    with pytest.raises(ValueError, match="duplicate"):
        native.VersionSpace((a, b))


def test_wave5aw_probe_selection_matches_r260_partition_oracle_and_is_order_invariant() -> None:
    native = _native()
    legacy = importlib.import_module("cogcoder.r260_active_repository_probes")
    patch = importlib.import_module("cogcoder.r247_executable_patch_cegis")
    query = importlib.import_module("cogcoder.r252_repository_query")

    native_probes = _probe_grid(native)
    hypotheses = (
        _hypothesis(native, native_probes, lambda x, y: x + y, display_name="add"),
        _hypothesis(native, native_probes, lambda x, y: x - y, display_name="sub"),
        _hypothesis(native, native_probes, lambda x, y: x * y, display_name="mul"),
    )
    version_space = native.VersionSpace(hypotheses)
    selected = native.select_informative_probe(version_space, native_probes)
    reversed_selected = native.select_informative_probe(
        native.VersionSpace(tuple(reversed(hypotheses))), tuple(reversed(native_probes))
    )
    assert selected.status == reversed_selected.status == "selected"
    assert selected.probe is not None and reversed_selected.probe is not None
    assert selected.probe.probe_id == reversed_selected.probe.probe_id
    assert selected.partition_signature == reversed_selected.partition_signature

    def candidate(cid, expression):
        source = f"def root(x, y):\n    return {expression}\n"
        return query.RepositoryPatchCandidate(cid, (), (("main.py", source),), 0, 0)

    legacy_receipt = legacy.solve_repository_patch_with_active_probes(
        (candidate("add", "x + y"), candidate("sub", "x - y"), candidate("mul", "x * y")),
        (patch.PatchTest("initial-zero", (0, 0), 0),),
        legacy.enumerate_probe_inputs(2, (-1, 0, 1, 2)),
        lambda x, y: x + y,
        verification_inputs=legacy.enumerate_probe_inputs(2, (-1, 0, 1)),
        max_selection_oracle_calls=2,
    )
    assert legacy_receipt.rounds
    assert selected.probe.args == legacy_receipt.rounds[0].probe.args
    assert selected.partition_signature == legacy_receipt.rounds[0].partition_signature
    assert selected.partition_count == legacy_receipt.rounds[0].partition_count
    assert selected.largest_partition == legacy_receipt.rounds[0].largest_partition


def test_wave5aw_noninformative_and_budget_paths_abstain_without_oracle_calls() -> None:
    native = _native()
    probes = _probe_grid(native, (-1, 0, 1))
    extra = native.ExperimentProbe((7, 11))
    hypothesis_domain = (*probes, extra)
    left = _hypothesis(native, hypothesis_domain, lambda x, y: x + y, display_name="left")
    right = native.ExperimentHypothesis(
        tuple((probe.probe_id, sum(probe.args)) for probe in probes)
        + ((extra.probe_id, 999),),
        display_name="right",
    )

    selection = native.select_informative_probe(native.VersionSpace((left, right)), probes)
    assert selection.status == "abstain"
    assert selection.reason == "no_informative_probe"
    assert selection.probe is None

    calls = {"count": 0}

    def oracle(probe):
        calls["count"] += 1
        return sum(probe.args)

    no_information = native.run_shadow_experiment(
        native.VersionSpace((left, right)),
        probes,
        oracle,
        verification_probes=probes[:2],
        max_selection_oracle_calls=3,
    )
    assert no_information.status == "abstain"
    assert no_information.reason == "no_informative_probe"
    assert no_information.selection_oracle_calls == 0
    assert no_information.verification_oracle_calls == 0
    assert calls["count"] == 0

    informative = native.VersionSpace(
        (
            _hypothesis(native, probes, lambda x, y: x + y, display_name="add"),
            _hypothesis(native, probes, lambda x, y: x - y, display_name="sub"),
        )
    )
    no_budget = native.run_shadow_experiment(
        informative,
        probes,
        oracle,
        verification_probes=probes[:2],
        max_selection_oracle_calls=0,
    )
    assert no_budget.status == "abstain"
    assert no_budget.reason == "selection_oracle_budget_exhausted"
    assert no_budget.selection_oracle_calls == 0
    assert calls["count"] == 0


def test_wave5aw_shadow_execution_is_pure_verified_and_does_not_self_promote() -> None:
    native = _native()
    probes = _probe_grid(native)
    verification = _probe_grid(native, (-2, -1, 0, 1))
    all_probes = tuple({row.probe_id: row for row in (*probes, *verification)}.values())
    hypotheses = (
        _hypothesis(native, all_probes, lambda x, y: x + y, display_name="add"),
        _hypothesis(native, all_probes, lambda x, y: x - y, display_name="sub"),
        _hypothesis(native, all_probes, lambda x, y: x * y, display_name="mul"),
    )
    space = native.VersionSpace(hypotheses)
    space_before = space.to_state()
    probes_before = tuple(row.to_state() for row in probes)
    calls = {"count": 0}

    def oracle(probe):
        calls["count"] += 1
        x, y = probe.args
        return x + y

    receipt = native.run_shadow_experiment(
        space,
        probes,
        oracle,
        verification_probes=verification,
        max_selection_oracle_calls=2,
    )
    assert receipt.status == "accept"
    assert receipt.reason == "shadow_experiment_verified"
    assert receipt.selected is not None
    assert receipt.selected.hypothesis_id == hypotheses[0].hypothesis_id
    assert receipt.selection_oracle_calls == 1
    assert receipt.verification_oracle_calls == len(verification)
    assert receipt.oracle_calls_total == calls["count"]
    assert receipt.promoted is False
    assert space.to_state() == space_before
    assert tuple(row.to_state() for row in probes) == probes_before

    deceptive_calls = {"count": 0}

    def deceptive(probe):
        deceptive_calls["count"] += 1
        x, y = probe.args
        if probe.probe_id == verification[1].probe_id:
            return 999
        return x + y

    failed = native.run_shadow_experiment(
        space,
        probes,
        deceptive,
        verification_probes=verification,
        max_selection_oracle_calls=2,
    )
    assert failed.status == "abstain"
    assert failed.reason == "independent_verification_failed"
    assert failed.selected is None
    assert failed.promoted is False


def test_wave5aw_experiment_ledger_requires_clean_evidence_and_roundtrips_deterministically() -> None:
    native = _native()
    probes = _probe_grid(native, (-1, 0, 1))
    verification = _probe_grid(native, (-2, -1, 0, 1))
    all_probes = tuple({row.probe_id: row for row in (*probes, *verification)}.values())
    space = native.VersionSpace(
        (
            _hypothesis(native, all_probes, lambda x, y: x + y, display_name="add"),
            _hypothesis(native, all_probes, lambda x, y: x - y, display_name="sub"),
        )
    )
    receipt = native.run_shadow_experiment(
        space,
        probes,
        lambda probe: probe.args[0] + probe.args[1],
        verification_probes=verification,
        max_selection_oracle_calls=1,
    )
    assert receipt.status == "accept"

    ledger = native.ExperimentLedger("causal-basis:test")
    evidence = EvidenceRecord("wave5aw-parity", "ai.research.1", True, 0, 0, "verified shadow experiment")
    record = ledger.register(receipt, evidence)
    assert record.experiment_id == receipt.experiment_id
    assert ledger.register(receipt, evidence) == record
    state = ledger.to_state()
    encoded = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    restored = native.ExperimentLedger.from_state(json.loads(encoded))
    restored_encoded = json.dumps(restored.to_state(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert restored_encoded == encoded
    assert restored.digest == ledger.digest

    with pytest.raises(ValueError, match="passing evidence"):
        native.ExperimentLedger("causal-basis:test").register(
            receipt, EvidenceRecord("bad", "ai.research.1", False)
        )
    with pytest.raises(ValueError, match="clean evidence"):
        native.ExperimentLedger("causal-basis:test").register(
            receipt, EvidenceRecord("dirty", "ai.research.1", True, regressions=1)
        )

    corrupt = json.loads(encoded)
    corrupt["schema_version"] = 999
    with pytest.raises(ValueError, match="schema"):
        native.ExperimentLedger.from_state(corrupt)


def test_wave5aw_authority_version_and_debt_cutover() -> None:
    row = build_component_implementation_ledger()["external.experimentation"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.experimentation"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.2"
    assert str(component_version("external.experimentation")) == "0.0.2"
    assert "cogcoder/r260_active_repository_probes.py" in row.legacy_sources

    debt = json.loads((_root() / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in debt["components"]}
    assert "external.experimentation" not in ids
    assert sum(debt["counts_by_status"].values()) == len(debt["components"])

    status = (_root() / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AW" in status
    assert "external.experimentation" in status
    assert "moves from 4 to 3 non-native" in status
