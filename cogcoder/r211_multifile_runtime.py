from __future__ import annotations

from dataclasses import dataclass, replace

from .r210_copy_edit_features import encode_evidence, enumerate_copy_edit_candidates
from .r210_copy_edit_model import CopyEditProposalNet, rank_candidates
from .r211_counterfactual_localizer import CounterfactualLocalizer, LocalizationScore
from .r29_patch_search import PatchSearchOutcome, VerifierGuidedPatchSearch


@dataclass(frozen=True, slots=True)
class MultiFileRepairOutcome:
    localized: LocalizationScore | None
    patch_outcome: PatchSearchOutcome | None

    @property
    def success(self) -> bool:
        return bool(self.patch_outcome is not None and self.patch_outcome.success)


def run_multifile_repair(
    case,
    proposer: CopyEditProposalNet,
    *,
    localizer: CounterfactualLocalizer,
    patch_budget: int = 2,
) -> MultiFileRepairOutcome:
    ranked = localizer.rank(
        case.symbols,
        graph=case.graph,
        failing_test_node=case.failing_test_node,
        language='javascript',
        probes=case.probes,
        probes_by_node=case.probes_by_node,
        coverage=case.coverage,
    )
    if not ranked:
        return MultiFileRepairOutcome(None, None)
    selected = ranked[0]
    symbol = next(item for item in case.symbols if item.node_id == selected.node_id)
    candidates = enumerate_copy_edit_candidates(
        symbol.source,
        language='javascript',
        target_path=symbol.path,
        candidate_prefix='r211-',
    )
    local_probes = case.probes_by_node.get(symbol.node_id, case.probes)
    scores = rank_candidates(
        proposer,
        symbol.source,
        language='javascript',
        target_path=symbol.path,
        candidates=candidates,
        evidence_features=encode_evidence(local_probes),
    )
    scored = tuple(
        replace(candidate, proposal_score=float(scores[index].item()))
        for index, candidate in enumerate(candidates)
    )
    outcome = VerifierGuidedPatchSearch(budget=patch_budget).search(
        case.snapshot,
        scored,
        case.evaluator,
        graph=case.graph,
    )
    return MultiFileRepairOutcome(selected, outcome)
