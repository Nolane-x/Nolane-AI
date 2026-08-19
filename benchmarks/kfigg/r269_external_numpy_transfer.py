from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Callable, Mapping

import numpy as np

from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r268_adaptive_causal_basis import synthesize_adaptive_causal_basis
from cogcoder.r269_causal_basis_adapter import compile_r268_experience
from cogcoder.r269_meta_learning_kernel import (
    MetaLearningConfig,
    PublicTaskSignature,
    run_cold_scratch,
    run_meta_learning_episode,
)

_PARENT = "fda7f502185266fedb00886d5786c6d28cc0e0eb"
_DEPENDENCY = "numpy==2.4.6"
_SOURCE_NAME = "numpy.add"
_DOMAIN = (-11, -7, -3, -2, -1, 0, 1, 2, 3, 4, 5, 7, 8, 9, 11, 13)
_OPS = ("add", "sub", "mul", "min", "max")
_DIAGNOSTIC_VALUES = (
    (0, 1),
    (1, 0),
    (2, 3),
    (-2, 4),
    (5, -1),
    (3, 7),
    (8, 2),
)
_TERMINAL_VALUES = ((11, 2), (-7, 3), (4, 9))


def _sha(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _python_scalar(value: object) -> int | float:
    item = value.item() if hasattr(value, "item") else value
    if isinstance(item, bool) or not isinstance(item, (int, float)):
        raise TypeError("external oracle must return a numeric scalar")
    return item


def _source_receipt():
    """Synthesize the source receipt from pinned NumPy callable I/O only.

    The query corpus is public test input chosen by R2.69; no source code,
    target labels, authored R2.68 benchmark case object, task/family identity,
    or NumPy implementation detail is supplied to the verifier.
    """
    fields = ("source_left", "source_right")
    discovery = ((-2.0, -2.0), (-2.0, -1.0), (-1.0, -2.0), (1.0, 3.0), (4.0, -2.0), (5.0, 7.0))
    validation = ((2.0, 5.0), (-3.0, 6.0), (8.0, -4.0))
    terminal = ((101.0, 103.0), (-109.0, 113.0), (127.0, -131.0))
    calls = 0

    def oracle(row: Mapping[str, object]) -> float:
        nonlocal calls
        calls += 1
        return float(
            np.add(
                np.float64(row["source_left"]),
                np.float64(row["source_right"]),
            )
        )

    def contexts(rows):
        return tuple(dict(zip(fields, values, strict=True)) for values in rows)

    need = OperatorInventionNeed(
        "R2.69 external NumPy add source",
        fields,
        "out",
        constants=(0.0, 2.0),
        max_depth=5,
        max_candidates=120_000,
    )
    receipt = synthesize_adaptive_causal_basis(
        oracle,
        fields,
        need,
        contexts(discovery),
        contexts(validation),
        terminal_contexts=contexts(terminal),
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
    return receipt, calls


def _source_authority_digest(receipt) -> str:
    payload = {
        "accepted_parent_sha": _PARENT,
        "dependency": _DEPENDENCY,
        "external_callable": _SOURCE_NAME,
        "source_exposure": "io_only",
        "passed": receipt.passed,
        "basis_size": receipt.selected_basis_size,
        "globally_minimal": receipt.globally_minimal,
        "proof_ledger_complete": receipt.structure.proof_ledger_complete,
        "lower_basis_universe_digest": receipt.structure.lower_basis_universe_digest,
        "necessity_witnesses": [row.witness_digest for row in receipt.structure.necessity_certificates],
        "lower_basis_witnesses": [row.witness_digest for row in receipt.structure.lower_basis_certificates],
        "expression": receipt.expression.to_data() if receipt.expression is not None else None,
        "terminal_exact": [receipt.final_validation_exact, receipt.final_validation_cases],
        "oracle_calls_total": receipt.oracle_calls_total,
    }
    return "r269.external-source-authority." + _sha(payload)


def _signature() -> PublicTaskSignature:
    return PublicTaskSignature(
        role_names=("left", "right"),
        numeric_domain="finite_integer",
        allowed_binary_ops=_OPS,
        query_space_digest="r269.external.numpy.scalar-integer-grid.v2",
        budget_contract="diagnostic<=6;transfer<=10;tight-scratch<=10;roomy-scratch<=96",
        finite_integer_values=_DOMAIN,
    )


def _contexts():
    names = ("left", "right")
    diagnostic = tuple(dict(zip(names, row, strict=True)) for row in _DIAGNOSTIC_VALUES)
    terminal = tuple(dict(zip(names, row, strict=True)) for row in _TERMINAL_VALUES)
    return diagnostic, terminal


def _external_value(name: str, row: Mapping[str, object]) -> int | float:
    left = np.int64(row["left"])
    right = np.int64(row["right"])
    if name == "numpy.maximum":
        return _python_scalar(np.maximum(left, right))
    if name == "numpy.minimum":
        return _python_scalar(np.minimum(left, right))
    if name == "numpy.subtract_swapped":
        return _python_scalar(np.subtract(right, left))
    if name == "numpy.bitwise_xor":
        return _python_scalar(np.bitwise_xor(left, right))
    raise ValueError(f"unknown external target: {name}")


def _tracked_oracle(name: str) -> tuple[Callable[[Mapping[str, object]], int | float], Callable[[], int]]:
    calls = 0

    def oracle(row: Mapping[str, object]) -> int | float:
        nonlocal calls
        calls += 1
        return _external_value(name, row)

    return oracle, lambda: calls


def _receipt_data(receipt, observed_calls: int) -> dict[str, object]:
    accounted = receipt.physical_diagnostic_calls + receipt.physical_terminal_calls
    return {
        "passed": receipt.passed,
        "mode": receipt.mode,
        "reason": receipt.reason,
        "selected_prior_digest": receipt.selected_prior_digest,
        "physical_diagnostic_calls": receipt.physical_diagnostic_calls,
        "physical_terminal_calls": receipt.physical_terminal_calls,
        "physical_oracle_calls": accounted,
        "observed_oracle_calls": observed_calls,
        "oracle_accounting_exact": accounted == observed_calls,
        "transfer_candidates_considered": receipt.transfer_candidates_considered,
        "scratch_candidates_considered": receipt.scratch_candidates_considered,
        "reused_observations": receipt.reused_observations,
        "false_accepts": receipt.false_accepts,
        "ledger_digests": [row.observation_digest for row in receipt.ledger],
    }


def _run_target(prior, signature, diagnostics, terminal, target: str, config, *, transfer: bool):
    oracle, calls = _tracked_oracle(target)
    if transfer:
        receipt = run_meta_learning_episode((prior,), signature, diagnostics, terminal, oracle, config)
    else:
        receipt = run_cold_scratch(signature, diagnostics, terminal, oracle, config)
    return receipt, _receipt_data(receipt, calls())


def _compute() -> dict[str, object]:
    if np.__version__ != "2.4.6":
        raise RuntimeError(f"R2.69 external evidence requires {_DEPENDENCY}, got {np.__version__}")

    source, source_calls = _source_receipt()
    source_verified = bool(
        source.passed
        and source.selected_basis_size == 2
        and source.globally_minimal
        and source.structure.proof_ledger_complete
        and source.false_accepts == 0
        and source.final_validation_cases > 0
        and source.final_validation_exact == source.final_validation_cases
        and source.oracle_calls_total == source_calls
    )
    if not source_verified:
        raise RuntimeError("external NumPy source receipt did not verify")

    prior = compile_r268_experience(
        source,
        source_authority_digest=_source_authority_digest(source),
        accepted_parent_sha=_PARENT,
    )
    signature = _signature()
    diagnostics, terminal = _contexts()
    tight = MetaLearningConfig(
        max_diagnostic_queries=6,
        transfer_candidate_cap=10,
        scratch_candidate_cap=10,
        scratch_max_depth=2,
        min_scratch_partitions=2,
    )
    roomy = MetaLearningConfig(
        max_diagnostic_queries=6,
        transfer_candidate_cap=10,
        scratch_candidate_cap=96,
        scratch_max_depth=2,
        min_scratch_partitions=2,
    )

    positives: list[dict[str, object]] = []
    transfer_solved = 0
    tight_solved = 0
    roomy_solved = 0
    transfer_calls = 0
    roomy_calls = 0
    transfer_work = 0
    roomy_work = 0
    false_accepts = 0
    accounting_exact = True

    for target in ("numpy.maximum", "numpy.minimum", "numpy.subtract_swapped"):
        transfer, transfer_data = _run_target(prior, signature, diagnostics, terminal, target, tight, transfer=True)
        tight_scratch, tight_data = _run_target(prior, signature, diagnostics, terminal, target, tight, transfer=False)
        roomy_scratch, roomy_data = _run_target(prior, signature, diagnostics, terminal, target, roomy, transfer=False)
        transfer_solved += int(transfer.passed)
        tight_solved += int(tight_scratch.passed)
        roomy_solved += int(roomy_scratch.passed)
        transfer_calls += transfer.physical_diagnostic_calls
        roomy_calls += roomy_scratch.physical_diagnostic_calls
        transfer_work += transfer.transfer_candidates_considered
        roomy_work += roomy_scratch.scratch_candidates_considered
        false_accepts += transfer.false_accepts + tight_scratch.false_accepts + roomy_scratch.false_accepts
        accounting_exact = accounting_exact and bool(
            transfer_data["oracle_accounting_exact"]
            and tight_data["oracle_accounting_exact"]
            and roomy_data["oracle_accounting_exact"]
        )
        positives.append(
            {
                "target": target,
                "source_exposure": "io_only",
                "target_exposure": "io_only",
                "transfer": transfer_data,
                "tight_scratch": tight_data,
                "roomy_scratch": roomy_data,
            }
        )

    negative_target = "numpy.bitwise_xor"
    negative, negative_data = _run_target(prior, signature, diagnostics, terminal, negative_target, tight, transfer=True)
    negative_cold, negative_cold_data = _run_target(prior, signature, diagnostics, terminal, negative_target, tight, transfer=False)
    false_accepts += negative.false_accepts + negative_cold.false_accepts
    accounting_exact = accounting_exact and bool(
        negative_data["oracle_accounting_exact"] and negative_cold_data["oracle_accounting_exact"]
    )
    negative_regret = max(
        0,
        negative.physical_diagnostic_calls - negative_cold.physical_diagnostic_calls,
    )

    result: dict[str, object] = {
        "schema_version": 1,
        "milestone": "R2.69",
        "capability": "external-black-box-meta-transfer",
        "dependency": _DEPENDENCY,
        "external_access": "callable-io-only",
        "source_external_callable": _SOURCE_NAME,
        "source_exposure": "io_only",
        "target_exposure": "io_only",
        "source_from_authored_generator": False,
        "accepted_parent_sha": _PARENT,
        "source_verified": source_verified,
        "source_basis_size": source.selected_basis_size,
        "source_oracle_calls_total": source.oracle_calls_total,
        "source_calls_observed": source_calls,
        "source_oracle_accounting_exact": source.oracle_calls_total == source_calls,
        "source_prior_digest": prior.portable_digest,
        "positive_targets": len(positives),
        "transfer_solved": transfer_solved,
        "tight_scratch_solved": tight_solved,
        "roomy_scratch_solved": roomy_solved,
        "source_prior_ablation_solved": tight_solved,
        "transfer_total_diagnostic_calls": transfer_calls,
        "roomy_scratch_total_diagnostic_calls": roomy_calls,
        "transfer_total_search_work": transfer_work,
        "roomy_scratch_total_search_work": roomy_work,
        "positive_cases": positives,
        "negative_target": negative_target,
        "negative_receipt_passed": negative.passed,
        "negative_cold_scratch_passed": negative_cold.passed,
        "negative_transfer_false_accepts": negative.false_accepts,
        "negative_extra_physical_oracle_regret": negative_regret,
        "negative_receipt": negative_data,
        "negative_cold_scratch_receipt": negative_cold_data,
        "oracle_accounting_exact": accounting_exact,
        "false_accepts": false_accepts,
        "trainable_parameter_count": 0,
    }
    gates = (
        result["source_verified"] is True,
        result["source_oracle_accounting_exact"] is True,
        result["source_from_authored_generator"] is False,
        transfer_solved == len(positives),
        roomy_solved == len(positives),
        tight_solved < transfer_solved,
        transfer_calls < roomy_calls,
        transfer_work < roomy_work,
        negative.passed is False,
        negative_cold.passed is False,
        negative_regret <= 1,
        result["negative_transfer_false_accepts"] == 0,
        accounting_exact,
        false_accepts == 0,
    )
    result["all_gates_pass"] = all(gates)
    result["semantic_result_digest"] = _sha(result)
    return result


@lru_cache(maxsize=1)
def _cached_json() -> str:
    return json.dumps(_compute(), sort_keys=True, separators=(",", ":"), allow_nan=False)


def run_external_transfer() -> dict[str, object]:
    return json.loads(_cached_json())


__all__ = ["run_external_transfer"]
