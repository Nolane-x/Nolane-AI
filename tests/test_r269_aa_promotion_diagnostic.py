from __future__ import annotations

import hashlib

from benchmarks.kfigg.r269_promotion_authority import run_promotion_authority_benchmark
from cogcoder.r269_promotion_authority import PromotionEvidenceAuthority


def test_promotion_authority_rejection_exposes_exact_evidence(monkeypatch):
    original = PromotionEvidenceAuthority.adjudicate

    def diagnostic(self, candidate, evidence, attestation):
        envelope = original(self, candidate, evidence, attestation)
        assert envelope.decision.promoted, (
            f"promotion rejected: reason={envelope.decision.reason}; "
            f"champion={evidence.champion_accepted_targets}/{evidence.heldout_targets}; "
            f"challenger={evidence.challenger_accepted_targets}/{evidence.heldout_targets}; "
            f"oracle_advantage={evidence.oracle_call_advantage}; "
            f"search_advantage={evidence.search_work_advantage}; "
            f"false_accepts={evidence.false_accepts}; "
            f"terminal={evidence.terminal_verification_passed}; "
            f"budget_exact={evidence.budget_accounting_exact}; "
            f"authority={evidence.verifier_authority_digest}"
        )
        return envelope

    monkeypatch.setattr(PromotionEvidenceAuthority, 'adjudicate', diagnostic)
    run_promotion_authority_benchmark(
        authority_root_digest=hashlib.sha256(b'r269-promotion-diagnostic-root').hexdigest(),
        hosted_run_identity='pytest:r269-promotion-diagnostic',
        source_tree_digest=hashlib.sha256(b'r269-promotion-diagnostic-tree').hexdigest(),
    )
