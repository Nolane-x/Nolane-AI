from __future__ import annotations

# The accepted R2.64 implementation is preserved byte-for-byte in the base
# module for auditability and rollback.  The public module keeps the original
# API while routing the solver through the post-merge frontier-fairness hotfix.
from cogcoder.r264_unified_adaptive_repository_search_base import (
    AdaptiveExpansionRound,
    AdaptiveFrontierCandidate,
    UnifiedAdaptiveRepositoryReceipt,
    expand_adaptive_repository_frontier,
)
from cogcoder.r264_frontier_fairness_hotfix import solve_unified_adaptive_repository_patch


__all__ = [
    'AdaptiveFrontierCandidate',
    'AdaptiveExpansionRound',
    'UnifiedAdaptiveRepositoryReceipt',
    'expand_adaptive_repository_frontier',
    'solve_unified_adaptive_repository_patch',
]
