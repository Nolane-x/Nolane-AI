from __future__ import annotations

from benchmarks.kfigg.r269_meta_learning import run_benchmark


def test_r269_benchmark_reports_matched_meta_learning_evidence():
    result = run_benchmark()

    required = {
        "schema_version",
        "passed",
        "claim",
        "positive",
        "negative",
        "ablations",
        "determinism",
        "strong_claim_gate",
        "trainable_parameter_count",
    }
    assert required.issubset(result)
    assert result["schema_version"] == 1
    assert result["trainable_parameter_count"] == 0

    positive = result["positive"]
    assert positive["total"] >= 18
    assert positive["transfer_solves"] <= positive["total"]
    assert positive["cold_scratch_solves"] <= positive["total"]
    assert positive["roomy_scratch_solves"] <= positive["total"]
    assert positive["transfer_physical_oracle_calls"] >= 0
    assert positive["cold_scratch_physical_oracle_calls"] >= 0
    assert positive["roomy_scratch_physical_oracle_calls"] >= 0
    assert positive["transfer_proof_distinct_search_work"] >= 0
    assert positive["cold_scratch_proof_distinct_search_work"] >= 0
    assert isinstance(positive["per_case"], list)
    assert len(positive["per_case"]) == positive["total"]

    negative = result["negative"]
    assert negative["total"] >= 12
    assert negative["false_accepts"] == 0
    assert negative["max_extra_physical_oracle_regret"] >= 0
    assert isinstance(negative["per_case"], list)
    assert len(negative["per_case"]) == negative["total"]

    ablations = result["ablations"]
    assert "source_prior" in ablations
    assert "shuffled_prior" in ablations
    assert ablations["source_prior"]["total"] == positive["total"]
    assert ablations["shuffled_prior"]["total"] == positive["total"]

    gate = result["strong_claim_gate"]
    assert gate["zero_false_accepts"] is True
    assert gate["roomy_scratch_expressibility"] is True
    assert gate["deterministic_replay"] is True
    assert result["passed"] is gate["passed"]


def test_r269_benchmark_is_semantically_deterministic_within_process():
    first = run_benchmark()
    second = run_benchmark()
    assert first["determinism"]["semantic_digest"] == second["determinism"]["semantic_digest"]
    assert first["positive"] == second["positive"]
    assert first["negative"] == second["negative"]
    assert first["ablations"] == second["ablations"]
