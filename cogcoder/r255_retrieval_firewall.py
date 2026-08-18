from __future__ import annotations

from dataclasses import dataclass

from .r255_reliability import KnowledgePoisonGuard

@dataclass(frozen=True, slots=True)
class HardenedRetrievalReceipt:
    raw: object
    poison: KnowledgePoisonReceipt
    sufficient: bool


class HardenedCognitiveAcquisitionFabric:
    """R2.54 retrieval with a pre-cognition acquisition firewall."""

    trainable_parameter_count = 0

    def __init__(self, retrieval_fabric, poison_guard: KnowledgePoisonGuard) -> None:
        self.retrieval_fabric = retrieval_fabric
        self.poison_guard = poison_guard

    def retrieve(self, need) -> HardenedRetrievalReceipt:
        raw = self.retrieval_fabric.retrieve(need)
        poison = self.poison_guard.filter(raw.attachments)
        if getattr(need, 'required_kinds', frozenset()):
            present = {row.kind for row in poison.accepted}
            kind_ok = set(need.required_kinds) <= present
        else:
            kind_ok = bool(poison.accepted)
        sufficient = bool(raw.sufficient and kind_ok)
        return HardenedRetrievalReceipt(raw, poison, sufficient)


def make_r255_hardened_cognitive_retrieval_operator(
    fabric: HardenedCognitiveAcquisitionFabric,
    *,
    operator_id: str = 'knowledge.r255_hardened_cognitive_acquire',
):
    """Attach only knowledge that survives the R2.55 acquisition firewall."""
    from .r253_external_cognition import CognitiveOperatorSpec
    from .r254_cognitive_retrieval import CognitiveRetrievalNeed

    def execute(state, snapshot, signal):
        query = str(state.context.get('knowledge_query', '')).strip()
        if not query:
            query = ' '.join(map(str, snapshot.unresolved_requirements)).strip() or snapshot.objective
        context_tags = frozenset(map(str, state.context.get('retrieval_context_tags', ())))
        symbols = frozenset(map(str, state.context.get('retrieval_symbols', ())))
        required_kinds = frozenset(map(str, state.context.get('retrieval_required_kinds', ())))
        if signal.kind in {'skill_gap', 'tool_gap'} and not required_kinds:
            required_kinds = frozenset({'procedure'})
        need = CognitiveRetrievalNeed(
            objective=snapshot.objective,
            deficit_kind=signal.kind,
            query=query,
            unresolved_requirements=tuple(map(str, snapshot.unresolved_requirements)),
            context_tags=context_tags,
            symbols=symbols,
            required_kinds=required_kinds,
            representation_id=snapshot.representation_id,
            min_sufficiency=0.45 if snapshot.evidence_coverage < 0.25 else 0.58,
        )
        receipt = fabric.retrieve(need)
        accepted = receipt.poison.accepted
        public = {
            'raw_stop_reason': receipt.raw.stop_reason,
            'raw_evidence_score': receipt.raw.evidence_score,
            'raw_attachment_ids': [row.artifact_id for row in receipt.raw.attachments],
            'accepted_attachment_ids': [row.artifact_id for row in accepted],
            'quarantined': [
                {'artifact_id': row.artifact_id, 'source_uri': row.source_uri, 'reason': row.reason}
                for row in receipt.poison.quarantined
            ],
            'echo_clusters': [list(cluster) for cluster in receipt.poison.echo_clusters],
            'sufficient': receipt.sufficient,
        }
        if not accepted:
            state.context['r255_retrieval_receipt'] = public
            return {'success': False, 'reason': 'all_retrieved_context_quarantined', 'updates': {'r255_retrieval_receipt': public}}
        for attachment in accepted:
            if attachment.artifact_id not in state.evidence:
                state.evidence.append(attachment.artifact_id)
        procedures = [
            {
                'artifact_id': row.artifact_id,
                'kind': row.kind,
                'source_uri': row.source_uri,
                'version': row.version,
                'activation': row.activation,
                'trust_score': min(row.trust_score, fabric.poison_guard.reliability.reliability(row.source_uri)),
                'rationale': tuple(row.rationale),
                'content': row.text,
                'content_sha256': row.content_sha256,
            }
            for row in accepted if row.kind == 'procedure'
        ]
        updates = {
            'r255_retrieval_receipt': public,
            'knowledge_chunk_ids': tuple(row.artifact_id for row in accepted),
            'knowledge_texts': tuple(row.text for row in accepted),
            'retrieved_procedure_candidates': procedures,
        }
        state.context.update(updates)
        return {
            'success': True,
            'updates': updates,
            'evidence': tuple(row.artifact_id for row in accepted),
            'provides': {'evidence', 'external_knowledge'},
        }

    return CognitiveOperatorSpec(
        operator_id=operator_id,
        family='factual_knowledge',
        tags=frozenset({'knowledge', 'retrieval', 'poison-defense', 'provenance', 'quarantine', 'cognition-time'}),
        requires=frozenset(),
        provides=frozenset({'evidence', 'external_knowledge'}),
        cost=1.7,
        risk=0.005,
        side_effect_class='state_only',
        version='1',
        source_uri='nolane://r255-hardened-cognitive-acquisition',
        executor=execute,
    )

