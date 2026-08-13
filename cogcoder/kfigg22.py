from __future__ import annotations

from dataclasses import dataclass
import random
import re
from typing import Iterable

from .epistemic_program import ProgramRegistry, compile_program_chunk
from .epistemic_workspace import EpistemicWorkspace
from .knowledge_store import InMemoryKnowledgeStore
from .knowledge_types import EvidenceChunk, KnowledgeDocument
from .retrieval_microcycle import CognitionTimeRetriever, KnowledgeNeed

_CLAIM = re.compile(r'^\s*(.+?)\s+--([^>-]+)-->\s+(.+?)\s*$')


@dataclass(frozen=True)
class KFIGG22PublicCase:
    seed: int
    question: str
    start: str
    hops: int
    documents: tuple[KnowledgeDocument, ...]
    kind: str
    program_name: str | None = None


@dataclass(frozen=True)
class KFIGG22Case:
    seed: int
    question: str
    start: str
    hops: int
    documents: tuple[KnowledgeDocument, ...]
    kind: str
    answer: str | int
    program_name: str | None = None

    def public(self) -> KFIGG22PublicCase:
        return KFIGG22PublicCase(self.seed, self.question, self.start, self.hops, self.documents, self.kind, self.program_name)


@dataclass(frozen=True)
class KFIGG22Result:
    answer: str | int | None
    retrieval_calls: int
    retrieved_chunks: int
    retrieved_chars: int
    chunk_budget: int
    provenance_ok: bool
    version_resolution_errors: int = 0
    programs_executed: int = 0
    trace: tuple[str, ...] = ()


def _token(rng: random.Random, prefix: str, index: int) -> str:
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
    return f'{prefix}{alphabet[rng.randrange(len(alphabet))]}{rng.randrange(1000,9999)}_{index}'


def _apply_program(value: int, instructions: tuple[tuple[str, int], ...]) -> int:
    for op, arg in instructions:
        if op == 'ADD': value += arg
        elif op == 'MUL': value *= arg
        elif op == 'XOR': value ^= arg
        elif op == 'MOD': value %= arg
        else: raise ValueError(op)
    return int(value)


def make_kfigg22_case(
    *,
    seed: int,
    force_program: bool | None = None,
    stale_probability: float = 0.62,
    distractors: int = 28,
    program_probability: float = 0.45,
    force_dependency: bool | None = None,
    dependency_probability: float = 0.35,
) -> KFIGG22Case:
    rng = random.Random(int(seed))
    if not 0.0 <= float(program_probability) <= 1.0:
        raise ValueError('program_probability must be in [0,1]')
    kind_program = (rng.random() < float(program_probability)) if force_program is None else bool(force_program)
    if not 0.0 <= float(dependency_probability) <= 1.0:
        raise ValueError('dependency_probability must be in [0,1]')
    use_dependency = kind_program and ((rng.random() < float(dependency_probability)) if force_dependency is None else bool(force_dependency))
    hops = rng.randint(2, 4)
    nodes = [_token(rng, 'N', i) for i in range(hops + 1)]
    docs: list[KnowledgeDocument] = []

    for index in range(hops):
        subject, current = nodes[index], nodes[index + 1]
        source = f'kfigg22://{seed}/route/{index}'
        if rng.random() < stale_probability:
            stale = _token(rng, 'OLD', index)
            docs.append(KnowledgeDocument(
                f'route-{index}-old', source, f'{subject} --next--> {stale}', version='1', trust_score=.99
            ))
            docs.append(KnowledgeDocument(
                f'route-{index}-new', source, f'{subject} --next--> {current}', version='2', trust_score=.82
            ))
        else:
            docs.append(KnowledgeDocument(
                f'route-{index}', source, f'{subject} --next--> {current}', version='2', trust_score=.92
            ))

    program_name = None
    if kind_program:
        value = rng.randint(1, 30)
        docs.append(KnowledgeDocument(
            'value', f'kfigg22://{seed}/value', f'{nodes[-1]} --value--> {value}', version='3', trust_score=.95
        ))
        program_name = f'prog_{seed}'
        if use_dependency:
            base_name = f'base_{seed}'
            base_instructions = (('ADD', rng.randint(1, 9)), ('MUL', rng.randint(2, 5)))
            combo_instructions = (('XOR', rng.randint(1, 15)), ('MOD', rng.choice((31, 37, 41, 43, 47))))
            base_text = 'PROGRAM ' + base_name + ' :: ' + ' | '.join(f'{op} {arg}' for op, arg in base_instructions)
            combo_text = f'PROGRAM {program_name} :: CALL {base_name} | ' + ' | '.join(f'{op} {arg}' for op, arg in combo_instructions)
            docs.append(KnowledgeDocument('program-base', f'kfigg22://{seed}/program/base', base_text, version='4', trust_score=.96))
            docs.append(KnowledgeDocument('program', f'kfigg22://{seed}/program/main', combo_text, version='4', trust_score=.97))
            answer = _apply_program(_apply_program(value, base_instructions), combo_instructions)
        else:
            instructions = (
                ('ADD', rng.randint(1, 9)),
                ('MUL', rng.randint(2, 5)),
                ('XOR', rng.randint(1, 15)),
                ('MOD', rng.choice((31, 37, 41, 43, 47))),
            )
            text = 'PROGRAM ' + program_name + ' :: ' + ' | '.join(f'{op} {arg}' for op, arg in instructions)
            docs.append(KnowledgeDocument('program', f'kfigg22://{seed}/program', text, version='4', trust_score=.97))
            answer = _apply_program(value, instructions)
        question = (
            f'Follow relation next from {nodes[0]} for exactly {hops} hops. '
            f'Read the integer value at the reached entity, then apply externally documented program {program_name}. '
            'Return the resulting integer.'
        )
        kind = 'documented_program'
    else:
        answer = nodes[-1]
        question = f'Follow relation next from {nodes[0]} for exactly {hops} hops using the current valid facts. Return the reached entity.'
        kind = 'dynamic_chain'

    for index in range(int(distractors)):
        a = _token(rng, 'D', index)
        b = _token(rng, 'X', index)
        relation = rng.choice(('next', 'owner', 'color', 'peer'))
        docs.append(KnowledgeDocument(
            f'd-{index}', f'kfigg22://{seed}/d/{index}', f'{a} --{relation}--> {b}', version=str(rng.randint(1, 4)), trust_score=rng.uniform(.55, .9)
        ))

    rng.shuffle(docs)
    return KFIGG22Case(int(seed), question, nodes[0], hops, tuple(docs), kind, answer, program_name)


def _parse_claim(chunk: EvidenceChunk):
    match = _CLAIM.match(chunk.text.strip())
    if not match:
        return None
    return match.group(1).strip(), match.group(2).strip(), match.group(3).strip()


def _raw_resolve(chunks: Iterable[EvidenceChunk], subject: str, relation: str) -> tuple[str | None, str | None]:
    candidates = []
    for chunk in chunks:
        parsed = _parse_claim(chunk)
        if parsed and parsed[0] == subject and parsed[1] == relation:
            candidates.append((chunk.trust_score, chunk.score, chunk.chunk_id, parsed[2]))
    if not candidates:
        return None, None
    candidates.sort(reverse=True)
    best = candidates[0]
    return best[3], best[2]


def _retriever(public: KFIGG22PublicCase, *, top_k: int, max_calls: int):
    store = InMemoryKnowledgeStore(public.documents, chunk_chars=256)
    return CognitionTimeRetriever(store, max_calls=max_calls, top_k=top_k, max_chars=100_000)


def _force(retriever: CognitionTimeRetriever, query: str):
    return retriever.step(KnowledgeNeed(query, uncertainty=1.0, query_drift=1.0, force=True))


def solve_r21_baseline(public: KFIGG22PublicCase, *, top_k: int = 2, max_calls: int = 6) -> KFIGG22Result:
    retriever = _retriever(public, top_k=top_k, max_calls=max_calls)
    current = public.start
    trace = []
    seen: list[EvidenceChunk] = []
    for _ in range(public.hops):
        decision = _force(retriever, f'{current} next')
        seen.extend(decision.chunks)
        current, cid = _raw_resolve(decision.chunks, current, 'next')
        if current is None:
            return KFIGG22Result(None, retriever.state.calls, len(seen), retriever.state.retrieved_chars, top_k * max_calls, retriever.ledger.verify(), trace=tuple(trace))
        if cid: trace.append(cid)
    if public.kind == 'dynamic_chain':
        return KFIGG22Result(current, retriever.state.calls, len(seen), retriever.state.retrieved_chars, top_k * max_calls, retriever.ledger.verify(), trace=tuple(trace))

    decision = _force(retriever, f'{current} value')
    seen.extend(decision.chunks)
    raw_value, cid = _raw_resolve(decision.chunks, current, 'value')
    if cid: trace.append(cid)
    try:
        answer = int(raw_value) if raw_value is not None else None
    except ValueError:
        answer = None
    # R2.1 has retrieval hooks but no provenance-bound executable knowledge layer.
    return KFIGG22Result(answer, retriever.state.calls, len(seen), retriever.state.retrieved_chars, top_k * max_calls, retriever.ledger.verify(), trace=tuple(trace))


def solve_r22_epistemic(public: KFIGG22PublicCase, *, top_k: int = 2, max_calls: int = 6) -> KFIGG22Result:
    retriever = _retriever(public, top_k=top_k, max_calls=max_calls)
    workspace = EpistemicWorkspace()
    registry = ProgramRegistry(max_steps=64)
    current = public.start
    trace = []
    version_errors = 0
    programs_executed = 0

    for _ in range(public.hops):
        decision = _force(retriever, f'{current} next')
        workspace.ingest_many(decision.chunks)
        belief = workspace.belief(current, 'next')
        if belief.object is None or belief.contested:
            version_errors += 1
            return KFIGG22Result(None, retriever.state.calls, len(workspace.chunks()), retriever.state.retrieved_chars, top_k * max_calls, workspace.verify_provenance() and retriever.ledger.verify(), version_errors, programs_executed, tuple(trace))
        current = belief.object
        trace.extend(belief.evidence_chunk_ids)

    if public.kind == 'dynamic_chain':
        return KFIGG22Result(current, retriever.state.calls, len(workspace.chunks()), retriever.state.retrieved_chars, top_k * max_calls, workspace.verify_provenance() and retriever.ledger.verify(), version_errors, programs_executed, tuple(trace))

    decision = _force(retriever, f'{current} value')
    workspace.ingest_many(decision.chunks)
    value_belief = workspace.belief(current, 'value')
    if value_belief.object is None or value_belief.contested:
        version_errors += 1
        return KFIGG22Result(None, retriever.state.calls, len(workspace.chunks()), retriever.state.retrieved_chars, top_k * max_calls, workspace.verify_provenance() and retriever.ledger.verify(), version_errors, programs_executed, tuple(trace))
    try:
        value = int(value_belief.object)
    except ValueError:
        return KFIGG22Result(None, retriever.state.calls, len(workspace.chunks()), retriever.state.retrieved_chars, top_k * max_calls, workspace.verify_provenance() and retriever.ledger.verify(), version_errors + 1, programs_executed, tuple(trace))
    trace.extend(value_belief.evidence_chunk_ids)

    decision = _force(retriever, f'PROGRAM {public.program_name}')
    workspace.ingest_many(decision.chunks)
    for chunk in decision.chunks:
        if chunk.text.lstrip().startswith('PROGRAM '):
            program = compile_program_chunk(chunk)
            registry.register(program)
    if public.program_name is None or not registry.has(public.program_name):
        return KFIGG22Result(None, retriever.state.calls, len(workspace.chunks()), retriever.state.retrieved_chars, top_k * max_calls, workspace.verify_provenance() and retriever.ledger.verify(), version_errors, programs_executed, tuple(trace))
    dependencies = registry.missing_dependencies(public.program_name)
    for dependency in dependencies:
        dep_decision = _force(retriever, f'PROGRAM {dependency}')
        workspace.ingest_many(dep_decision.chunks)
        for chunk in dep_decision.chunks:
            if chunk.text.lstrip().startswith('PROGRAM '):
                program = compile_program_chunk(chunk)
                registry.register(program)
    if registry.missing_dependencies(public.program_name):
        return KFIGG22Result(None, retriever.state.calls, len(workspace.chunks()), retriever.state.retrieved_chars, top_k * max_calls, workspace.verify_provenance() and retriever.ledger.verify(), version_errors, programs_executed, tuple(trace))
    answer = registry.execute(public.program_name, value)
    programs_executed = 1 + len(dependencies)
    return KFIGG22Result(answer, retriever.state.calls, len(workspace.chunks()), retriever.state.retrieved_chars, top_k * max_calls, workspace.verify_provenance() and retriever.ledger.verify(), version_errors, programs_executed, tuple(trace))


def evaluate_kfigg22(*, seeds: Iterable[int], top_k: int = 2, max_calls: int = 7, stale_probability: float = 0.62, distractors: int = 28, program_probability: float = 0.45, dependency_probability: float = 0.35):
    rows = []
    by_kind = {
        'dynamic_chain': {'cases': 0, 'baseline_solved': 0, 'candidate_solved': 0},
        'documented_program': {'cases': 0, 'baseline_solved': 0, 'candidate_solved': 0},
    }
    baseline_solved = candidate_solved = provenance_failures = version_errors = 0
    for seed in seeds:
        case = make_kfigg22_case(seed=int(seed), stale_probability=stale_probability, distractors=distractors, program_probability=program_probability, dependency_probability=dependency_probability)
        public = case.public()
        baseline = solve_r21_baseline(public, top_k=top_k, max_calls=max_calls)
        candidate = solve_r22_epistemic(public, top_k=top_k, max_calls=max_calls)
        b_ok = baseline.answer == case.answer
        c_ok = candidate.answer == case.answer
        baseline_solved += int(b_ok)
        candidate_solved += int(c_ok)
        provenance_failures += int(not baseline.provenance_ok) + int(not candidate.provenance_ok)
        version_errors += candidate.version_resolution_errors
        bucket = by_kind[case.kind]
        bucket['cases'] += 1
        bucket['baseline_solved'] += int(b_ok)
        bucket['candidate_solved'] += int(c_ok)
        rows.append((case, baseline, candidate))
    n = len(rows)
    for bucket in by_kind.values():
        count = max(1, bucket['cases'])
        bucket['baseline_solve_rate'] = bucket['baseline_solved'] / count
        bucket['candidate_solve_rate'] = bucket['candidate_solved'] / count
    return {
        'cases': n,
        'baseline_solved': baseline_solved,
        'candidate_solved': candidate_solved,
        'baseline_solve_rate': baseline_solved / max(1, n),
        'candidate_solve_rate': candidate_solved / max(1, n),
        'gain_pp': 100.0 * (candidate_solved - baseline_solved) / max(1, n),
        'provenance_failures': provenance_failures,
        'version_resolution_errors': version_errors,
        'chunk_budget': top_k * max_calls,
        'top_k': top_k,
        'max_calls': max_calls,
        'by_kind': by_kind,
        'rows': rows,
    }
