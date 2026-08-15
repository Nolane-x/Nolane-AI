from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from .r28_repo_world import RepoWorldGraph
from .r29_patch_model import PatchCandidate, RepositorySnapshot, apply_candidate, patch_fingerprint


@dataclass(frozen=True, slots=True)
class VerificationResult:
    targeted_tests_passed: int
    targeted_tests_total: int
    full_tests_passed: bool | None
    verifier_score: float
    success: bool
    observations: tuple[str, ...] = ()
    regression_detected: bool = False

    def __post_init__(self) -> None:
        if self.targeted_tests_total < 0 or self.targeted_tests_passed < 0:
            raise ValueError('test counts must be non-negative')
        if self.targeted_tests_passed > self.targeted_tests_total:
            raise ValueError('passed targeted tests cannot exceed total')
        if not 0.0 <= float(self.verifier_score) <= 1.0:
            raise ValueError('verifier_score must be in [0, 1]')
        if self.success and self.full_tests_passed is False:
            raise ValueError('a regressing patch cannot be marked successful')

    @property
    def targeted_fraction(self) -> float:
        if self.targeted_tests_total == 0:
            return 0.0
        return self.targeted_tests_passed / self.targeted_tests_total


@dataclass(frozen=True, slots=True)
class PatchSearchStep:
    evaluation_index: int
    candidate_id: str
    fingerprint: str
    priority: float
    result: VerificationResult


@dataclass(frozen=True, slots=True)
class PatchSearchOutcome:
    success: bool
    candidate: PatchCandidate | None
    best_result: VerificationResult
    trace: tuple[PatchSearchStep, ...]
    evaluations: int
    duplicate_candidates: int
    budget_exhausted: bool


class PatchSearchMemory:
    def __init__(self) -> None:
        self._results: dict[str, VerificationResult] = {}
        self._seen: set[str] = set()
        self.duplicate_candidates = 0

    def register(self, candidate: PatchCandidate) -> bool:
        fingerprint = patch_fingerprint(candidate)
        if fingerprint in self._seen:
            self.duplicate_candidates += 1
            return False
        self._seen.add(fingerprint)
        return True

    def record(self, candidate: PatchCandidate, result: VerificationResult) -> None:
        self._results[patch_fingerprint(candidate)] = result

    def result_for(self, candidate: PatchCandidate) -> VerificationResult | None:
        return self._results.get(patch_fingerprint(candidate))


PatchEvaluator = Callable[[RepositorySnapshot, PatchCandidate], VerificationResult]
PatchRefiner = Callable[[PatchCandidate, VerificationResult], Iterable[PatchCandidate]]


class VerifierGuidedPatchSearch:
    """Deterministic best-first patch search under a hard evaluator budget."""

    def __init__(
        self,
        *,
        budget: int = 8,
        verifier_weight: float = 1.5,
        targeted_weight: float = 0.8,
        full_test_weight: float = 0.4,
        risk_weight: float = 0.8,
        size_weight: float = 0.02,
        regression_penalty: float = 0.8,
    ) -> None:
        if budget < 1:
            raise ValueError('budget must be positive')
        self.budget = int(budget)
        self.verifier_weight = float(verifier_weight)
        self.targeted_weight = float(targeted_weight)
        self.full_test_weight = float(full_test_weight)
        self.risk_weight = float(risk_weight)
        self.size_weight = float(size_weight)
        self.regression_penalty = float(regression_penalty)

    def _patch_size(self, candidate: PatchCandidate) -> int:
        size = 0
        for edit in candidate.edits:
            removed = max(0, edit.end_line - edit.start_line)
            added = len(edit.replacement.splitlines())
            size += max(removed, added, 1)
        return size

    def _risk(self, candidate: PatchCandidate, graph: RepoWorldGraph | None) -> float:
        if graph is None or not candidate.targeted_nodes:
            return 0.0
        known = {node.node_id for node in graph.nodes}
        targets = candidate.targeted_nodes.intersection(known)
        if not targets:
            return 0.0
        return graph.edit_risk(targets)

    def _priority(
        self,
        candidate: PatchCandidate,
        *,
        graph: RepoWorldGraph | None,
        parent_result: VerificationResult | None,
    ) -> float:
        priority = float(candidate.proposal_score)
        priority -= self.risk_weight * self._risk(candidate, graph)
        priority -= self.size_weight * self._patch_size(candidate)
        if parent_result is not None:
            priority += self.verifier_weight * float(parent_result.verifier_score)
            priority += self.targeted_weight * parent_result.targeted_fraction
            if parent_result.full_tests_passed is True:
                priority += self.full_test_weight
            if parent_result.regression_detected or parent_result.full_tests_passed is False:
                priority -= self.regression_penalty
        return priority

    def search(
        self,
        snapshot: RepositorySnapshot,
        initial_candidates: Sequence[PatchCandidate],
        evaluator: PatchEvaluator,
        *,
        refine: PatchRefiner | None = None,
        graph: RepoWorldGraph | None = None,
    ) -> PatchSearchOutcome:
        if not initial_candidates:
            raise ValueError('at least one initial patch candidate is required')

        memory = PatchSearchMemory()
        queue: list[tuple[float, str, PatchCandidate, VerificationResult | None]] = []

        def enqueue(candidate: PatchCandidate, parent_result: VerificationResult | None) -> None:
            if not memory.register(candidate):
                return
            priority = self._priority(candidate, graph=graph, parent_result=parent_result)
            heapq.heappush(
                queue,
                (-priority, patch_fingerprint(candidate), candidate, parent_result),
            )

        for candidate in initial_candidates:
            enqueue(candidate, None)

        trace: list[PatchSearchStep] = []
        best_candidate: PatchCandidate | None = None
        best_result: VerificationResult | None = None
        best_quality: tuple[float, float, int, str] | None = None
        evaluations = 0

        while queue and evaluations < self.budget:
            neg_priority, fingerprint, candidate, _parent_result = heapq.heappop(queue)
            priority = -neg_priority
            patched = apply_candidate(snapshot, candidate)
            result = evaluator(patched, candidate)
            if not isinstance(result, VerificationResult):
                raise TypeError('evaluator must return VerificationResult')
            evaluations += 1
            memory.record(candidate, result)
            trace.append(PatchSearchStep(evaluations, candidate.candidate_id, fingerprint, priority, result))

            quality = (
                float(result.verifier_score),
                result.targeted_fraction,
                int(result.full_tests_passed is True),
                fingerprint,
            )
            if best_quality is None or quality > best_quality:
                best_quality = quality
                best_candidate = candidate
                best_result = result

            if result.success:
                return PatchSearchOutcome(
                    success=True,
                    candidate=candidate,
                    best_result=result,
                    trace=tuple(trace),
                    evaluations=evaluations,
                    duplicate_candidates=memory.duplicate_candidates,
                    budget_exhausted=False,
                )

            if refine is not None:
                for child in refine(candidate, result):
                    enqueue(child, result)

        assert best_result is not None
        return PatchSearchOutcome(
            success=False,
            candidate=best_candidate,
            best_result=best_result,
            trace=tuple(trace),
            evaluations=evaluations,
            duplicate_candidates=memory.duplicate_candidates,
            budget_exhausted=bool(queue) and evaluations >= self.budget,
        )
