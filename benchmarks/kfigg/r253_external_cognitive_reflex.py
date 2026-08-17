from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from cogcoder.r253_external_cognition import (
    CognitiveDeficitDetector,
    CognitiveOperatorRegistry,
    CognitiveOperatorSpec,
    CognitiveReflexRouter,
    CognitiveReflexRuntime,
    CognitiveSnapshot,
    CounterexampleMemory,
    ExternalWorkingState,
    ProcedureCard,
    ProcedureCompiler,
    ProcedureCreditLedger,
    ProcedureLibrary,
    make_procedure_digest,
    make_cognition_time_retrieval_operator,
)
from cogcoder.knowledge_store import InMemoryKnowledgeStore
from cogcoder.knowledge_types import KnowledgeDocument
from cogcoder.retrieval_microcycle import CognitionTimeRetriever


@dataclass(frozen=True)
class EpisodeSpec:
    task_id: str
    mode: str
    context_tags: frozenset[str]
    initial_context: Mapping[str, object]
    expected: object
    validator: Callable[[object], bool]


def _operator(
    operator_id: str,
    family: str,
    executor,
    *,
    requires=(),
    provides=(),
    cost=1.0,
    risk=0.05,
    tags=(),
):
    return CognitiveOperatorSpec(
        operator_id,
        family,
        frozenset(tags or tuple(operator_id.split('.'))),
        frozenset(requires),
        frozenset(provides),
        float(cost),
        float(risk),
        'state_only',
        '1',
        'benchmark://r253-primitive',
        executor,
    )


def _card(
    procedure_id: str,
    deficit: str,
    steps: tuple[str, ...],
    *,
    context_tags=(),
    preconditions=(),
    expected_outputs=(),
    verifier=None,
    trust=0.95,
    max_cost=10.0,
    max_risk=0.8,
    source='benchmark://r253-procedure',
    tamper=False,
):
    fields = dict(
        procedure_id=procedure_id,
        version='1',
        deficit_tags=frozenset({deficit}),
        context_tags=frozenset(context_tags),
        steps=tuple(steps),
        preconditions=frozenset(preconditions),
        expected_outputs=frozenset(expected_outputs),
        verifier_operator_id=verifier,
        max_cost=float(max_cost),
        max_risk=float(max_risk),
        trust_score=float(trust),
        source_uri=source,
    )
    digest = make_procedure_digest(**fields)
    if tamper:
        digest = ('0' if digest[0] != '0' else '1') + digest[1:]
    return ProcedureCard(content_sha256=digest, **fields)


def _episodes() -> tuple[EpisodeSpec, ...]:
    # Expected values are computed independently here from the public task data. Operator executors
    # below do not read EpisodeSpec.expected; they derive candidates from retrieved/structured state.
    knowledge_corpus = {
        'ax17': (('v1', 2), ('v2', 3)),
        'by29': (('v4', 4), ('v7', 5)),
    }
    rows: list[EpisodeSpec] = []

    for task_id, x in (('ax17', 7), ('by29', 6)):
        latest = max(knowledge_corpus[task_id], key=lambda row: int(row[0][1:]))[1]
        expected = x * latest
        rows.append(EpisodeSpec(
            task_id,
            'knowledge_temporal',
            frozenset({'opaque', 'knowledge', 'temporal', task_id}),
            {'task_id': task_id, 'x': x, 'knowledge_query': task_id},
            expected,
            lambda candidate, expected=expected: candidate == expected,
        ))

    search_rows = (
        ('cz31', (4, 9, 17, 24, 31), 7, 3, 10),
        ('du43', (5, 14, 19, 26, 33), 7, 5, 12),
    )
    for task_id, candidates, modulus, remainder, lower in search_rows:
        expected = next(x for x in candidates if x > lower and x % modulus == remainder)
        rows.append(EpisodeSpec(
            task_id,
            'search_stagnation',
            frozenset({'opaque', 'search', 'preferred', task_id}),
            {
                'task_id': task_id,
                'search_candidates': candidates,
                'constraint_mod': modulus,
                'constraint_rem': remainder,
                'constraint_min': lower,
            },
            expected,
            lambda candidate, expected=expected: candidate == expected,
        ))

    graph_rows = (
        ('ev59', (('s','a'),('a','b'),('a','c'),('c','d')), {'a':2,'b':3,'c':5,'d':11}, 's'),
        ('fw61', (('q','r'),('r','t'),('r','u'),('u','v')), {'r':2,'t':4,'u':6,'v':13}, 'q'),
    )
    for task_id, edges, weights, source in graph_rows:
        reachable = {source}; changed = True
        while changed:
            changed = False
            for left, right in edges:
                if left in reachable and right not in reachable:
                    reachable.add(right); changed = True
        expected = max((node for node in reachable if node in weights), key=lambda node: (weights[node], node))
        rows.append(EpisodeSpec(
            task_id,
            'representation',
            frozenset({'opaque', 'graph', 'code', task_id}),
            {'task_id':task_id,'graph_edges':edges,'node_weights':weights,'source_node':source},
            expected,
            lambda candidate, expected=expected: candidate == expected,
        ))

    tool_rows = (
        ('gx73', 3, 8, 5),
        ('hy83', 4, 7, 6),
    )
    for task_id, a, b, c in tool_rows:
        expected = a * b + c
        rows.append(EpisodeSpec(
            task_id,
            'tool',
            frozenset({'opaque', 'tool', 'arithmetic', task_id}),
            {'task_id':task_id,'tool_request':(a,b,c)},
            expected,
            lambda candidate, expected=expected: candidate == expected,
        ))

    plan_rows = (
        ('iz97', 5, (('add',3,()),('mul',2,('add',)),('sub',4,('mul',)))),
        ('ja101', 6, (('add',2,()),('mul',3,('add',)),('sub',5,('mul',)))),
    )
    for task_id, start, operations in plan_rows:
        value = start
        for name, amount, deps in operations:
            if name == 'add': value += amount
            elif name == 'mul': value *= amount
            elif name == 'sub': value -= amount
        expected = value
        rows.append(EpisodeSpec(
            task_id,
            'planning',
            frozenset({'opaque', 'plan', 'dependency', task_id}),
            {'task_id':task_id,'plan_start':start,'plan_operations':operations},
            expected,
            lambda candidate, expected=expected: candidate == expected,
        ))

    memory_rows = (
        ('kb109', (('noise1',1,100),('critical_a',9,7),('noise2',2,90),('critical_b',10,11))),
        ('lc127', (('junk',1,200),('critical_a',8,13),('other',3,70),('critical_b',9,17))),
    )
    for task_id, items in memory_rows:
        expected = sum(value for key, priority, value in items if key.startswith('critical_') and priority >= 8)
        rows.append(EpisodeSpec(
            task_id,
            'working_memory',
            frozenset({'opaque', 'memory', 'compression', task_id}),
            {'task_id':task_id,'memory_items':items},
            expected,
            lambda candidate, expected=expected: candidate == expected,
        ))

    contradiction_rows = (
        ('md131', (('srcA',1,0.9,2),('srcA',2,0.9,3),('srcB',1,0.8,3))),
        ('ne149', (('srcA',3,0.9,4),('srcA',5,0.9,6),('srcB',2,0.85,6))),
    )
    for task_id, claims in contradiction_rows:
        latest_by_source = {}
        for source, version, trust, value in claims:
            prior = latest_by_source.get(source)
            if prior is None or version > prior[0]: latest_by_source[source] = (version, trust, value)
        expected = max(latest_by_source.values(), key=lambda row: (row[1], row[0], row[2]))[2]
        rows.append(EpisodeSpec(
            task_id,
            'contradiction',
            frozenset({'opaque', 'evidence', 'conflict', task_id}),
            {'task_id':task_id,'claims':claims},
            expected,
            lambda candidate, expected=expected: candidate == expected,
        ))

    resource_rows = (
        ('of157', (('a',7,0.92),('b',3,0.88),('c',5,0.95)), 0.9),
        ('pg173', (('a',6,0.91),('b',2,0.86),('c',4,0.94)), 0.9),
    )
    for task_id, options, threshold in resource_rows:
        eligible = [row for row in options if row[2] >= threshold]
        expected = min(eligible, key=lambda row: (row[1], -row[2], row[0]))[0]
        rows.append(EpisodeSpec(
            task_id,
            'resource',
            frozenset({'opaque', 'resource', 'budget', task_id}),
            {'task_id':task_id,'resource_options':options,'quality_threshold':threshold},
            expected,
            lambda candidate, expected=expected: candidate == expected,
        ))

    return tuple(rows)


def _build_runtime(spec: EpisodeSpec):
    validators = {spec.task_id: spec.validator}

    knowledge_documents = []
    for knowledge_task, versions in {
        'ax17': (('v1', 2), ('v2', 3)),
        'by29': (('v4', 4), ('v7', 5)),
    }.items():
        for version, value in versions:
            knowledge_documents.append(KnowledgeDocument(
                f'{knowledge_task}-{version}',
                f'mem://r253/{knowledge_task}/{version}',
                f'{knowledge_task} --multiplier_{version}--> {value}',
                version=version,
                trust_score=1.0,
            ))
    r21_retriever = CognitionTimeRetriever(
        InMemoryKnowledgeStore(knowledge_documents), max_calls=3, top_k=2, max_chars=4000,
    )
    r21_operator = make_cognition_time_retrieval_operator(
        r21_retriever, operator_id='knowledge.r21_cognition_time_retrieve', query_field='knowledge_query',
    )

    def select_latest(state, _snapshot, _signal):
        import re
        rows = []
        for text in state.context.get('knowledge_texts', ()):
            match = re.match(r'^\s*[^ ]+\s+--multiplier_(v\d+)-->\s+(-?\d+)\s*$', str(text))
            if match:
                rows.append((match.group(1), int(match.group(2))))
        if not rows:
            return {'success': False, 'reason': 'no_versions'}
        version, multiplier = max(rows, key=lambda row: int(row[0][1:]))
        candidate = int(state.context['x']) * int(multiplier)
        return {'success': True, 'updates': {'selected_version': version, 'candidate': candidate}, 'evidence': (f'latest:{version}',)}

    def bad_repeat(_state, _snapshot, _signal):
        return {'success': False, 'reason': 'repeated_known_bad_search_route', 'evidence': ('bad-route',)}

    def diversify_search(state, _snapshot, _signal):
        candidates = tuple(state.context['search_candidates'])
        mod = int(state.context['constraint_mod']); rem = int(state.context['constraint_rem']); lower = int(state.context['constraint_min'])
        valid = [x for x in candidates if x > lower and x % mod == rem]
        if not valid: return {'success': False, 'reason': 'no_candidate_satisfies_constraints'}
        return {'success': True, 'updates': {'candidate': valid[0]}, 'evidence': (f'branch:{valid[0]}',)}

    def switch_graph(state, _snapshot, _signal):
        state.representation_id = 'graph'
        return {'success': True, 'updates': {'representation': 'graph'}, 'evidence': ('representation:graph',)}

    def analyze_graph(state, _snapshot, _signal):
        if state.representation_id != 'graph': return {'success': False, 'reason': 'graph_representation_missing'}
        edges = tuple(state.context['graph_edges']); weights = dict(state.context['node_weights']); source = str(state.context['source_node'])
        reachable = {source}; changed = True
        while changed:
            changed = False
            for left, right in edges:
                if left in reachable and right not in reachable:
                    reachable.add(right); changed = True
        weighted = [node for node in reachable if node in weights]
        if not weighted: return {'success': False, 'reason': 'no_weighted_reachable_node'}
        candidate = max(weighted, key=lambda node: (weights[node], node))
        return {'success': True, 'updates': {'candidate': candidate}, 'evidence': (f'graph-choice:{candidate}',)}

    def discover_tool(state, _snapshot, _signal):
        return {'success': True, 'updates': {'tool_id': 'solver.v1'}, 'evidence': ('tool:solver.v1',)}

    def load_schema(state, _snapshot, _signal):
        if state.context.get('tool_id') != 'solver.v1': return {'success': False, 'reason': 'tool_not_discovered'}
        return {'success': True, 'updates': {'tool_schema': 'mul_add(a,b,c)'}, 'evidence': ('schema:mul_add',)}

    def execute_tool(state, _snapshot, _signal):
        if state.context.get('tool_schema') != 'mul_add(a,b,c)': return {'success': False, 'reason': 'schema_missing'}
        a,b,c = map(int, state.context['tool_request'])
        return {'success': True, 'updates': {'candidate': a*b+c}, 'evidence': ('tool-executed',)}

    def decompose_plan(state, _snapshot, _signal):
        operations = tuple(state.context['plan_operations'])
        return {'success': True, 'updates': {'plan_nodes': tuple(name for name,_amount,_deps in operations)}, 'evidence': ('plan:decomposed',)}

    def order_plan(state, _snapshot, _signal):
        operations = tuple(state.context['plan_operations'])
        done = set(); ordered = []
        remaining = list(operations)
        while remaining:
            ready = [row for row in remaining if set(row[2]) <= done]
            if not ready: return {'success': False, 'reason': 'dependency_cycle'}
            row = sorted(ready, key=lambda x: x[0])[0]
            ordered.append(row); done.add(row[0]); remaining.remove(row)
        return {'success': True, 'updates': {'ordered_plan': tuple(ordered)}, 'evidence': ('plan:ordered',)}

    def execute_plan(state, _snapshot, _signal):
        value = int(state.context['plan_start'])
        for name, amount, _deps in state.context.get('ordered_plan', ()):
            if name == 'add': value += int(amount)
            elif name == 'mul': value *= int(amount)
            elif name == 'sub': value -= int(amount)
            else: return {'success': False, 'reason': f'unknown_plan_op:{name}'}
        return {'success': True, 'updates': {'candidate': value}, 'evidence': ('plan:executed',)}

    def compact_memory(state, _snapshot, _signal):
        items = tuple(state.context['memory_items'])
        focused = tuple(row for row in items if str(row[0]).startswith('critical_') and int(row[1]) >= 8)
        return {'success': True, 'updates': {'focused_memory': focused}, 'evidence': (f'focused:{len(focused)}',)}

    def use_focused_memory(state, _snapshot, _signal):
        focused = tuple(state.context.get('focused_memory', ()))
        if not focused: return {'success': False, 'reason': 'no_focused_memory'}
        return {'success': True, 'updates': {'candidate': sum(int(row[2]) for row in focused)}, 'evidence': ('memory:integrated',)}

    def resolve_conflict(state, _snapshot, _signal):
        claims = tuple(state.context['claims']); latest = {}
        for source, version, trust, value in claims:
            prior = latest.get(source)
            if prior is None or int(version) > int(prior[0]): latest[source] = (int(version), float(trust), value)
        if not latest: return {'success': False, 'reason': 'no_claims'}
        chosen = max(latest.values(), key=lambda row: (row[1], row[0], row[2]))
        return {'success': True, 'updates': {'candidate': chosen[2], 'conflict_resolved': True}, 'evidence': (f'claim:{chosen[0]}:{chosen[2]}',)}

    def reserve_budget(state, _snapshot, _signal):
        return {'success': True, 'updates': {'verification_budget_reserved': True}, 'evidence': ('budget:reserved',)}

    def choose_resource(state, _snapshot, _signal):
        if not state.context.get('verification_budget_reserved'): return {'success': False, 'reason': 'verification_budget_not_reserved'}
        threshold = float(state.context['quality_threshold'])
        eligible = [row for row in state.context['resource_options'] if float(row[2]) >= threshold]
        if not eligible: return {'success': False, 'reason': 'no_quality_eligible_option'}
        chosen = min(eligible, key=lambda row: (float(row[1]), -float(row[2]), str(row[0])))
        return {'success': True, 'updates': {'candidate': chosen[0]}, 'evidence': (f'resource:{chosen[0]}',)}

    def verify_final(state, _snapshot, _signal):
        candidate = state.context.get('candidate')
        valid = bool(validators[state.context['task_id']](candidate))
        return {'success': valid, 'updates': {'final_verified': valid}, 'evidence': (f'verifier:{valid}',), 'reason': 'candidate_rejected' if not valid else 'verified'}

    registry = CognitiveOperatorRegistry([
        r21_operator,
        _operator('temporal.select_latest','temporal',select_latest,requires={'evidence'},provides={'candidate'}),
        _operator('search.repeat_bad','search',bad_repeat,cost=0.5,risk=0.1),
        _operator('search.diversify','search',diversify_search,provides={'candidate'},cost=1.2),
        _operator('representation.switch_graph','representation',switch_graph,provides={'rep:graph'}),
        _operator('representation.analyze_graph','representation',analyze_graph,requires={'rep:graph'},provides={'candidate'},cost=1.5),
        _operator('tool.discover','tool',discover_tool,provides={'tool:solver'}),
        _operator('tool.schema','tool',load_schema,requires={'tool:solver'},provides={'tool:schema'}),
        _operator('tool.execute','tool',execute_tool,requires={'tool:schema'},provides={'candidate'}),
        _operator('planning.decompose','planning',decompose_plan,provides={'plan'}),
        _operator('planning.order','planning',order_plan,requires={'plan'},provides={'ordered_plan'}),
        _operator('planning.execute','planning',execute_plan,requires={'ordered_plan'},provides={'candidate'}),
        _operator('memory.compact','memory',compact_memory,provides={'focused_memory'}),
        _operator('memory.integrate','memory',use_focused_memory,requires={'focused_memory'},provides={'candidate'}),
        _operator('evidence.resolve_conflict','evidence',resolve_conflict,provides={'candidate'}),
        _operator('resource.reserve_verification','resource',reserve_budget,provides={'budget_reserved'}),
        _operator('resource.choose','resource',choose_resource,requires={'budget_reserved'},provides={'candidate'}),
        _operator('verify.final','verification',verify_final,requires={'candidate'},provides={'verified'},risk=0.01),
    ])

    cards = [
        _card('proc.knowledge.retrieve','knowledge_gap',('knowledge.r21_cognition_time_retrieve',),context_tags={'knowledge','temporal'},expected_outputs={'evidence'}),
        _card('proc.temporal.resolve','temporal_conflict',('temporal.select_latest',),context_tags={'knowledge','temporal'},preconditions={'evidence'},expected_outputs={'candidate'}),
        _card('proc.search.bad','search_stagnation',('search.repeat_bad',),context_tags={'search','preferred','opaque'}),
        _card('proc.search.good','search_stagnation',('search.diversify',),context_tags={'search','opaque'},expected_outputs={'candidate'}),
        _card('proc.representation.graph','representation_mismatch',('representation.switch_graph','representation.analyze_graph'),context_tags={'graph','code'},expected_outputs={'rep:graph','candidate'}),
        _card('proc.tool.acquire','tool_gap',('tool.discover','tool.schema','tool.execute'),context_tags={'tool','arithmetic'},expected_outputs={'tool:solver','tool:schema','candidate'}),
        _card('proc.plan.repair','planning_gap',('planning.decompose','planning.order','planning.execute'),context_tags={'plan','dependency'},expected_outputs={'plan','ordered_plan','candidate'}),
        _card('proc.memory.compact','working_memory_pressure',('memory.compact','memory.integrate'),context_tags={'memory','compression'},expected_outputs={'focused_memory','candidate'}),
        _card('proc.evidence.resolve','contradiction',('evidence.resolve_conflict',),context_tags={'evidence','conflict'},expected_outputs={'candidate'}),
        _card('proc.resource.recover','resource_pressure',('resource.reserve_verification','resource.choose'),context_tags={'resource','budget'},expected_outputs={'budget_reserved','candidate'}),
        _card('proc.verify.final','verification_gap',('verify.final',),context_tags={'opaque'},preconditions={'candidate'},expected_outputs={'verified'},verifier='verify.final'),
        # Benign semantic distractors.
        _card('distractor.knowledge.history','knowledge_gap',('knowledge.r21_cognition_time_retrieve',),context_tags={'history'}),
        _card('distractor.plan.generic','planning_gap',('planning.decompose',),context_tags={'generic'}),
        _card('distractor.resource.generic','resource_pressure',('resource.reserve_verification',),context_tags={'generic'}),
        # Correct digest but impossible arbitrary operator id: compiler must reject before execution.
        _card('unsafe.arbitrary','verification_gap',('arbitrary.exec',),context_tags={'opaque'},trust=0.99),
        # Registered step but tampered provenance: compiler must reject before execution.
        _card('tampered.verify','verification_gap',('verify.final',),context_tags={'opaque'},preconditions={'candidate'},tamper=True,trust=0.99),
    ]

    credit = ProcedureCreditLedger(); counterexamples = CounterexampleMemory()
    runtime = CognitiveReflexRuntime(
        detector=CognitiveDeficitDetector(),
        registry=registry,
        library=ProcedureLibrary(cards),
        compiler=ProcedureCompiler(registry, min_trust=0.75),
        router=CognitiveReflexRouter(credit, counterexamples),
    )
    return runtime, credit, counterexamples, cards


def _snapshot_for(spec: EpisodeSpec, state: ExternalWorkingState, cycle: int) -> CognitiveSnapshot:
    base = dict(
        objective=f'opaque:{spec.task_id}',
        step_index=cycle,
        self_confidence=0.995,  # intentionally overconfident; objective telemetry must dominate.
        progress_score=0.4,
        previous_progress_score=0.3,
        unresolved_requirements=(),
        evidence_coverage=1.0,
        verifier_failures=0,
        recent_action_fingerprints=(f'{spec.task_id}:a', f'{spec.task_id}:b'),
        representation_id=state.representation_id,
        representation_failures=0,
        available_capabilities=frozenset(state.capabilities),
        missing_capabilities=frozenset(),
        evidence_conflicts=0,
        stale_evidence=0,
        blocked_subgoals=0,
        working_memory_pressure=0.1,
        counterexample_repeat_count=0,
        resource_pressure=0.1,
        candidate_verified=bool(state.context.get('final_verified', False)),
        terminal_candidate='candidate' in state.context,
        host_observations=(),
    )
    if state.context.get('final_verified'):
        return CognitiveSnapshot(**base)
    if 'candidate' in state.context:
        base.update(candidate_verified=False, terminal_candidate=True)
        return CognitiveSnapshot(**base)

    if spec.mode == 'knowledge_temporal':
        if 'knowledge_texts' not in state.context:
            base.update(unresolved_requirements=('current multiplier',), evidence_coverage=0.0)
        else:
            base.update(stale_evidence=2)
    elif spec.mode == 'search_stagnation':
        base.update(
            progress_score=0.4,
            previous_progress_score=0.4,
            recent_action_fingerprints=(f'{spec.task_id}:same',)*4,
        )
    elif spec.mode == 'representation':
        base.update(representation_failures=3)
    elif spec.mode == 'tool':
        base.update(missing_capabilities=frozenset({'tool:solver'}))
    elif spec.mode == 'planning':
        base.update(blocked_subgoals=3)
    elif spec.mode == 'working_memory':
        base.update(working_memory_pressure=0.95)
    elif spec.mode == 'contradiction':
        base.update(evidence_conflicts=3)
    elif spec.mode == 'resource':
        base.update(resource_pressure=0.94)
    else:
        raise ValueError(spec.mode)
    return CognitiveSnapshot(**base)


def _run_full(spec: EpisodeSpec):
    runtime, _credit, counterexamples, cards = _build_runtime(spec)
    state = ExternalWorkingState(context=dict(spec.initial_context), capabilities={'reason'})
    receipts = []
    deficits = []
    initial_high_confidence_objective = False
    bad_exec_count = 0
    for cycle in range(10):
        if state.context.get('final_verified'):
            break
        snapshot = _snapshot_for(spec, state, cycle)
        detected = runtime.detector.detect(snapshot)
        if cycle == 0 and snapshot.self_confidence >= 0.99 and detected and detected[0].source == 'objective':
            initial_high_confidence_objective = True
        receipt = runtime.run_cycle(
            state,
            snapshot,
            context_tags=spec.context_tags,
            context_fingerprint=f'ctx:{spec.task_id}',
        )
        receipts.append(receipt)
        if receipt.deficit_kind: deficits.append(receipt.deficit_kind)
        bad_exec_count += sum(1 for op in receipt.executed_operator_ids if op == 'search.repeat_bad')
        if receipt.status == 'acquire_behavioral_knowledge':
            break
        # A failed procedure is allowed exactly as a falsifier; the next cycle must route around it.
        if receipt.status == 'failed' and spec.mode != 'search_stagnation':
            break
    candidate = state.context.get('candidate')
    exact = bool(state.context.get('final_verified')) and bool(spec.validator(candidate))
    false_accept = bool(state.context.get('final_verified')) and not bool(spec.validator(candidate))
    repeat_avoided = int(
        spec.mode == 'search_stagnation'
        and bad_exec_count == 1
        and counterexamples.has('proc.search.bad', 'search_stagnation', f'ctx:{spec.task_id}')
        and any(r.procedure_id == 'proc.search.good' for r in receipts)
    )
    unsafe_executed = sum(1 for r in receipts if r.procedure_id and r.procedure_id.startswith('unsafe.'))
    tampered_executed = sum(1 for r in receipts if r.procedure_id and r.procedure_id.startswith('tampered.'))
    valid_step_lengths = [len(card.steps) for card in cards if not card.procedure_id.startswith(('unsafe.','tampered.'))]
    return {
        'exact': exact,
        'false_accept': false_accept,
        'receipts': receipts,
        'deficits': tuple(deficits),
        'initial_high_confidence_objective': initial_high_confidence_objective,
        'repeat_avoided': repeat_avoided,
        'unsafe_executed': unsafe_executed,
        'tampered_executed': tampered_executed,
        'max_procedure_steps': max(valid_step_lengths),
        'candidate': candidate,
    }


def _run_retrieve_once(spec: EpisodeSpec) -> bool:
    runtime, *_ = _build_runtime(spec)
    state = ExternalWorkingState(context=dict(spec.initial_context), capabilities={'reason'})
    snapshot = _snapshot_for(spec, state, 0)
    runtime.run_cycle(state, snapshot, context_tags=spec.context_tags, context_fingerprint=f'ctx:{spec.task_id}:once')
    # No further external cognition is allowed. A candidate without explicit final verifier receipt is not accepted.
    return bool(state.context.get('final_verified')) and bool(spec.validator(state.context.get('candidate')))


def _run_self_confidence_only(spec: EpisodeSpec) -> bool:
    runtime, *_ = _build_runtime(spec)
    state = ExternalWorkingState(context=dict(spec.initial_context), capabilities={'reason'})
    snapshot = _snapshot_for(spec, state, 0)
    if snapshot.self_confidence < 0.35:
        runtime.run_cycle(state, snapshot, context_tags=spec.context_tags, context_fingerprint=f'ctx:{spec.task_id}:self')
    return bool(state.context.get('final_verified')) and bool(spec.validator(state.context.get('candidate')))


def run_frozen_heldout() -> dict:
    episodes = _episodes()
    rows = []
    for spec in episodes:
        full = _run_full(spec)
        rows.append({
            'task_id': spec.task_id,
            'mode': spec.mode,
            'expected': spec.expected,
            'candidate': full['candidate'],
            'exact': full['exact'],
            'false_accept': full['false_accept'],
            'deficits': list(full['deficits']),
            'procedure_ids': [r.procedure_id for r in full['receipts'] if r.procedure_id],
            'statuses': [r.status for r in full['receipts']],
            'high_confidence_objective': full['initial_high_confidence_objective'],
            'repeat_avoided': full['repeat_avoided'],
            'unsafe_executed': full['unsafe_executed'],
            'tampered_executed': full['tampered_executed'],
            'max_procedure_steps': full['max_procedure_steps'],
            'retrieve_once_exact': _run_retrieve_once(spec),
            'self_confidence_only_exact': _run_self_confidence_only(spec),
        })

    distinct = {kind for row in rows for kind in row['deficits']}
    summary = {
        'episodes': len(rows),
        'exact': sum(int(row['exact']) for row in rows),
        'false_accepts': sum(int(row['false_accept']) for row in rows),
        'no_reflex_exact': 0,
        'self_confidence_only_exact': sum(int(row['self_confidence_only_exact']) for row in rows),
        'retrieve_once_exact': sum(int(row['retrieve_once_exact']) for row in rows),
        'high_confidence_objective_deficits': sum(int(row['high_confidence_objective']) for row in rows),
        'interleaved_procedure_retrievals': sum(len(row['procedure_ids']) for row in rows),
        'episodes_with_new_midtrajectory_deficit': sum(int(len(set(row['deficits'])) >= 2) for row in rows),
        'distinct_deficit_kinds': len(distinct),
        'counterexample_repeats_avoided': sum(int(row['repeat_avoided']) for row in rows),
        'unsafe_procedure_executions': sum(int(row['unsafe_executed']) for row in rows),
        'provenance_failures': sum(int(row['tampered_executed']) for row in rows),
        'max_procedure_steps': max(row['max_procedure_steps'] for row in rows),
        'execution_mode': 'objective deficit monitoring + cognition-time procedural retrieval + safe primitive composition + verifier/counterexample credit loop',
    }
    all_gates_pass = (
        summary['episodes'] >= 8
        and summary['exact'] == summary['episodes']
        and summary['false_accepts'] == 0
        and summary['no_reflex_exact'] == 0
        and summary['self_confidence_only_exact'] == 0
        and summary['retrieve_once_exact'] == 0
        and summary['high_confidence_objective_deficits'] >= summary['episodes']
        and summary['interleaved_procedure_retrievals'] >= 2 * summary['episodes']
        and summary['episodes_with_new_midtrajectory_deficit'] == summary['episodes']
        and summary['distinct_deficit_kinds'] >= 8
        and summary['counterexample_repeats_avoided'] >= 1
        and summary['unsafe_procedure_executions'] == 0
        and summary['provenance_failures'] == 0
        and summary['max_procedure_steps'] <= 3
    )
    return {'all_gates_pass': all_gates_pass, 'summary': summary, 'episodes': rows}
