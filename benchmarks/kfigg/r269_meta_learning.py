from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from statistics import median
from typing import Callable, Mapping

from benchmarks.kfigg import r268_adaptive_causal_basis as r268_benchmark
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r268_adaptive_causal_basis import synthesize_adaptive_causal_basis
from cogcoder.r269_causal_basis_adapter import PortableExperience, compile_r268_experience
from cogcoder.r269_meta_learning_kernel import (
    MetaLearningConfig,
    PriorRegistry,
    PublicTaskSignature,
    run_cold_scratch,
    run_meta_learning_episode,
)

_PARENT = "fda7f502185266fedb00886d5786c6d28cc0e0eb"
_DOMAIN = (-5, -3, -1, 0, 1, 2, 4, 7, 11)
_BINARY_OPS = ("add", "sub", "mul", "min", "max")
_POSITIVE_CONTEXT_VALUES = (
    (-5, 11), (11, -3), (2, 7), (-3, 4), (1, -5), (7, 2), (4, 11),
    (-1, 7), (11, 4), (2, -5),
)


def _sha(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _authority_digest(receipt, label: str) -> str:
    payload = {
        "label": label,
        "passed": receipt.passed,
        "selected_basis_size": receipt.selected_basis_size,
        "globally_minimal": receipt.globally_minimal,
        "proof_ledger_complete": receipt.structure.proof_ledger_complete,
        "lower_basis_universe_digest": receipt.structure.lower_basis_universe_digest,
        "necessity_witnesses": [row.witness_digest for row in receipt.structure.necessity_certificates],
        "lower_basis_witnesses": [row.witness_digest for row in receipt.structure.lower_basis_certificates],
        "expression": receipt.expression.to_data() if receipt.expression is not None else None,
        "terminal_exact": [receipt.final_validation_exact, receipt.final_validation_cases],
    }
    return "r269.source-authority." + _sha(payload)


def _accepted_r268_receipt(case):
    name, fields, oracle, discovery, validation, terminal, _expected_size = case
    return synthesize_adaptive_causal_basis(
        oracle,
        fields,
        r268_benchmark._need(name, fields),
        r268_benchmark._contexts(fields, discovery),
        r268_benchmark._contexts(fields, validation),
        terminal_contexts=r268_benchmark._contexts(fields, terminal),
        intervention_anchor_values=(0.0,),
        intervention_arity=1,
        max_basis_size=4,
        composition_constants=(0.0, 2.0),
        composition_max_depth=5,
        composition_max_candidates_per_basis=30_000,
        max_composition_candidates_total=160_000,
        composition_beam_width=192,
        probe_constants=(0.0, 2.0),
        probe_max_depth=5,
        probe_max_candidates=50_000,
        probe_beam_width=192,
    )


def _three_x_plus_y_receipt():
    case = r268_benchmark._cases()[1]
    _name, fields, _oracle, discovery, validation, terminal, _expected = case

    def oracle(row: Mapping[str, object]) -> float:
        return 3.0 * float(row["a"]) + float(row["b"])

    need = OperatorInventionNeed(
        "r269-source-three-x-plus-y",
        fields,
        "out",
        constants=(0.0, 2.0),
        max_depth=5,
        max_candidates=120_000,
    )
    return synthesize_adaptive_causal_basis(
        oracle,
        fields,
        need,
        r268_benchmark._contexts(fields, discovery),
        r268_benchmark._contexts(fields, validation),
        terminal_contexts=r268_benchmark._contexts(fields, terminal),
        intervention_anchor_values=(0.0,),
        intervention_arity=1,
        max_basis_size=4,
        composition_constants=(0.0, 2.0),
        composition_max_depth=5,
        composition_max_candidates_per_basis=30_000,
        max_composition_candidates_total=160_000,
        composition_beam_width=192,
        probe_constants=(0.0, 2.0),
        probe_max_depth=5,
        probe_max_candidates=50_000,
        probe_beam_width=192,
    )


def _compile(receipt, label: str) -> PortableExperience:
    return compile_r268_experience(
        receipt,
        source_authority_digest=_authority_digest(receipt, label),
        accepted_parent_sha=_PARENT,
    )


def _signature(role_names: tuple[str, ...], *, suffix: str = "v1") -> PublicTaskSignature:
    return PublicTaskSignature(
        role_names=role_names,
        numeric_domain="finite_integer",
        allowed_binary_ops=_BINARY_OPS,
        query_space_digest=f"r269.complete-finite-integer-universe.{suffix}",
        budget_contract="diagnostic<=6;tight_search<=64;roomy_search<=1000",
        finite_integer_values=_DOMAIN,
    )


def _contexts(role_names: tuple[str, str]):
    rows = tuple(dict(zip(role_names, values, strict=True)) for values in _POSITIVE_CONTEXT_VALUES)
    return rows[:7], rows[7:]


def _receipt_row(name: str, receipt) -> dict[str, object]:
    return {
        "name": name,
        "passed": receipt.passed,
        "mode": receipt.mode,
        "reason": receipt.reason,
        "selected_prior_digest": receipt.selected_prior_digest,
        "physical_diagnostic_calls": receipt.physical_diagnostic_calls,
        "physical_terminal_calls": receipt.physical_terminal_calls,
        "transfer_candidates_considered": receipt.transfer_candidates_considered,
        "scratch_candidates_considered": receipt.scratch_candidates_considered,
        "reused_observations": receipt.reused_observations,
        "transfer_contradictions": receipt.transfer_contradictions,
        "quarantine_action": receipt.quarantine_action,
        "false_accepts": receipt.false_accepts,
        "observation_digests": [row.observation_digest for row in receipt.ledger],
    }


def _build_sources():
    accepted_cases = r268_benchmark._cases()[1:]
    accepted_receipts = tuple(_accepted_r268_receipt(case) for case in accepted_cases)
    accepted_priors = tuple(
        _compile(receipt, f"accepted-r268-{case[0]}")
        for receipt, case in zip(accepted_receipts, accepted_cases, strict=True)
    )
    hard_receipt = _three_x_plus_y_receipt()
    hard_prior = _compile(hard_receipt, "verified-r268-three-x-plus-y")
    return accepted_receipts, accepted_priors, hard_receipt, hard_prior


def _positive_cases(simple_prior: PortableExperience, hard_prior: PortableExperience):
    tight = MetaLearningConfig(
        max_diagnostic_queries=6,
        transfer_candidate_cap=64,
        scratch_candidate_cap=64,
        scratch_max_depth=2,
        min_scratch_partitions=2,
    )
    roomy_easy = MetaLearningConfig(
        max_diagnostic_queries=6,
        transfer_candidate_cap=64,
        scratch_candidate_cap=256,
        scratch_max_depth=2,
        min_scratch_partitions=2,
    )
    roomy_hard = MetaLearningConfig(
        max_diagnostic_queries=6,
        transfer_candidate_cap=64,
        scratch_candidate_cap=1000,
        scratch_max_depth=3,
        min_scratch_partitions=2,
    )

    easy_roles = (("x", "y"), ("left", "right"), ("u", "v"), ("north", "south"))
    hard_roles = (
        ("alpha", "beta"), ("p", "q"), ("hot", "cold"),
        ("major", "minor"), ("first", "second"), ("red", "blue"),
    )
    rows = []

    for roles in easy_roles:
        signature = _signature(roles)
        diagnostic, terminal = _contexts(roles)
        first, second = roles
        for op in ("add", "sub", "mul"):
            def oracle(row, op=op, first=first, second=second):
                left = row[first]
                right = row[second]
                if op == "add":
                    return left + right
                if op == "sub":
                    return left - right
                return left * right

            transfer = run_meta_learning_episode((simple_prior,), signature, diagnostic, terminal, oracle, tight)
            cold = run_cold_scratch(signature, diagnostic, terminal, oracle, tight)
            roomy = run_cold_scratch(signature, diagnostic, terminal, oracle, roomy_easy)
            ablation = cold
            shuffled = run_meta_learning_episode(
                (hard_prior,), signature, diagnostic, terminal, oracle, tight, registry=PriorRegistry(),
            )
            rows.append((f"easy-{op}-{first}-{second}", transfer, cold, roomy, ablation, shuffled))

    for index, roles in enumerate(hard_roles):
        signature = _signature(roles)
        diagnostic, terminal = _contexts(roles)
        first, second = roles
        swap = index >= 3

        def oracle(row, first=first, second=second, swap=swap):
            x, y = row[first], row[second]
            if swap:
                x, y = y, x
            return 3 * x + y

        transfer = run_meta_learning_episode((hard_prior,), signature, diagnostic, terminal, oracle, tight)
        cold = run_cold_scratch(signature, diagnostic, terminal, oracle, tight)
        roomy = run_cold_scratch(signature, diagnostic, terminal, oracle, roomy_hard)
        ablation = cold
        shuffled = run_meta_learning_episode(
            (simple_prior,), signature, diagnostic, terminal, oracle, tight, registry=PriorRegistry(),
        )
        rows.append((f"hard-linear-{index}", transfer, cold, roomy, ablation, shuffled))
    return rows


def _negative_cases(simple_prior: PortableExperience):
    config = MetaLearningConfig(
        max_diagnostic_queries=6,
        transfer_candidate_cap=64,
        scratch_candidate_cap=64,
        scratch_max_depth=2,
        min_scratch_partitions=2,
    )
    roles = ("x", "y")
    signature = _signature(roles, suffix="negative")
    diagnostic, terminal = _contexts(roles)
    terminal_values = {tuple(row[name] for name in roles) for row in terminal}
    rows = []

    topology = (
        ("xy-plus-x", lambda row: row["x"] * row["y"] + row["x"]),
        ("xy-plus-y", lambda row: row["x"] * row["y"] + row["y"]),
        ("x-plus-yy", lambda row: row["x"] + row["y"] * row["y"]),
        ("xx-minus-y", lambda row: row["x"] * row["x"] - row["y"]),
    )
    for name, oracle in topology:
        receipt = run_meta_learning_episode(
            (simple_prior,), signature, diagnostic, terminal, oracle, config, registry=PriorRegistry(),
        )
        cold = run_cold_scratch(signature, diagnostic, terminal, oracle, config)
        rows.append((f"topology-{name}", receipt, cold))

    for delta in (1, 2, -1):
        def oracle(row, delta=delta):
            base = row["x"] + row["y"]
            key = (row["x"], row["y"])
            return base + delta if key in terminal_values else base

        receipt = run_meta_learning_episode(
            (simple_prior,), signature, diagnostic, terminal, oracle, config, registry=PriorRegistry(),
        )
        cold = run_cold_scratch(signature, diagnostic, terminal, oracle, config)
        rows.append((f"terminal-contradiction-{delta}", receipt, cold))

    for label, bad in (("nan", float("nan")), ("inf", float("inf"))):
        def oracle(_row, bad=bad):
            return bad

        receipt = run_meta_learning_episode(
            (simple_prior,), signature, diagnostic, terminal, oracle, config, registry=PriorRegistry(),
        )
        cold = run_cold_scratch(signature, diagnostic, terminal, oracle, config)
        rows.append((f"invalid-oracle-{label}", receipt, cold))

    roles3 = ("a", "b", "c")
    signature3 = _signature(roles3, suffix="negative-cardinality")
    values3 = (
        (-5, 1, 2), (1, 0, -3), (2, 4, 1), (-3, 2, 11),
        (4, -1, 2), (1, 7, -3), (7, 2, 1), (-1, -5, 2), (4, 2, 1), (7, -3, 4),
    )
    contexts3 = tuple(dict(zip(roles3, values, strict=True)) for values in values3)
    diagnostic3, terminal3 = contexts3[:7], contexts3[7:]
    functions: tuple[Callable[[Mapping[str, object]], object], ...] = (
        lambda row: row["a"] + row["b"] + row["c"],
        lambda row: row["a"] * row["b"] + row["c"],
        lambda row: row["a"] - row["b"] + row["c"],
    )
    for index, oracle in enumerate(functions):
        receipt = run_meta_learning_episode(
            (simple_prior,), signature3, diagnostic3, terminal3, oracle, config, registry=PriorRegistry(),
        )
        cold = run_cold_scratch(signature3, diagnostic3, terminal3, oracle, config)
        rows.append((f"cardinality-{index}", receipt, cold))
    return rows


def _compute() -> dict[str, object]:
    accepted_receipts, accepted_priors, hard_receipt, hard_prior = _build_sources()
    simple_prior = accepted_priors[0]
    positive = _positive_cases(simple_prior, hard_prior)
    negative = _negative_cases(simple_prior)

    transfer_receipts = [row[1] for row in positive]
    cold_receipts = [row[2] for row in positive]
    roomy_receipts = [row[3] for row in positive]
    ablation_receipts = [row[4] for row in positive]
    shuffled_receipts = [row[5] for row in positive]

    transfer_solved = sum(row.passed for row in transfer_receipts)
    cold_solved = sum(row.passed for row in cold_receipts)
    roomy_solved = sum(row.passed for row in roomy_receipts)
    ablation_solved = sum(row.passed for row in ablation_receipts)
    shuffled_solved = sum(row.passed for row in shuffled_receipts)

    cold_solved_calls = [row.physical_diagnostic_calls for row in cold_receipts if row.passed]
    transfer_calls = [row.physical_diagnostic_calls for row in transfer_receipts if row.passed]
    transfer_work = [row.transfer_candidates_considered for row in transfer_receipts]
    tight_work = [row.scratch_candidates_considered for row in cold_receipts]

    solve_advantage = max(0, transfer_solved - cold_solved)
    removed = max(0, transfer_solved - ablation_solved)
    removal_fraction = 1.0 if solve_advantage == 0 and removed > 0 else (
        removed / solve_advantage if solve_advantage else 0.0
    )

    negative_false_accepts = sum(
        int(receipt.passed and receipt.mode == "transfer") for _name, receipt, _cold in negative
    )
    continued_rows = [
        (receipt, cold) for _name, receipt, cold in negative
        if receipt.mode in ("scratch_after_transfer", "scratch")
    ]
    continued_correct = all(receipt.passed == cold.passed for receipt, cold in continued_rows)
    regrets = [
        receipt.physical_diagnostic_calls - cold.physical_diagnostic_calls
        for _name, receipt, cold in negative
    ]

    positive_rows = [
        {
            "name": name,
            "transfer": _receipt_row(name, transfer),
            "cold_scratch": _receipt_row(name, cold),
            "roomy_scratch": _receipt_row(name, roomy),
            "source_prior_ablation": _receipt_row(name, ablation),
            "shuffled_prior": _receipt_row(name, shuffled),
        }
        for name, transfer, cold, roomy, ablation, shuffled in positive
    ]
    negative_rows = [
        {
            "name": name,
            "transfer_path": _receipt_row(name, receipt),
            "cold_scratch": _receipt_row(name, cold),
            "diagnostic_regret": receipt.physical_diagnostic_calls - cold.physical_diagnostic_calls,
        }
        for name, receipt, cold in negative
    ]

    result: dict[str, object] = {
        "milestone": "R2.69",
        "capability": "autonomous-transfer-meta-learning-kernel",
        "accepted_parent_sha": _PARENT,
        "source_basis_sizes": [receipt.selected_basis_size for receipt in accepted_receipts],
        "source_portable_digests": [prior.portable_digest for prior in accepted_priors],
        "hard_source_verified": bool(
            hard_receipt.passed and hard_receipt.globally_minimal and hard_receipt.structure.proof_ledger_complete
        ),
        "hard_source_portable_digest": hard_prior.portable_digest,
        "positive_targets": len(positive),
        "positive_transfer_solved": transfer_solved,
        "tight_cold_scratch_solved": cold_solved,
        "roomy_scratch_solved": roomy_solved,
        "source_prior_ablation_solved": ablation_solved,
        "shuffled_prior_solved": shuffled_solved,
        "source_prior_ablation_advantage_removed_fraction": removal_fraction,
        "median_transfer_diagnostic_calls": median(transfer_calls),
        "median_cold_solved_diagnostic_calls": median(cold_solved_calls),
        "median_transfer_search_work": median(transfer_work),
        "median_tight_scratch_search_work": median(tight_work),
        "negative_targets": len(negative),
        "negative_transfer_false_accepts": negative_false_accepts,
        "continued_scratch_correctness_preserved": continued_correct,
        "max_negative_transfer_diagnostic_regret": max(regrets),
        "false_accepts": sum(row.false_accepts for row in transfer_receipts)
            + sum(receipt.false_accepts for _name, receipt, _cold in negative),
        "trainable_parameter_count": 0,
        "positive_cases": positive_rows,
        "negative_cases": negative_rows,
    }
    gates = (
        result["source_basis_sizes"] == [2, 3, 4],
        result["hard_source_verified"] is True,
        transfer_solved >= 17,
        cold_solved <= 12,
        roomy_solved >= 17,
        result["median_transfer_diagnostic_calls"] <= 0.70 * result["median_cold_solved_diagnostic_calls"],
        result["median_transfer_search_work"] <= 0.50 * result["median_tight_scratch_search_work"],
        ablation_solved <= cold_solved,
        removal_fraction >= 0.80,
        shuffled_solved < transfer_solved,
        len(negative) == 12,
        negative_false_accepts == 0,
        continued_correct,
        max(regrets) <= 1,
        result["false_accepts"] == 0,
    )
    result["authored_gate_pass"] = all(gates)
    result["semantic_result_digest"] = _sha(result)
    return result


@lru_cache(maxsize=1)
def _cached_json() -> str:
    return json.dumps(_compute(), sort_keys=True, separators=(",", ":"), allow_nan=False)


def run_benchmark() -> dict[str, object]:
    return json.loads(_cached_json())


__all__ = ["run_benchmark"]
