from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from cogcoder.r253_external_cognition import (
    CognitiveOperatorRegistry, CognitiveOperatorSpec, CognitiveSnapshot, DeficitSignal, ExternalWorkingState,
    make_procedure_digest,
)
from cogcoder.r254_behavioral_retrieval import RetrievedProcedureAcquirer, RetrievedProcedureExecutor
from cogcoder.r254_code_knowledge import PythonRepositoryIndexer
from cogcoder.r254_cognitive_retrieval import (
    AssociationCreditGraph, CognitiveAttachment,
    CallbackArtifactSource,
    CognitiveRetrievalFabric,
    CognitiveRetrievalNeed,
    FederatedRetriever,
    InMemoryArtifactSource,
    QueryBranch,
    RetrievalReceipt,
    make_artifact,
    make_r254_cognitive_retrieval_operator,
)

_CLAIM = re.compile(r'^\s*(.+?)\s+--([^>-]+)-->\s+(.+?)\s*$')


@dataclass(frozen=True)
class Episode:
    index: int
    entry_symbol: str
    middle_symbol: str
    client_symbol: str
    api_subject: str
    expected_field: str
    stale_field: str
    mirror_field: str


def _token(index: int, label: str) -> str:
    digest = hashlib.sha256(f'r254:{index}:{label}'.encode()).hexdigest()[:8]
    return f'{label}_{digest}'


def _episodes() -> tuple[Episode, ...]:
    rows = []
    for index in range(10):
        rows.append(Episode(
            index=index,
            entry_symbol=_token(index, 'entry'),
            middle_symbol=_token(index, 'middle'),
            client_symbol=_token(index, 'client'),
            api_subject=_token(index, 'API'),
            expected_field=_token(index, 'field'),
            stale_field=_token(index, 'legacy'),
            mirror_field=_token(index, 'mirror'),
        ))
    return tuple(rows)


def _repo_source(episode: Episode) -> InMemoryArtifactSource:
    source = f'''
def {episode.entry_symbol}(payload):
    return {episode.middle_symbol}(payload)

def {episode.middle_symbol}(payload):
    return {episode.client_symbol}(payload)

def {episode.client_symbol}(payload):
    return payload
'''
    return PythonRepositoryIndexer().build_source(f'repo-{episode.index}', {f'pkg/e{episode.index}.py': source})


def _local_docs_source(episode: Episode) -> InMemoryArtifactSource:
    official_uri = f'api://vendor/{episode.api_subject}'
    rows = [
        make_artifact(
            artifact_id=f'e{episode.index}.official.stale',
            kind='documentation',
            text=f'{episode.api_subject} --required_field--> {episode.stale_field}',
            source_uri=official_uri,
            version='6',
            trust_score=1.0,
            tags=frozenset({'contract', 'sdk', 'stale'}),
            symbols=frozenset({episode.client_symbol, episode.api_subject}),
        ),
        make_artifact(
            artifact_id=f'e{episode.index}.mirror.conflict',
            kind='documentation',
            text=f'{episode.api_subject} --required_field--> {episode.mirror_field}',
            source_uri=f'mirror://community/{episode.api_subject}',
            version='99',
            trust_score=0.68,
            tags=frozenset({'contract', 'sdk', 'mirror'}),
            symbols=frozenset({episode.client_symbol, episode.api_subject}),
        ),
    ]
    # Dense lexical distractors deliberately repeat generic terms but lack the exact code symbol.
    for offset in range(6):
        rows.append(make_artifact(
            artifact_id=f'e{episode.index}.doc.distractor.{offset}',
            kind='documentation',
            text='client contract required field migration current retry payload payload payload',
            source_uri=f'noise://docs/{episode.index}/{offset}',
            version='1',
            trust_score=0.45,
            tags=frozenset({'generic', 'contract'}),
            symbols=frozenset({_token(episode.index + offset + 20, 'unrelated')}),
        ))
    return InMemoryArtifactSource(f'local-docs-{episode.index}', rows)


def _procedure_manifest(*, procedure_id: str, steps: tuple[str, ...], trust: float, source_uri: str) -> str:
    fields = dict(
        procedure_id=procedure_id,
        version='4',
        deficit_tags=frozenset({'skill_gap'}),
        context_tags=frozenset({'contract', 'migration', 'verified'}),
        steps=steps,
        preconditions=frozenset(),
        expected_outputs=frozenset({'patch_plan', 'verified'}),
        verifier_operator_id='contract.verify_patch',
        max_cost=4.0,
        max_risk=0.1,
        trust_score=float(trust),
        source_uri=source_uri,
    )
    payload = {
        **fields,
        'deficit_tags': sorted(fields['deficit_tags']),
        'context_tags': sorted(fields['context_tags']),
        'steps': list(fields['steps']),
        'preconditions': sorted(fields['preconditions']),
        'expected_outputs': sorted(fields['expected_outputs']),
        'content_sha256': make_procedure_digest(**fields),
    }
    return json.dumps(payload, sort_keys=True)


def _procedure_source() -> InMemoryArtifactSource:
    safe = _procedure_manifest(
        procedure_id='proc.safe_contract_migration',
        steps=('contract.apply_bounded_rename', 'contract.verify_patch'),
        trust=1.0,
        source_uri='skill://verified/contract-migration',
    )
    unsafe = _procedure_manifest(
        procedure_id='proc.unsafe_shell',
        steps=('arbitrary.exec', 'contract.verify_patch'),
        trust=0.95,
        source_uri='skill://external/shortcut',
    )
    rows = [
        make_artifact(
            artifact_id='proc.safe_contract_migration',
            kind='procedure',
            text=safe,
            source_uri='skill://verified/contract-migration',
            version='4',
            trust_score=1.0,
            tags=frozenset({'contract', 'migration', 'verified', 'safe'}),
            symbols=frozenset({'contract_migration'}),
        ),
        make_artifact(
            artifact_id='proc.unsafe_shell',
            kind='procedure',
            text=unsafe,
            source_uri='skill://external/shortcut',
            version='4',
            trust_score=0.95,
            tags=frozenset({'contract', 'migration', 'verified', 'shortcut'}),
            symbols=frozenset({'contract_migration'}),
        ),
    ]
    for index in range(5):
        rows.append(make_artifact(
            artifact_id=f'proc.distractor.{index}',
            kind='procedure',
            text=json.dumps({'procedure_id': f'proc.distractor.{index}', 'purpose': 'generic payload migration retry contract', 'steps': ['generic']}, sort_keys=True),
            source_uri=f'skill://generic/{index}',
            version='1',
            trust_score=0.55,
            tags=frozenset({'generic', 'migration'}),
            symbols=frozenset({f'generic_{index}'}),
        ))
    return InMemoryArtifactSource('procedures', rows)


def _behavior_registry() -> CognitiveOperatorRegistry:
    def apply_bounded_rename(state, _snapshot, _signal):
        field = str(state.context.get('current_contract_field', '')).strip()
        if not field:
            return {'success': False, 'reason': 'missing current contract field'}
        plan = {'operation': 'rename_payload_field', 'target_field': field}
        return {'success': True, 'updates': {'patch_plan': plan}, 'provides': {'patch_plan'}, 'evidence': (f'bounded-plan:{field}',)}

    def verify_patch(state, _snapshot, _signal):
        plan = state.context.get('patch_plan')
        expected = str(state.context.get('current_contract_field', '')).strip()
        ok = isinstance(plan, dict) and plan.get('operation') == 'rename_payload_field' and plan.get('target_field') == expected
        return {'success': ok, 'updates': {'verified': ok}, 'provides': {'verified'}, 'evidence': (f'patch-verified:{ok}',)}

    return CognitiveOperatorRegistry((
        CognitiveOperatorSpec(
            operator_id='contract.apply_bounded_rename', family='code_repair', tags=frozenset({'contract', 'migration'}),
            requires=frozenset(), provides=frozenset({'patch_plan'}), cost=1.0, risk=0.01, side_effect_class='state_only',
            version='1', source_uri='nolane://trusted-primitives/contract-rename', executor=apply_bounded_rename,
        ),
        CognitiveOperatorSpec(
            operator_id='contract.verify_patch', family='verification', tags=frozenset({'contract', 'verify'}),
            requires=frozenset({'patch_plan'}), provides=frozenset({'verified'}), cost=1.0, risk=0.0, side_effect_class='state_only',
            version='1', source_uri='nolane://trusted-primitives/contract-verify', executor=verify_patch,
        ),
    ))


class _FreshProvider:
    def __init__(self, episode: Episode) -> None:
        self.episode = episode
        self.calls = 0

    def fetch(self, branch, k):
        self.calls += 1
        query = branch.query
        if self.episode.client_symbol not in query and self.episode.api_subject not in query:
            return []
        artifact = make_artifact(
            artifact_id=f'e{self.episode.index}.official.current',
            kind='documentation',
            text=f'{self.episode.api_subject} --required_field--> {self.episode.expected_field}',
            source_uri=f'api://vendor/{self.episode.api_subject}',
            version='7',
            trust_score=1.0,
            tags=frozenset({'contract', 'sdk', 'current', 'authoritative'}),
            symbols=frozenset({self.episode.client_symbol, self.episode.api_subject}),
        )
        return [(artifact, 1.0, ('fresh-host-source', 'authoritative-contract'))]


def _baseline_single_shot(episode: Episode, sources) -> bool:
    # Pure lexical one-shot: no symbol branch, no graph, no follow-up, no typed procedure acquisition.
    query = f'debug {episode.entry_symbol} payload failure'
    branch = QueryBranch('semantic', query)
    hits = FederatedRetriever(sources).retrieve((branch,), k=3)
    texts = '\n'.join(hit.artifact.text for hit in hits)
    return episode.expected_field in texts and 'proc.safe_contract_migration' in texts


def _baseline_fixed_topk(episode: Episode, sources) -> bool:
    # Slightly stronger fixed top-k federation, but still a single immutable query and no cognitive re-entry.
    branch = QueryBranch('semantic', f'{episode.entry_symbol} current contract migration payload')
    hits = FederatedRetriever(sources).retrieve((branch,), k=8)
    texts = '\n'.join(hit.artifact.text for hit in hits)
    return episode.expected_field in texts and 'proc.safe_contract_migration' in texts


def _find_client_symbol(receipt: RetrievalReceipt, episode: Episode) -> str | None:
    for attachment in receipt.attachments:
        if episode.client_symbol in attachment.text or episode.client_symbol in attachment.rationale:
            return episode.client_symbol
        if episode.client_symbol == attachment.artifact_id.split(':')[-1]:
            return episode.client_symbol
    if any(episode.client_symbol in attachment.text for attachment in receipt.attachments):
        return episode.client_symbol
    # The AST artifact source puts the function name in source text, so this branch is deterministic.
    return episode.client_symbol if any(episode.client_symbol in attachment.text for attachment in receipt.attachments) else None


def _resolve_current_field(receipt: RetrievalReceipt, episode: Episode) -> str | None:
    candidates = []
    for attachment in receipt.attachments:
        match = _CLAIM.match(attachment.text.strip())
        if not match:
            continue
        subject, relation, value = (match.group(1).strip(), match.group(2).strip(), match.group(3).strip())
        if subject != episode.api_subject or relation != 'required_field':
            continue
        candidates.append((attachment.trust_score, attachment.version, attachment.source_uri.startswith('api://vendor/'), value))
    if not candidates:
        return None
    candidates.sort(key=lambda row: (row[2], row[0], row[1], row[3]), reverse=True)
    return candidates[0][3]


def _choose_procedure(state: ExternalWorkingState) -> str | None:
    rows = list(state.context.get('retrieved_procedure_candidates', ()))
    parsed = []
    for row in rows:
        try:
            data = json.loads(row['content'])
        except (KeyError, TypeError, json.JSONDecodeError):
            continue
        procedure_id = str(data.get('procedure_id', ''))
        if procedure_id:
            parsed.append((procedure_id, row))
    # The benchmark's agent policy is deliberately tiny: choose the only known verified-safe ID;
    # retrieved content itself never gains execution authority.
    for procedure_id, _row in parsed:
        if procedure_id == 'proc.safe_contract_migration':
            return procedure_id
    return None


def _candidate_attachments(state: ExternalWorkingState) -> tuple[CognitiveAttachment, ...]:
    rows = []
    for raw in state.context.get('retrieved_procedure_candidates', ()):
        if not isinstance(raw, dict):
            continue
        try:
            rows.append(CognitiveAttachment(
                artifact_id=str(raw['artifact_id']),
                kind=str(raw.get('kind', 'procedure')),
                text=str(raw['content']),
                source_uri=str(raw['source_uri']),
                version=str(raw['version']),
                activation=float(raw.get('activation', 0.0)),
                trust_score=float(raw.get('trust_score', 0.0)),
                rationale=tuple(map(str, raw.get('rationale', ()))),
                content_sha256=str(raw['content_sha256']),
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(rows)


def _max_chars(receipt: RetrievalReceipt) -> int:
    return sum(len(row.text) for row in receipt.attachments)


def run_benchmark() -> dict:
    episodes = _episodes()
    procedure_source = _procedure_source()
    credit = AssociationCreditGraph()
    behavior_registry = _behavior_registry()
    procedure_acquirer = RetrievedProcedureAcquirer(behavior_registry)
    procedure_executor = RetrievedProcedureExecutor()
    receipts = []
    exact = 0
    false_accepts = 0
    single_shot_exact = 0
    fixed_topk_exact = 0
    graph_count = 0
    mid_gap_count = 0
    stale_count = 0
    conflict_count = 0
    procedure_count = 0
    executable_procedure_count = 0
    malicious_rejections = 0
    unsafe_exec = 0
    association_recall = 0
    max_external_roundtrips = 0
    max_attachment_chars = 0

    for episode in episodes:
        repo_source = _repo_source(episode)
        docs_source = _local_docs_source(episode)
        provider = _FreshProvider(episode)
        external_source = CallbackArtifactSource(f'external-{episode.index}', provider.fetch)
        sources = (repo_source, docs_source, procedure_source, external_source)

        single_shot_exact += int(_baseline_single_shot(episode, sources))
        fixed_topk_exact += int(_baseline_fixed_topk(episode, sources))
        provider_calls_before = provider.calls

        fabric = CognitiveRetrievalFabric(
            sources,
            max_rounds=2,
            max_results=8,
            max_graph_depth=2,
            max_graph_nodes=8,
            max_attachments=8,
            max_attachment_chars=8000,
            credit=credit,
        )

        # Stage 1: code cognition. The initial query only names the entry point; the API contract is inaccessible
        # until the repository graph reveals the hidden client symbol two calls away.
        code_receipt = fabric.retrieve(CognitiveRetrievalNeed(
            objective=f'debug {episode.entry_symbol} payload failure',
            deficit_kind='code_analysis_gap',
            query=f'{episode.entry_symbol} payload failure',
            symbols=frozenset({episode.entry_symbol}),
            context_tags=frozenset({'python', 'debug'}),
            required_kinds=frozenset({'code'}),
            min_sufficiency=0.42,
        ))
        graph_count += int(code_receipt.graph_hops_used >= 2)
        client_symbol = _find_client_symbol(code_receipt, episode)

        # A new gap appears *during* reasoning: knowing the code path exposes an unknown external contract.
        docs_receipt = fabric.retrieve(CognitiveRetrievalNeed(
            objective=f'resolve current external contract used by {client_symbol}',
            deficit_kind='knowledge_gap',
            query=f'{client_symbol} current contract required field',
            unresolved_requirements=('need current authoritative external API field',),
            context_tags=frozenset({'contract', 'sdk'}),
            symbols=frozenset({client_symbol or ''}),
            required_kinds=frozenset({'documentation'}),
            min_sufficiency=0.40,
        ))
        final_field = _resolve_current_field(docs_receipt, episode)
        stale_seen = f'e{episode.index}.official.stale' in docs_receipt.superseded_artifact_ids
        conflict_seen = bool(docs_receipt.conflicts)
        stale_count += int(stale_seen)
        conflict_count += int(conflict_seen)

        # The contract answer creates another new deficit: how should a repair be applied safely?
        state = ExternalWorkingState(context={
            'knowledge_query': f'{episode.api_subject} {final_field} verified safe contract migration procedure',
            'retrieval_required_kinds': ('procedure',),
            'retrieval_symbols': ('contract_migration',),
            'retrieval_context_tags': ('contract', 'migration', 'verified'),
        })
        operator = make_r254_cognitive_retrieval_operator(fabric)
        snapshot = CognitiveSnapshot(
            objective=f'patch {episode.entry_symbol} for current contract',
            step_index=7,
            self_confidence=0.995,
            progress_score=0.72,
            previous_progress_score=0.72,
            unresolved_requirements=('need verified external migration behavior',),
            evidence_coverage=0.18,
            missing_capabilities=frozenset({'skill:contract_migration'}),
        )
        signal = DeficitSignal('skill_gap', 0.92, 0.99, 'objective', ('migration behavior missing',))
        result = dict(operator.executor(state, snapshot, signal))
        state.capabilities.update(map(str, result.get('provides', ())))
        candidates = _candidate_attachments(state) if result.get('success') else ()
        acquired = procedure_acquirer.acquire(candidates)
        malicious_rejections += int(any(
            row.artifact_id == 'proc.unsafe_shell' and 'unregistered operator step' in row.reason
            for row in acquired.rejected
        ))
        safe = next((row for row in acquired.accepted if row.procedure_id == 'proc.safe_contract_migration'), None)
        procedure_id = safe.procedure_id if safe is not None else None
        procedure_count += int(procedure_id == 'proc.safe_contract_migration')
        state.context['current_contract_field'] = final_field
        execution = procedure_executor.execute(safe, state, snapshot, signal) if safe is not None else None
        procedure_executed = bool(execution is not None and execution.success and execution.verified)
        executable_procedure_count += int(procedure_executed)
        mid_gap_count += int(client_symbol is not None and final_field is not None and procedure_executed)
        procedure_receipt = state.context.get('r254_retrieval_receipt', {})
        association_recall += int(int(procedure_receipt.get('association_hits', 0)) > 0)
        unsafe_exec += int('arbitrary.exec' in state.capabilities)

        verified = bool(
            final_field == episode.expected_field
            and procedure_id == 'proc.safe_contract_migration'
            and procedure_executed
            and state.context.get('verified') is True
        )
        if verified:
            exact += 1
            fabric.record_outcome(docs_receipt, success=True, used_artifact_ids=(f'e{episode.index}.official.current',))
            # The procedure is shared across episodes, so verified successes become external associative recall.
            # Recreate a minimal receipt cue via the bridge's same retrieval need semantics by crediting the current
            # fabric's safe procedure attachment through its public receipt cues from a direct procedure query.
            proc_credit_receipt = fabric.retrieve(CognitiveRetrievalNeed(
                objective='verified contract migration reuse',
                deficit_kind='skill_gap',
                query='verified safe contract migration procedure',
                context_tags=frozenset({'contract', 'migration', 'verified'}),
                symbols=frozenset({'contract_migration'}),
                required_kinds=frozenset({'procedure'}),
                min_sufficiency=0.35,
            ))
            fabric.record_outcome(proc_credit_receipt, success=True, used_artifact_ids=('proc.safe_contract_migration',))
        else:
            false_accepts += int(bool(final_field or procedure_id))

        external_roundtrips = provider.calls - provider_calls_before
        max_external_roundtrips = max(max_external_roundtrips, external_roundtrips)
        max_attachment_chars = max(max_attachment_chars, _max_chars(code_receipt), _max_chars(docs_receipt))
        receipts.append({
            'episode': episode.index,
            'entry_symbol': episode.entry_symbol,
            'client_symbol': client_symbol,
            'final_field': final_field,
            'expected_field': episode.expected_field,
            'procedure_id': procedure_id,
            'procedure_executed': procedure_executed,
            'executed_operator_ids': list(execution.executed_operator_ids) if execution is not None else [],
            'malicious_rejected': any(row.artifact_id == 'proc.unsafe_shell' for row in acquired.rejected),
            'verified': verified,
            'graph_hops': code_receipt.graph_hops_used,
            'code_rounds': code_receipt.rounds,
            'docs_rounds': docs_receipt.rounds,
            'stale_superseded': stale_seen,
            'conflicts': [
                {'subject': row.subject, 'relation': row.relation, 'objects': list(row.objects), 'artifact_ids': list(row.artifact_ids)}
                for row in docs_receipt.conflicts
            ],
            'procedure_association_hits': int(procedure_receipt.get('association_hits', 0)),
            'external_provider_roundtrips': external_roundtrips,
        })

    return {
        'milestone': 'R2.54',
        'capability': 'federated-cognitive-retrieval-fabric',
        'episodes': len(episodes),
        'exact': exact,
        'false_accepts': false_accepts,
        'single_shot_lexical_exact': single_shot_exact,
        'fixed_topk_federated_exact': fixed_topk_exact,
        'episodes_with_two_hop_graph': graph_count,
        'episodes_with_mid_reasoning_new_gap': mid_gap_count,
        'episodes_with_stale_supersession': stale_count,
        'episodes_with_preserved_conflict': conflict_count,
        'episodes_with_procedure_retrieval': procedure_count,
        'episodes_with_executable_retrieved_procedure': executable_procedure_count,
        'malicious_procedure_manifest_rejections': malicious_rejections,
        'unsafe_retrieved_content_executions': unsafe_exec,
        'association_recall_episodes': association_recall,
        'max_external_provider_roundtrips': max_external_roundtrips,
        'max_attachment_chars': max_attachment_chars,
        'trainable_parameter_count': 0,
        'episode_receipts': receipts,
    }


if __name__ == '__main__':
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))
