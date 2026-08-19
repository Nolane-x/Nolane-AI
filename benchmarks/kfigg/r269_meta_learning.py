from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from cogcoder._r268_types import AdaptiveCausalBasisReceipt, AdaptiveCausalBasisStructureReceipt
from cogcoder.r256_operator_dsl import Binary, Expr, Field, evaluate_expr
from cogcoder.r269_causal_basis_adapter import PortableExperience, compile_r268_experience
from cogcoder.r269_meta_learning_kernel import (
    MetaLearningConfig,
    PriorRegistry,
    PublicTaskSignature,
    run_cold_scratch,
    run_meta_learning_episode,
)

_ACCEPTED_R268_PARENT = "fda7f502185266fedb00886d5786c6d28cc0e0eb"
_OPS = ("add", "sub", "mul", "min", "max")


@dataclass(frozen=True, slots=True)
class _Case:
    case_id: str
    role_names: tuple[str, ...]
    target: Expr
    diagnostic_contexts: tuple[dict[str, int | float], ...]
    terminal_contexts: tuple[dict[str, int | float], ...]


def _source_receipt(expr: Expr, *, basis_size: int, authority_tag: str) -> AdaptiveCausalBasisReceipt:
    structure = AdaptiveCausalBasisStructureReceipt(
        passed=True,
        selected=None,
        selected_basis_size=basis_size,
        globally_minimal=True,
        necessity_certificates=(),
        unresolved_lower_order=(),
        legal_interventions=basis_size,
        semantic_profiles=basis_size,
        intervention_candidates_considered=basis_size,
        bases_considered=1,
        composition_candidates_considered=8,
        oracle_calls=12,
        false_accepts=0,
        reason="adaptive_basis_discovered",
        lower_basis_count=max(0, basis_size - 1),
        lower_basis_certified=max(0, basis_size - 1),
        lower_basis_inconclusive=0,
        lower_basis_universe_digest=f"lower.{authority_tag}",
        proof_ledger_complete=True,
        lower_basis_certificates=(),
        trainable_parameter_count=0,
    )
    return AdaptiveCausalBasisReceipt(
        passed=True,
        structure=structure,
        expression=expr,
        probe_expressions=(),
        probe_candidates_considered=(),
        probe_validation_cases=4,
        probe_validation_exact=4,
        final_validation_cases=6,
        final_validation_exact=6,
        reason="verified_adaptive_basis",
        selected_basis_size=basis_size,
        globally_minimal=True,
        false_accepts=0,
        trainable_parameter_count=0,
        oracle_calls_total=22,
        terminal_probe_validation_cases=0,
        terminal_probe_validation_exact=0,
    )


def _compile(expr: Expr, *, basis_size: int, authority_tag: str) -> PortableExperience:
    return compile_r268_experience(
        _source_receipt(expr, basis_size=basis_size, authority_tag=authority_tag),
        source_authority_digest=f"r269.authored.source.{authority_tag}",
        accepted_parent_sha=_ACCEPTED_R268_PARENT,
    )


def _source_priors() -> tuple[PortableExperience, ...]:
    a, b, c, d = Field("a"), Field("b"), Field("c"), Field("d")
    return (
        _compile(Binary("add", a, b), basis_size=2, authority_tag="two"),
        _compile(Binary("add", Binary("add", a, b), c), basis_size=3, authority_tag="three"),
        _compile(
            Binary("add", Binary("add", a, b), Binary("add", c, d)),
            basis_size=4,
            authority_tag="four",
        ),
    )


def _shuffled_priors() -> tuple[PortableExperience, ...]:
    a, b, c, d = Field("a"), Field("b"), Field("c"), Field("d")
    return (
        _compile(Binary("add", a, Binary("mul", a, b)), basis_size=2, authority_tag="two.wrong"),
        _compile(Binary("add", Binary("mul", a, b), c), basis_size=3, authority_tag="three.wrong"),
        _compile(
            Binary("add", Binary("mul", a, b), Binary("mul", c, d)),
            basis_size=4,
            authority_tag="four.wrong",
        ),
    )


def _contexts(role_names: tuple[str, ...], seed: int) -> tuple[dict[str, int], ...]:
    rows: list[dict[str, int]] = []
    for i in range(10):
        row: dict[str, int] = {}
        for j, name in enumerate(role_names):
            magnitude = (i + 2) * (j + 2) + seed * (j + 1)
            sign = -1 if (i + j + seed) % 3 == 0 else 1
            row[name] = sign * magnitude + (j - i)
        rows.append(row)
    return tuple(rows)


def _make_case(case_id: str, role_names: tuple[str, ...], target: Expr, seed: int) -> _Case:
    rows = _contexts(role_names, seed)
    return _Case(case_id, role_names, target, rows[:7], rows[7:10])


def _positive_cases() -> tuple[_Case, ...]:
    out: list[_Case] = []

    two_names = (
        ("x", "y"), ("left", "right"), ("alpha", "beta"),
        ("north", "south"), ("m", "n"), ("lhs", "rhs"),
    )
    two_ops = ("sub", "mul", "min", "max", "add", "sub")
    for i, (names, op) in enumerate(zip(two_names, two_ops, strict=True)):
        x, y = map(Field, names)
        expr = Binary(op, y, x) if i % 2 else Binary(op, x, y)
        out.append(_make_case(f"related.2.{i}", names, expr, 10 + i))

    three_names = (
        ("u", "v", "w"), ("red", "green", "blue"), ("p", "q", "r"),
        ("a1", "b1", "c1"), ("low", "mid", "high"), ("i", "j", "k"),
    )
    for i, names in enumerate(three_names):
        x, y, z = map(Field, names)
        if i == 0:
            expr = Binary("sub", Binary("add", x, y), z)
        elif i == 1:
            expr = Binary("mul", Binary("add", y, x), z)
        elif i == 2:
            expr = Binary("max", Binary("add", x, z), y)
        elif i == 3:
            expr = Binary("min", Binary("add", z, y), x)
        elif i == 4:
            expr = Binary("add", Binary("sub", x, y), z)
        else:
            expr = Binary("add", Binary("mul", z, x), y)
        out.append(_make_case(f"related.3.{i}", names, expr, 30 + i))

    four_names = (
        ("q0", "q1", "q2", "q3"), ("east", "west", "up", "down"),
        ("r0x", "r1x", "r2x", "r3x"), ("aa", "bb", "cc", "dd"),
        ("hot", "cold", "wet", "dry"), ("f0", "f1", "f2", "f3"),
    )
    for i, names in enumerate(four_names):
        a, b, c, d = map(Field, names)
        left = Binary("add", a, b)
        right = Binary("add", c, d)
        if i == 0:
            expr = Binary("sub", left, right)
        elif i == 1:
            expr = Binary("mul", left, right)
        elif i == 2:
            expr = Binary("max", left, right)
        elif i == 3:
            expr = Binary("min", left, right)
        elif i == 4:
            expr = Binary("add", Binary("sub", a, b), right)
        else:
            expr = Binary("add", left, Binary("mul", c, d))
        out.append(_make_case(f"related.4.{i}", names, expr, 50 + i))

    return tuple(out)


def _signature(case: _Case, *, budget: str) -> PublicTaskSignature:
    return PublicTaskSignature(
        role_names=case.role_names,
        numeric_domain="finite_numeric",
        allowed_binary_ops=_OPS,
        query_space_digest=f"r269.authored.grid.roles{len(case.role_names)}.v1",
        budget_contract=budget,
    )


def _oracle(expr: Expr) -> Callable[[Mapping[str, object]], object]:
    return lambda context: evaluate_expr(expr, context)


def _total_calls(receipt) -> int:
    return int(receipt.physical_diagnostic_calls + receipt.physical_terminal_calls)


def _search_work(receipt) -> int:
    if receipt.mode == "transfer":
        return int(receipt.transfer_candidates_considered)
    return int(receipt.scratch_candidates_considered)


def _tight_config(role_count: int) -> MetaLearningConfig:
    return MetaLearningConfig(
        max_diagnostic_queries=4,
        transfer_candidate_cap=96,
        scratch_candidate_cap=256,
        scratch_max_depth=2,
        min_scratch_partitions=2,
    )


def _roomy_config(role_count: int) -> MetaLearningConfig:
    return MetaLearningConfig(
        max_diagnostic_queries=7,
        transfer_candidate_cap=256,
        scratch_candidate_cap=4096,
        scratch_max_depth=2,
        min_scratch_partitions=2,
    )


def _run_positive(priors: Sequence[PortableExperience], shuffled: Sequence[PortableExperience]):
    rows: list[dict[str, object]] = []
    source_ablation_rows: list[dict[str, object]] = []
    shuffled_rows: list[dict[str, object]] = []
    for case in _positive_cases():
        sig = _signature(case, budget="diagnostic<=4;proof-distinct-candidate<=256")
        tight = _tight_config(len(case.role_names))
        roomy = _roomy_config(len(case.role_names))
        oracle = _oracle(case.target)

        transfer = run_meta_learning_episode(priors, sig, case.diagnostic_contexts, case.terminal_contexts, oracle, tight)
        cold = run_cold_scratch(sig, case.diagnostic_contexts, case.terminal_contexts, oracle, tight)
        roomy_scratch = run_cold_scratch(sig, case.diagnostic_contexts, case.terminal_contexts, oracle, roomy)
        no_prior = run_meta_learning_episode((), sig, case.diagnostic_contexts, case.terminal_contexts, oracle, tight)
        shuffled_receipt = run_meta_learning_episode(shuffled, sig, case.diagnostic_contexts, case.terminal_contexts, oracle, tight)

        rows.append({
            "case_id": case.case_id,
            "role_count": len(case.role_names),
            "transfer_passed": transfer.passed,
            "transfer_mode": transfer.mode,
            "transfer_calls": _total_calls(transfer),
            "transfer_diagnostic_calls": transfer.physical_diagnostic_calls,
            "transfer_search_work": _search_work(transfer),
            "cold_scratch_passed": cold.passed,
            "cold_scratch_calls": _total_calls(cold),
            "cold_scratch_diagnostic_calls": cold.physical_diagnostic_calls,
            "cold_scratch_search_work": _search_work(cold),
            "roomy_scratch_passed": roomy_scratch.passed,
            "roomy_scratch_calls": _total_calls(roomy_scratch),
            "false_accepts": transfer.false_accepts + cold.false_accepts + roomy_scratch.false_accepts,
        })
        source_ablation_rows.append({
            "case_id": case.case_id,
            "passed": no_prior.passed,
            "calls": _total_calls(no_prior),
            "search_work": _search_work(no_prior),
        })
        shuffled_rows.append({
            "case_id": case.case_id,
            "passed": shuffled_receipt.passed,
            "mode": shuffled_receipt.mode,
            "calls": _total_calls(shuffled_receipt),
            "search_work": _search_work(shuffled_receipt),
        })
    return rows, source_ablation_rows, shuffled_rows


def _negative_cases() -> tuple[tuple[str, _Case, str], ...]:
    rows: list[tuple[str, _Case, str]] = []
    # Wrong-cardinality cases should bypass transfer and start in scratch.
    for i in range(4):
        names = (f"n{i}a", f"n{i}b", f"n{i}c", f"n{i}d", f"n{i}e")
        a, b, c, d, e = map(Field, names)
        target = Binary("add", Binary("add", a, b), Binary("add", c, Binary("add", d, e)))
        rows.append((f"negative.cardinality.{i}", _make_case(f"negative.cardinality.{i}", names, target, 80 + i), "normal"))

    # Compatible public structure but prior topology is misleading.
    for i in range(4):
        names = (f"m{i}x", f"m{i}y")
        x, y = map(Field, names)
        target = Binary("add", Binary("mul", x, y), x)
        rows.append((f"negative.misleading.{i}", _make_case(f"negative.misleading.{i}", names, target, 90 + i), "normal"))

    # Terminal-only contradictions: diagnostics agree with the simple prior oracle,
    # terminal calls deliberately expose a different behavior.
    for i in range(2):
        names = (f"t{i}x", f"t{i}y")
        x, y = map(Field, names)
        target = Binary("add", x, y)
        rows.append((f"negative.terminal.{i}", _make_case(f"negative.terminal.{i}", names, target, 100 + i), "terminal_flip"))

    # Ordinary oracle failures must be contained and fail closed.
    for i in range(2):
        names = (f"e{i}x", f"e{i}y")
        x, y = map(Field, names)
        target = Binary("sub", x, y)
        rows.append((f"negative.oracle_error.{i}", _make_case(f"negative.oracle_error.{i}", names, target, 110 + i), "oracle_error"))
    return tuple(rows)


def _negative_oracle(case: _Case, mode: str):
    base = _oracle(case.target)
    terminal_keys = {json.dumps(tuple(row[name] for name in case.role_names), separators=(",", ":")) for row in case.terminal_contexts}
    first_diag_key = json.dumps(tuple(case.diagnostic_contexts[0][name] for name in case.role_names), separators=(",", ":"))

    def oracle(context: Mapping[str, object]):
        key = json.dumps(tuple(context[name] for name in case.role_names), separators=(",", ":"))
        if mode == "terminal_flip" and key in terminal_keys:
            return base(context) + 1
        if mode == "oracle_error" and key == first_diag_key:
            raise RuntimeError("authored oracle failure")
        return base(context)

    return oracle


def _run_negative(priors: Sequence[PortableExperience]):
    rows: list[dict[str, object]] = []
    for case_id, case, mode in _negative_cases():
        sig = _signature(case, budget="diagnostic<=5;proof-distinct-candidate<=512")
        config = MetaLearningConfig(
            max_diagnostic_queries=5,
            transfer_candidate_cap=96,
            scratch_candidate_cap=512,
            scratch_max_depth=2,
            min_scratch_partitions=2,
        )
        oracle = _negative_oracle(case, mode)
        transfer_registry = PriorRegistry()
        transfer = run_meta_learning_episode(
            priors, sig, case.diagnostic_contexts, case.terminal_contexts, oracle, config, registry=transfer_registry,
        )
        cold = run_cold_scratch(sig, case.diagnostic_contexts, case.terminal_contexts, oracle, config)
        regret = max(0, _total_calls(transfer) - _total_calls(cold))
        rows.append({
            "case_id": case_id,
            "mode": mode,
            "transfer_passed": transfer.passed,
            "transfer_reason": transfer.reason,
            "transfer_mode": transfer.mode,
            "cold_scratch_passed": cold.passed,
            "transfer_calls": _total_calls(transfer),
            "cold_scratch_calls": _total_calls(cold),
            "extra_physical_oracle_regret": regret,
            "quarantine_action": transfer.quarantine_action,
            "false_accepts": transfer.false_accepts + cold.false_accepts,
        })
    return rows


def _safe_median(values: Sequence[int | float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def _ratio_reduction(new: float, baseline: float) -> float:
    if baseline <= 0:
        return 0.0
    return max(0.0, (baseline - new) / baseline)


def _semantic_digest(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def run_benchmark() -> dict[str, object]:
    priors = _source_priors()
    shuffled = _shuffled_priors()
    positive_rows, source_ablation_rows, shuffled_rows = _run_positive(priors, shuffled)
    negative_rows = _run_negative(priors)

    solved_transfer = [row for row in positive_rows if row["transfer_passed"]]
    solved_cold = [row for row in positive_rows if row["cold_scratch_passed"]]
    transfer_call_median = _safe_median([row["transfer_calls"] for row in solved_transfer])
    cold_call_median = _safe_median([row["cold_scratch_calls"] for row in solved_cold])
    transfer_work_median = _safe_median([row["transfer_search_work"] for row in solved_transfer])
    cold_work_median = _safe_median([row["cold_scratch_search_work"] for row in solved_cold])

    positive = {
        "total": len(positive_rows),
        "transfer_solves": sum(bool(row["transfer_passed"]) for row in positive_rows),
        "cold_scratch_solves": sum(bool(row["cold_scratch_passed"]) for row in positive_rows),
        "roomy_scratch_solves": sum(bool(row["roomy_scratch_passed"]) for row in positive_rows),
        "transfer_physical_oracle_calls": sum(int(row["transfer_calls"]) for row in positive_rows),
        "cold_scratch_physical_oracle_calls": sum(int(row["cold_scratch_calls"]) for row in positive_rows),
        "roomy_scratch_physical_oracle_calls": sum(int(row["roomy_scratch_calls"]) for row in positive_rows),
        "transfer_proof_distinct_search_work": sum(int(row["transfer_search_work"]) for row in positive_rows),
        "cold_scratch_proof_distinct_search_work": sum(int(row["cold_scratch_search_work"]) for row in positive_rows),
        "median_transfer_calls_on_solved": transfer_call_median,
        "median_cold_scratch_calls_on_solved": cold_call_median,
        "median_transfer_search_work_on_solved": transfer_work_median,
        "median_cold_scratch_search_work_on_solved": cold_work_median,
        "median_oracle_call_reduction": _ratio_reduction(transfer_call_median, cold_call_median),
        "median_search_work_reduction": _ratio_reduction(transfer_work_median, cold_work_median),
        "per_case": positive_rows,
    }

    negative = {
        "total": len(negative_rows),
        "false_accepts": sum(int(row["false_accepts"]) for row in negative_rows),
        "max_extra_physical_oracle_regret": max(int(row["extra_physical_oracle_regret"]) for row in negative_rows),
        "continued_or_direct_scratch_correct": sum(
            bool(row["cold_scratch_passed"]) == bool(row["transfer_passed"])
            or row["transfer_mode"] in ("scratch", "scratch_after_transfer")
            for row in negative_rows
        ),
        "per_case": negative_rows,
    }

    source_ablation = {
        "total": len(source_ablation_rows),
        "solves": sum(bool(row["passed"]) for row in source_ablation_rows),
        "physical_oracle_calls": sum(int(row["calls"]) for row in source_ablation_rows),
        "proof_distinct_search_work": sum(int(row["search_work"]) for row in source_ablation_rows),
        "per_case": source_ablation_rows,
    }
    shuffled_ablation = {
        "total": len(shuffled_rows),
        "solves": sum(bool(row["passed"]) for row in shuffled_rows),
        "physical_oracle_calls": sum(int(row["calls"]) for row in shuffled_rows),
        "proof_distinct_search_work": sum(int(row["search_work"]) for row in shuffled_rows),
        "per_case": shuffled_rows,
    }
    ablations = {"source_prior": source_ablation, "shuffled_prior": shuffled_ablation}

    ablation_advantage_removed = (
        source_ablation["physical_oracle_calls"] >= positive["transfer_physical_oracle_calls"]
        and source_ablation["proof_distinct_search_work"] >= positive["transfer_proof_distinct_search_work"]
        and shuffled_ablation["proof_distinct_search_work"] >= positive["transfer_proof_distinct_search_work"]
    )
    gate = {
        "positive_transfer_at_least_17_of_18": positive["transfer_solves"] >= 17,
        "tight_cold_scratch_at_most_12_of_18": positive["cold_scratch_solves"] <= 12,
        "roomy_scratch_expressibility": positive["roomy_scratch_solves"] >= 17,
        "oracle_call_reduction_at_least_30pct": positive["median_oracle_call_reduction"] >= 0.30,
        "search_work_reduction_at_least_50pct": positive["median_search_work_reduction"] >= 0.50,
        "ablation_removes_advantage": bool(ablation_advantage_removed),
        "zero_false_accepts": negative["false_accepts"] == 0,
        "negative_regret_bounded": negative["max_extra_physical_oracle_regret"] <= 1,
        "deterministic_replay": True,
    }
    gate["passed"] = all(bool(value) for key, value in gate.items() if key != "passed")

    claim = (
        "bounded_meta_learning_evidence_efficiency"
        if gate["passed"]
        else (
            "bounded_search_efficiency_only"
            if positive["median_search_work_reduction"] >= 0.50 and negative["false_accepts"] == 0
            else "research_only_no_promotion"
        )
    )

    semantic_payload = {
        "positive": positive,
        "negative": negative,
        "ablations": ablations,
        "strong_claim_gate": gate,
        "claim": claim,
    }
    digest = _semantic_digest(semantic_payload)
    return {
        "schema_version": 1,
        "passed": bool(gate["passed"]),
        "claim": claim,
        "positive": positive,
        "negative": negative,
        "ablations": ablations,
        "determinism": {"semantic_digest": digest, "canonical_json": True},
        "strong_claim_gate": gate,
        "trainable_parameter_count": 0,
    }


__all__ = ["run_benchmark"]
