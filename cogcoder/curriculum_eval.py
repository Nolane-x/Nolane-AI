from __future__ import annotations

import hashlib
import json
from typing import Iterable

from .skill_memory import SkillArtifact, SkillRegistry
from .skill_synthesis import BoundedSkillSynthesizer
from .curriculum_cases import KFIGG23PublicCase, KFIGG23SolverResult, TeachingBatch, make_kfigg23_case


class _ReplayMemory:
    def __init__(self):
        self.rows: dict[tuple[str, str], dict[int, int]] = {}
        self.current: dict[str, str] = {}
        self.observed = 0

    def learn(self, teaching: TeachingBatch) -> None:
        self.rows[(teaching.skill_name, teaching.version)] = {
            int(d.input_value): int(d.output_value) for d in teaching.demonstrations
        }
        self.current[teaching.skill_name] = teaching.version
        self.observed += len(teaching.demonstrations)

    def apply(self, name: str, value: int) -> int | None:
        version = self.current.get(name)
        return None if version is None else self.rows[(name, version)].get(int(value))

    def compose(self, names: tuple[str, ...], value: int) -> int | None:
        current: int | None = int(value)
        for name in names:
            if current is None:
                return None
            current = self.apply(name, current)
        return current


def run_replay_baseline(public: KFIGG23PublicCase) -> KFIGG23SolverResult:
    memory = _ReplayMemory()
    answers: dict[str, int | None] = {}
    for item in public.initial_teachings:
        memory.learn(item)
    q = public.queries[0]
    answers[q.query_id] = memory.apply(q.skill_names[0], q.input_value)
    for item in public.intervening_teachings:
        memory.learn(item)
    q = public.queries[1]
    answers[q.query_id] = memory.apply(q.skill_names[0], q.input_value)
    memory.learn(public.revision_teaching)
    q = public.queries[2]
    answers[q.query_id] = memory.apply(q.skill_names[0], q.input_value)
    q = public.queries[3]
    answers[q.query_id] = memory.compose(q.skill_names, q.input_value)
    return KFIGG23SolverResult(answers, memory.observed, 0, 0)


def _digest(teaching: TeachingBatch) -> str:
    payload = {
        'name': teaching.skill_name,
        'version': teaching.version,
        'source_uri': teaching.source_uri,
        'demonstrations': [(int(d.input_value), int(d.output_value)) for d in teaching.demonstrations],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _learn(registry: SkillRegistry, inducer: BoundedSkillSynthesizer, teaching: TeachingBatch) -> tuple[bool, int]:
    result = inducer.synthesize(teaching.skill_name, teaching.version, teaching.demonstrations)
    if not result.resolved or result.program is None:
        return False, 0
    provenance = _digest(teaching)
    artifact = SkillArtifact(
        teaching.skill_name,
        teaching.version,
        result.program,
        tuple((int(d.input_value), int(d.output_value)) for d in teaching.demonstrations),
        provenance,
        teaching.source_uri,
        1.0,
    )
    registry.install(artifact)
    return True, int(artifact.provenance_sha256 != provenance or artifact.source_uri != teaching.source_uri)


def run_continual_candidate(public: KFIGG23PublicCase, *, max_depth: int = 3, max_candidates: int = 100_000) -> KFIGG23SolverResult:
    inducer = BoundedSkillSynthesizer(max_depth=max_depth, max_candidates=max_candidates)
    registry = SkillRegistry()
    answers: dict[str, int | None] = {}
    observed = integrity_failures = synthesis_failures = 0

    def learn(teaching: TeachingBatch) -> None:
        nonlocal observed, integrity_failures, synthesis_failures
        observed += len(teaching.demonstrations)
        ok, integrity = _learn(registry, inducer, teaching)
        integrity_failures += integrity
        synthesis_failures += int(not ok)

    for item in public.initial_teachings:
        learn(item)
    q = public.queries[0]
    answers[q.query_id] = registry.execute(q.skill_names[0], q.input_value) if registry.has(q.skill_names[0]) else None
    for item in public.intervening_teachings:
        learn(item)
    q = public.queries[1]
    answers[q.query_id] = registry.execute(q.skill_names[0], q.input_value) if registry.has(q.skill_names[0]) else None
    learn(public.revision_teaching)
    q = public.queries[2]
    answers[q.query_id] = registry.execute(q.skill_names[0], q.input_value) if registry.has(q.skill_names[0]) else None
    q = public.queries[3]
    current: int | None = int(q.input_value)
    for name in q.skill_names:
        if current is None or not registry.has(name):
            current = None
            break
        current = registry.execute(name, current)
    answers[q.query_id] = current
    return KFIGG23SolverResult(answers, observed, integrity_failures, synthesis_failures)


def measure_kfigg23(
    *,
    seeds: Iterable[int],
    seen_probability: float = 0.35,
    composition_seen_probability: float = 0.25,
    max_depth: int = 3,
    max_candidates: int = 100_000,
    demonstrations_per_skill: int = 5,
):
    cases = baseline_solved = candidate_solved = integrity_failures = synthesis_failures = 0
    by_kind = {k: {'queries': 0, 'baseline_solved': 0, 'candidate_solved': 0} for k in ('induction', 'retention', 'revision', 'composition')}
    for seed in seeds:
        case = make_kfigg23_case(
            seed=int(seed),
            seen_probability=seen_probability,
            composition_seen_probability=composition_seen_probability,
            demonstrations_per_skill=demonstrations_per_skill,
        )
        baseline = run_replay_baseline(case.public)
        candidate = run_continual_candidate(case.public, max_depth=max_depth, max_candidates=max_candidates)
        expected = dict(case.expected_answers)
        cases += 1
        integrity_failures += candidate.integrity_failures
        synthesis_failures += candidate.synthesis_failures
        for q in case.public.queries:
            b_ok = baseline.answers.get(q.query_id) == expected[q.query_id]
            c_ok = candidate.answers.get(q.query_id) == expected[q.query_id]
            baseline_solved += int(b_ok)
            candidate_solved += int(c_ok)
            bucket = by_kind[q.kind]
            bucket['queries'] += 1
            bucket['baseline_solved'] += int(b_ok)
            bucket['candidate_solved'] += int(c_ok)
    total = max(1, cases * 4)
    for bucket in by_kind.values():
        n = max(1, bucket['queries'])
        bucket['baseline_solve_rate'] = bucket['baseline_solved'] / n
        bucket['candidate_solve_rate'] = bucket['candidate_solved'] / n
    return {
        'cases': cases,
        'queries': cases * 4,
        'baseline_solved': baseline_solved,
        'candidate_solved': candidate_solved,
        'baseline_solve_rate': baseline_solved / total,
        'candidate_solve_rate': candidate_solved / total,
        'gain_pp': 100.0 * (candidate_solved - baseline_solved) / total,
        'induction_solve_rate': by_kind['induction']['candidate_solve_rate'],
        'retention_solve_rate': by_kind['retention']['candidate_solve_rate'],
        'revision_solve_rate': by_kind['revision']['candidate_solve_rate'],
        'composition_solve_rate': by_kind['composition']['candidate_solve_rate'],
        'integrity_failures': integrity_failures,
        'synthesis_failures': synthesis_failures,
        'by_kind': by_kind,
        'protocol': {
            'seen_probability': seen_probability,
            'composition_seen_probability': composition_seen_probability,
            'max_depth': max_depth,
            'max_candidates': max_candidates,
            'demonstrations_per_skill': demonstrations_per_skill,
        },
    }
