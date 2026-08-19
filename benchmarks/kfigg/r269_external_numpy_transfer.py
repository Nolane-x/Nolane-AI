from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Mapping

import numpy as np

from benchmarks.kfigg import r268_adaptive_causal_basis as r268_benchmark
from cogcoder.r268_adaptive_causal_basis import synthesize_adaptive_causal_basis
from cogcoder.r269_causal_basis_adapter import compile_r268_experience
from cogcoder.r269_meta_learning_kernel import (
    MetaLearningConfig,
    PublicTaskSignature,
    run_cold_scratch,
    run_meta_learning_episode,
)

_PARENT = "fda7f502185266fedb00886d5786c6d28cc0e0eb"
_DOMAIN = (-11, -7, -3, -1, 0, 2, 5, 9, 13)
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


def _source_receipt():
    case = r268_benchmark._cases()[1]
    name, fields, oracle, discovery, validation, terminal, _expected = case
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


def _source_authority_digest(receipt) -> str:
    payload = {
        "accepted_parent_sha": _PARENT,
        "passed": receipt.passed,
        "basis_size": receipt.selected_basis_size,
        "globally_minimal": receipt.globally_minimal,
        "proof_ledger_complete": receipt.structure.proof_ledger_complete,
        "lower_basis_universe_digest": receipt.structure.lower_basis_universe_digest,
        "necessity_witnesses": [row.witness_digest for row in receipt.structure.necessity_certificates],
        "lower_basis_witnesses": [row.witness_digest for row in receipt.structure.lower_basis_certificates],
        "expression": receipt.expression.to_data() if receipt.expression is not None else None,
        "terminal_exact": [receipt.final_validation_exact, receipt.final_validation_cases],
    }
    return "r269.external-source-authority." + _sha(payload)


def _signature() -> PublicTaskSignature:
    return PublicTaskSignature(
        role_names=("left", "right"),
        numeric_domain="finite_integer",
        allowed_binary_ops=_OPS,
        query_space_digest="r269.external.numpy.scalar-integer-grid.v1",
        budget_contract="diagnostic<=6;proof-distinct-candidate<=10",
        finite_integer_values=_DOMAIN,
    )


def _contexts():
    names = ("left", "right")
    diagnostic = tuple(dict(zip(names, row, strict=True)) for row in _DIAGNOSTIC_VALUES)
    terminal = tuple(dict(zip(names, row, strict=True)) for row in _TERMINAL_VALUES)
    return diagnostic, terminal


def _python_scalar(value: object) -> int | float:
    item = value.item() if hasattr(value, "item") else value
    if isinstance(item, bool) or not isinstance(item, (int, float)):
        raise TypeError("external oracle must return a numeric scalar")
    return item


def _oracle_for(name: str):
    if name == "numpy.maximum":
        return lambda row: _python_scalar(np.maximum(np.int64(row["left"]), np.int64(row["right"])))
    if name == "numpy.minimum":
        return lambda row: _python_scalar(np.minimum(np.int64(row["left"]), np.int64(row["right"])))
    if name == "numpy.subtract_swapped":
        return lambda row: _python_scalar(np.subtract(np.int64(row["right"]), np.int64(row["left"])))
    if name == "numpy.bitwise_xor":
        return lambda row: _python_scalar(np.bitwise_xor(np.int64(row["left"]), np.int64(row["right"])))
    raise ValueError(f"unknown external target: {name}")


def _receipt_data(receipt) -> dict[str, object]:
    return {
        "passed": receipt.passed,
        "mode": receipt.mode,
        "reason": receipt.reason,
        "selected_prior_digest": receipt.selected_prior_digest,
        "physical_diagnostic_calls": receipt.physical_diagnostic_calls,
        "physical_terminal_calls": receipt.physical_terminal_calls,
        "transfer_candidates_considered": receipt.transfer_candidates_considered,
        "scratch_candidates_considered": receipt.scratch_candidates_considered,
        "reused_observations": receipt.reused_observations,
        "false_accepts": receipt.false_accepts,
        "ledger_digests": [row.observation_digest for row in receipt.ledger],
    }


def _compute() -> dict[str, object]:
    if np.__version__ != "2.4.6":
        raise RuntimeError(f"R2.69 external evidence requires numpy==2.4.6, got {np.__version__}")

    source = _source_receipt()
    source_verified = bool(
        source.passed
        and source.selected_basis_size == 2
        and source.globally_minimal
        and source.structure.proof_ledger_complete
        and source.false_accepts == 0
        and source.final_validation_cases > 0
        and source.final_validation_exact == source.final_validation_cases
    )
    if not source_verified:
        raise RuntimeError("accepted R2.68 source receipt did not verify")

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

    for target in ("numpy.maximum", "numpy.minimum", "numpy.subtract_swapped"):
        oracle = _oracle_for(target)
        transfer = run_meta_learning_episode((prior,), signature, diagnostics, terminal, oracle, tight)
        tight_scratch = run_cold_scratch(signature, diagnostics, terminal, oracle, tight)
        roomy_scratch = run_cold_scratch(signature, diagnostics, terminal, oracle, roomy)
        transfer_solved += int(transfer.passed)
        tight_solved += int(tight_scratch.passed)
        roomy_solved += int(roomy_scratch.passed)
        transfer_calls += transfer.physical_diagnostic_calls
        roomy_calls += roomy_scratch.physical_diagnostic_calls
        transfer_work += transfer.transfer_candidates_considered
        roomy_work += roomy_scratch.scratch_candidates_considered
        false_accepts += transfer.false_accepts + tight_scratch.false_accepts + roomy_scratch.false_accepts
        positives.append(
            {
                "target": target,
                "transfer": _receipt_data(transfer),
                "tight_scratch": _receipt_data(tight_scratch),
                "roomy_scratch": _receipt_data(roomy_scratch),
            }
        )

    negative_oracle = _oracle_for("numpy.bitwise_xor")
    negative = run_meta_learning_episode((prior,), signature, diagnostics, terminal, negative_oracle, tight)
    false_accepts += negative.false_accepts

    result: dict[str, object] = {
        "milestone": "R2.69",
        "capability": "external-black-box-meta-transfer",
        "dependency": "numpy==2.4.6",
        "external_access": "callable-io-only",
        "accepted_parent_sha": _PARENT,
        "source_verified": source_verified,
        "source_basis_size": source.selected_basis_size,
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
        "negative_target": "numpy.bitwise_xor",
        "negative_receipt_passed": negative.passed,
        "negative_transfer_false_accepts": int(negative.passed and negative.mode == "transfer"),
        "negative_receipt": _receipt_data(negative),
        "false_accepts": false_accepts,
        "trainable_parameter_count": 0,
    }
    gates = (
        result["source_verified"] is True,
        transfer_solved == len(positives),
        roomy_solved == len(positives),
        tight_solved < transfer_solved,
        transfer_calls < roomy_calls,
        transfer_work < roomy_work,
        negative.passed is False,
        result["negative_transfer_false_accepts"] == 0,
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
