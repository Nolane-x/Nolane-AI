from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.implementation_status import ImplementationStatus, build_component_implementation_ledger


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


def test_wave5au_canonical_cognitive_library_owns_typed_operator_vocabulary_and_catalog() -> None:
    library_module = importlib.import_module("nolane.external_core.cognitive_library")
    operators = importlib.import_module("nolane.external_core.cognitive_operators")
    vocabulary = importlib.import_module("nolane.external_core.cognitive_vocabulary")
    catalog = importlib.import_module("nolane.external_core.cognitive_catalog")

    assert library_module.COMPONENT_ID == "external.cognitive_library"
    assert library_module.COMPONENT_VERSION == "0.0.1"
    assert library_module.MIGRATED_FROM == "cogcoder R2.53/R2.56/R2.57 cognitive-library lineage"

    for module, names in (
        (operators, ("Expr", "Field", "Const", "Unary", "Binary", "IfElse", "evaluate_expr", "expr_digest", "enumerate_expressions")),
        (vocabulary, ("TemplateParam", "AbstractionCall", "LearnedAbstraction", "CognitiveVocabulary", "make_abstraction", "expand_expr", "evaluate_with_vocabulary")),
        (catalog, ("SubOperatorDescriptor", "OperatorFamilyDescriptor", "build_default_externalization_catalog")),
        (library_module, ("CognitiveLibrary",)),
    ):
        for name in names:
            assert hasattr(module, name), f"missing canonical cognitive-library object: {module.__name__}.{name}"


def test_wave5au_canonical_cognitive_library_has_no_reverse_historical_imports() -> None:
    root = _root()
    for suffix in ("cognitive_library", "cognitive_operators", "cognitive_vocabulary", "cognitive_catalog"):
        imports = _imports(root / "nolane" / "external_core" / f"{suffix}.py")
        assert not any(module.startswith("cogcoder.r") for module in imports)
        assert not any(module.startswith("cogcoder.organization") for module in imports)


def test_wave5au_operator_and_vocabulary_semantics_match_historical_lineage() -> None:
    native_ops = importlib.import_module("nolane.external_core.cognitive_operators")
    legacy_ops = importlib.import_module("cogcoder.r256_operator_dsl")
    native_vocab = importlib.import_module("nolane.external_core.cognitive_vocabulary")
    legacy_vocab = importlib.import_module("cogcoder.r257_vocabulary")

    native_expr = native_ops.Binary("add", native_ops.Field("x"), native_ops.Const(2))
    legacy_expr = legacy_ops.Binary("add", legacy_ops.Field("x"), legacy_ops.Const(2))
    assert native_expr.to_data() == legacy_expr.to_data()
    assert native_ops.expr_digest(native_expr) == legacy_ops.expr_digest(legacy_expr)
    assert native_ops.evaluate_expr(native_expr, {"x": 5}) == legacy_ops.evaluate_expr(legacy_expr, {"x": 5}) == 7

    native_template = native_ops.Binary("add", native_vocab.TemplateParam(0), native_ops.Const(1))
    legacy_template = legacy_ops.Binary("add", legacy_vocab.TemplateParam(0), legacy_ops.Const(1))
    native_abs = native_vocab.make_abstraction(
        native_template,
        parameter_count=1,
        support_task_ids=("t3", "t1", "t2"),
        raw_occurrence_cost=12,
        rewritten_cost=8,
    )
    legacy_abs = legacy_vocab.make_abstraction(
        legacy_template,
        parameter_count=1,
        support_task_ids=("t3", "t1", "t2"),
        raw_occurrence_cost=12,
        rewritten_cost=8,
    )
    assert native_abs.abstraction_id == legacy_abs.abstraction_id
    assert native_abs.support_task_ids == legacy_abs.support_task_ids
    native_vocabulary = native_vocab.CognitiveVocabulary((native_abs,))
    call = native_vocab.AbstractionCall(native_abs.abstraction_id, (native_ops.Field("x"),))
    assert native_vocab.evaluate_with_vocabulary(call, {"x": 9}, native_vocabulary) == 10


def test_wave5au_default_catalog_preserves_explicit_capability_status_semantics() -> None:
    native = importlib.import_module("nolane.external_core.cognitive_catalog")
    legacy = importlib.import_module("cogcoder.r253_operator_catalog")

    native_families = native.build_default_externalization_catalog()
    legacy_families = legacy.build_default_externalization_catalog()
    assert [(row.family_id, row.summary) for row in native_families] == [
        (row.family_id, row.summary) for row in legacy_families
    ]
    assert [
        (sub.operator_id, sub.status, sub.summary, tuple(sorted(sub.tags)))
        for family in native_families
        for sub in family.suboperators
    ] == [
        (sub.operator_id, sub.status, sub.summary, tuple(sorted(sub.tags)))
        for family in legacy_families
        for sub in family.suboperators
    ]
    assert {sub.status for family in native_families for sub in family.suboperators} <= {
        "implemented", "host_required", "knowledge_only", "experimental"
    }


def test_wave5au_library_snapshot_is_deterministic_roundtrippable_and_fail_closed() -> None:
    library_module = importlib.import_module("nolane.external_core.cognitive_library")
    operators = importlib.import_module("nolane.external_core.cognitive_operators")
    vocabulary = importlib.import_module("nolane.external_core.cognitive_vocabulary")
    catalog = importlib.import_module("nolane.external_core.cognitive_catalog")

    library = library_module.CognitiveLibrary.with_defaults()
    abstraction = vocabulary.make_abstraction(
        operators.Binary("add", vocabulary.TemplateParam(0), operators.Const(1)),
        parameter_count=1,
        support_task_ids=("task-b", "task-a", "task-c"),
        raw_occurrence_cost=12,
        rewritten_cost=8,
    )
    library.register_abstraction(abstraction)
    state = library.to_state()
    restored = library_module.CognitiveLibrary.from_state(state)
    assert restored.to_state() == state
    assert restored.digest == library.digest
    assert json.loads(json.dumps(state, sort_keys=True)) == state

    first_family = library.families()[0]
    conflicting = catalog.OperatorFamilyDescriptor(
        first_family.family_id,
        first_family.summary + " conflict",
        first_family.suboperators,
    )
    with pytest.raises(ValueError, match="conflicting cognitive operator family"):
        library.register_family(conflicting)

    conflicting_abstraction = vocabulary.LearnedAbstraction(
        abstraction.abstraction_id,
        abstraction.parameter_count,
        operators.Binary("sub", vocabulary.TemplateParam(0), operators.Const(1)),
        abstraction.support_task_ids,
        abstraction.raw_occurrence_cost,
        abstraction.rewritten_cost,
    )
    with pytest.raises(ValueError, match="abstraction digest collision"):
        library.register_abstraction(conflicting_abstraction)


def test_wave5au_authority_version_and_native_debt_cutover() -> None:
    row = build_component_implementation_ledger()["external.cognitive_library"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.cognitive_library"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("external.cognitive_library")) == "0.0.1"
    for source in (
        "cogcoder/r253_operator_catalog.py",
        "cogcoder/r256_operator_dsl.py",
        "cogcoder/r257_vocabulary.py",
    ):
        assert source in row.legacy_sources

    state = json.loads((_root() / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    ids = {record["component_id"] for record in state["components"]}
    wave5au_debt = {
        "external.capability_acquisition",
        "external.causal",
        "external.experimentation",
        "external.transfer_meta",
        "neural.shared",
    }
    assert "external.cognitive_library" not in ids
    assert "neural.shared" in ids
    assert ids <= wave5au_debt
    assert len(state["components"]) <= 5
    assert state["counts_by_status"].get("frozen_asset", 0) == 1
    assert state["counts_by_status"].get("historical_only", 0) <= 4


def test_wave5au_current_status_tracks_cognitive_library_cutover() -> None:
    status = (_root() / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AU" in status
    assert "external.cognitive_library" in status
    assert "5 non-native" in status
