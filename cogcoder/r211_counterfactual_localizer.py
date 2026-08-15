from __future__ import annotations

import hashlib
import math
from collections import deque
from dataclasses import dataclass
from typing import Mapping, Sequence

import torch
from torch import Tensor

from .r28_repo_world import RepoWorldGraph
from .r210_copy_edit_features import (
    FailureProbe,
    canonicalize_source,
    encode_evidence,
    enumerate_copy_edit_candidates,
)
from .r210_copy_edit_model import CopyEditProposalNet, rank_candidates
from .r29_patch_model import RepositorySnapshot, apply_candidate


@dataclass(frozen=True, slots=True)
class TestCoverageObservation:
    test_node: str
    covered_nodes: frozenset[str]
    passed: bool


@dataclass(frozen=True, slots=True)
class SymbolSlice:
    node_id: str
    path: str
    source: str

    def __post_init__(self) -> None:
        if not self.node_id or not self.path or not self.source:
            raise ValueError('node_id, path and source are required')


@dataclass(frozen=True, slots=True)
class LocalizationScore:
    node_id: str
    path: str
    score: float
    edit_gain: float
    graph_distance: int
    canonical_fingerprint: str
    features: tuple[float, ...]


def canonical_source_fingerprint(source: str, *, language: str) -> str:
    canonical = '\x1f'.join(canonicalize_source(source, language=language)).encode('utf-8')
    return hashlib.sha256(canonical).hexdigest()


def _distances(
    graph: RepoWorldGraph,
    seed: str,
    *,
    allowed_kinds: tuple[str, ...] = ('tests', 'calls', 'depends_on', 'imports', 'contains'),
    max_depth: int = 16,
) -> dict[str, int]:
    graph.get_node(seed)
    distances = {seed: 0}
    queue = deque([seed])
    while queue:
        current = queue.popleft()
        depth = distances[current]
        if depth >= max_depth:
            continue
        for neighbor in graph.neighbors(current, direction='outgoing', kinds=allowed_kinds):
            if neighbor in distances:
                continue
            distances[neighbor] = depth + 1
            queue.append(neighbor)
    return distances


class CounterfactualLocalizer:
    """Zero-parameter localizer using R2.10 edit-gain plus R2.8 topology.

    Paths and graph node identifiers are never neural/scoring features. They are
    carried only so the selected symbol can later be patched and graph-traversed.
    """

    def __init__(
        self,
        proposer: CopyEditProposalNet,
        *,
        distance_weight: float = 0.10,
        risk_weight: float = 0.05,
        coverage_weight: float = 2.0,
        behavior_weight: float = 1.0,
        edit_gain_weight: float = 0.0,
    ) -> None:
        self.proposer = proposer
        self.distance_weight = float(distance_weight)
        self.risk_weight = float(risk_weight)
        self.coverage_weight = float(coverage_weight)
        self.behavior_weight = float(behavior_weight)
        self.edit_gain_weight = float(edit_gain_weight)

    def _edit_gain(
        self,
        symbol: SymbolSlice,
        *,
        language: str,
        probes: Sequence[FailureProbe],
    ) -> float:
        candidates = enumerate_copy_edit_candidates(
            symbol.source,
            language=language,
            target_path=symbol.path,
            candidate_prefix='anon-',
        )
        logits = rank_candidates(
            self.proposer,
            symbol.source,
            language=language,
            target_path=symbol.path,
            candidates=candidates,
            evidence_features=encode_evidence(probes),
        )
        snapshot = RepositorySnapshot({symbol.path: symbol.source})
        no_op_indices: list[int] = []
        changed_indices: list[int] = []
        for index, candidate in enumerate(candidates):
            patched = apply_candidate(snapshot, candidate).files[symbol.path]
            (no_op_indices if patched == symbol.source else changed_indices).append(index)
        if len(no_op_indices) != 1 or not changed_indices:
            raise ValueError('copy-edit family must contain exactly one no-op and at least one changed candidate')
        noop = float(logits[no_op_indices[0]].item())
        changed = max(float(logits[index].item()) for index in changed_indices)
        return changed - noop

    def rank(
        self,
        symbols: Sequence[SymbolSlice],
        *,
        graph: RepoWorldGraph,
        failing_test_node: str,
        language: str,
        probes: Sequence[FailureProbe],
        probes_by_node: Mapping[str, Sequence[FailureProbe]] | None = None,
        coverage: Sequence[TestCoverageObservation] = (),
    ) -> tuple[LocalizationScore, ...]:
        if not symbols:
            return ()
        distances = _distances(graph, failing_test_node)
        rows: list[LocalizationScore] = []
        # Differential behavior is computed from public per-symbol runtime traces.
        # Expected intermediate values are not needed: the majority observation
        # among covered peer implementations is used as the local consensus.
        consensus: list[float] = []
        if probes_by_node:
            width = max((len(items) for items in probes_by_node.values()), default=0)
            for probe_index in range(width):
                values: list[float] = []
                for items in probes_by_node.values():
                    if probe_index < len(items):
                        values.append(round(float(items[probe_index].observed), 8))
                if values:
                    counts: dict[float, int] = {}
                    for value in values:
                        counts[value] = counts.get(value, 0) + 1
                    consensus.append(max(sorted(counts), key=lambda value: counts[value]))

        for symbol in symbols:
            distance = distances.get(symbol.node_id)
            if distance is None:
                continue
            local_probes = probes if probes_by_node is None else probes_by_node.get(symbol.node_id, probes)
            edit_gain = 0.0
            if self.edit_gain_weight != 0.0:
                edit_gain = self._edit_gain(symbol, language=language, probes=local_probes)
            disagreement = 0.0
            if probes_by_node and symbol.node_id in probes_by_node and consensus:
                items = probes_by_node[symbol.node_id]
                comparisons = [
                    float(round(float(items[index].observed), 8) != consensus[index])
                    for index in range(min(len(items), len(consensus)))
                ]
                disagreement = sum(comparisons) / len(comparisons) if comparisons else 0.0
            proximity = 1.0 / (1.0 + float(distance))
            try:
                risk = graph.edit_risk((symbol.node_id,))
            except KeyError:
                continue
            failed_total = sum(int(not item.passed) for item in coverage)
            failed_covered = sum(int((not item.passed) and symbol.node_id in item.covered_nodes) for item in coverage)
            passed_covered = sum(int(item.passed and symbol.node_id in item.covered_nodes) for item in coverage)
            suspiciousness = 0.0
            denom = failed_total * (failed_covered + passed_covered)
            if failed_covered and denom > 0:
                suspiciousness = failed_covered / math.sqrt(float(denom))
            score = (
                self.coverage_weight * suspiciousness
                + self.behavior_weight * disagreement
                + self.edit_gain_weight * edit_gain
                + self.distance_weight * proximity
                - self.risk_weight * risk
            )
            fingerprint = canonical_source_fingerprint(symbol.source, language=language)
            rows.append(
                LocalizationScore(
                    node_id=symbol.node_id,
                    path=symbol.path,
                    score=score,
                    edit_gain=edit_gain,
                    graph_distance=distance,
                    canonical_fingerprint=fingerprint,
                    features=(suspiciousness, disagreement, edit_gain, proximity, risk),
                )
            )
        rows.sort(key=lambda item: (-item.score, item.canonical_fingerprint))
        return tuple(rows)
