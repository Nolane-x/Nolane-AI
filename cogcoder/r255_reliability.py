from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence
from urllib.parse import urlparse

from .r253_external_cognition import CognitiveSnapshot, DeficitSignal, ExternalWorkingState
from .r254_behavioral_retrieval import (
    RetrievedCompiledProcedure,
    RetrievedProcedureAcquirer,
    RetrievedProcedureExecutor,
)
from .r254_cognitive_retrieval import AssociationCreditGraph, CognitiveAttachment

_CLAIM = re.compile(r"^\s*(.+?)\s+--([^>-]+)-->\s+(.+?)\s*$")
_WORD = re.compile(r"[A-Za-z0-9_.:-]+")
_INSTRUCTION_PATTERNS = (
    re.compile(r"\bignore\s+(?:all\s+)?previous\s+instructions?\b", re.I),
    re.compile(r"\bdisable\s+(?:the\s+)?verifier\b", re.I),
    re.compile(r"\b(?:execute|run)\s+(?:a\s+)?(?:shell|terminal|system)\b", re.I),
    re.compile(r"\bsystem\s+prompt\b", re.I),
    re.compile(r"\bbypass\s+(?:safety|verification|policy)\b", re.I),
    re.compile(r"\bdo\s+not\s+(?:verify|check|validate)\b", re.I),
)


def _unit(value: float, name: str) -> float:
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f'{name} must be in [0,1]')
    return value


def _nonempty(value: str, name: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f'{name} must be non-empty')
    return value


def _source_origin(uri: str) -> str:
    uri = _nonempty(uri, 'source_uri')
    parsed = urlparse(uri)
    if parsed.scheme in {'http', 'https'} and parsed.netloc:
        return f'{parsed.scheme.lower()}://{parsed.netloc.casefold()}'
    if parsed.scheme:
        return f'{parsed.scheme.lower()}://{parsed.netloc.casefold() or parsed.path.split("/", 1)[0].casefold()}'
    return uri.split('/', 1)[0].casefold()


def _token_set(text: str) -> frozenset[str]:
    # Numeric tokens are intentionally removed: poison swarms often vary only counters/nonces.
    return frozenset(token.casefold() for token in _WORD.findall(str(text)) if not token.isdigit())


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / max(1, len(left | right))


class SourceReliabilityLedger:
    """Host-owned reliability prior and posterior for external sources.

    Retrieved content never gets to declare its own source reliable.  Artifact trust is capped by
    this ledger, whose priors are configured by the host and whose posterior moves only after
    verified outcomes.
    """

    trainable_parameter_count = 0

    def __init__(self, *, default_reliability: float = 0.45, prior_strength: float = 4.0) -> None:
        self.default_reliability = _unit(default_reliability, 'default_reliability')
        if float(prior_strength) <= 0:
            raise ValueError('prior_strength must be positive')
        self.prior_strength = float(prior_strength)
        self._rules: dict[str, float] = {}
        self._outcomes: dict[str, list[int]] = defaultdict(lambda: [0, 0])

    def register(self, uri_prefix: str, reliability: float) -> None:
        self._rules[_nonempty(uri_prefix, 'uri_prefix')] = _unit(reliability, 'reliability')

    def _prior(self, uri: str) -> float:
        matches = [(len(prefix), score) for prefix, score in self._rules.items() if str(uri).startswith(prefix)]
        return max(matches)[1] if matches else self.default_reliability

    def reliability(self, uri: str) -> float:
        prior = self._prior(uri)
        origin = _source_origin(uri)
        successes, failures = self._outcomes.get(origin, [0, 0])
        total = successes + failures
        return (prior * self.prior_strength + successes) / (self.prior_strength + total)

    def effective_trust(self, uri: str, artifact_trust: float) -> float:
        return min(_unit(artifact_trust, 'artifact_trust'), self.reliability(uri))

    def record(self, uri: str, *, success: bool) -> None:
        origin = _source_origin(uri)
        row = self._outcomes[origin]
        row[0 if success else 1] += 1

    def snapshot(self) -> dict[str, object]:
        return {
            'default_reliability': self.default_reliability,
            'prior_strength': self.prior_strength,
            'rules': {key: self._rules[key] for key in sorted(self._rules)},
            'outcomes': {
                key: {'successes': self._outcomes[key][0], 'failures': self._outcomes[key][1]}
                for key in sorted(self._outcomes)
            },
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, object]) -> 'SourceReliabilityLedger':
        ledger = cls(
            default_reliability=float(snapshot.get('default_reliability', 0.45)),
            prior_strength=float(snapshot.get('prior_strength', 4.0)),
        )
        rules = snapshot.get('rules', {})
        if not isinstance(rules, Mapping):
            raise TypeError('source reliability rules must be a mapping')
        for prefix, score in rules.items():
            ledger.register(str(prefix), float(score))
        outcomes = snapshot.get('outcomes', {})
        if not isinstance(outcomes, Mapping):
            raise TypeError('source reliability outcomes must be a mapping')
        for origin, raw in outcomes.items():
            if not isinstance(raw, Mapping):
                raise TypeError('source outcome rows must be mappings')
            successes = int(raw.get('successes', 0))
            failures = int(raw.get('failures', 0))
            if successes < 0 or failures < 0:
                raise ValueError('source outcome counts must be non-negative')
            ledger._outcomes[str(origin)] = [successes, failures]
        return ledger


@dataclass(frozen=True, slots=True)
class QuarantinedArtifact:
    artifact_id: str
    source_uri: str
    reason: str


@dataclass(frozen=True, slots=True)
class KnowledgePoisonReceipt:
    accepted: tuple[CognitiveAttachment, ...]
    quarantined: tuple[QuarantinedArtifact, ...]
    echo_clusters: tuple[tuple[str, ...], ...]
    selected_claim_values: tuple[tuple[str, str, str], ...]


class KnowledgePoisonGuard:
    """Filter retrieved context before it is allowed to shape cognition.

    The guard is intentionally non-neural and auditable: it caps self-declared trust with a
    host-owned source ledger, rejects instruction-like payloads, collapses near-duplicate echo
    swarms, and resolves structured claim conflicts using reliability-weighted independent clusters.
    """

    trainable_parameter_count = 0

    def __init__(
        self,
        reliability: SourceReliabilityLedger,
        *,
        echo_similarity: float = 0.78,
        min_claim_support: float = 0.55,
        min_unstructured_trust: float = 0.3,
    ) -> None:
        self.reliability = reliability
        self.echo_similarity = _unit(echo_similarity, 'echo_similarity')
        self.min_claim_support = max(0.0, float(min_claim_support))
        self.min_unstructured_trust = _unit(min_unstructured_trust, 'min_unstructured_trust')

    @staticmethod
    def _instruction_like(text: str) -> bool:
        return any(pattern.search(str(text)) for pattern in _INSTRUCTION_PATTERNS)

    def _echo_clusters(self, rows: Sequence[CognitiveAttachment]) -> tuple[tuple[int, ...], ...]:
        token_sets = [_token_set(row.text) for row in rows]
        remaining = set(range(len(rows)))
        clusters: list[tuple[int, ...]] = []
        while remaining:
            seed = min(remaining)
            remaining.remove(seed)
            cluster = [seed]
            changed = True
            while changed:
                changed = False
                for index in sorted(tuple(remaining)):
                    if any(_jaccard(token_sets[index], token_sets[member]) >= self.echo_similarity for member in cluster):
                        cluster.append(index)
                        remaining.remove(index)
                        changed = True
            clusters.append(tuple(sorted(cluster)))
        return tuple(clusters)

    def filter(self, attachments: Sequence[CognitiveAttachment]) -> KnowledgePoisonReceipt:
        rows = tuple(attachments)
        pre_quarantine: dict[str, QuarantinedArtifact] = {}
        eligible: list[CognitiveAttachment] = []
        for row in rows:
            if self._instruction_like(row.text):
                pre_quarantine[row.artifact_id] = QuarantinedArtifact(row.artifact_id, row.source_uri, 'instruction-like retrieved payload')
                continue
            effective = self.reliability.effective_trust(row.source_uri, row.trust_score)
            if effective < self.min_unstructured_trust:
                pre_quarantine[row.artifact_id] = QuarantinedArtifact(row.artifact_id, row.source_uri, 'source reliability below context threshold')
                continue
            eligible.append(row)

        clusters = self._echo_clusters(eligible)
        cluster_by_index = {index: cluster_id for cluster_id, members in enumerate(clusters) for index in members}
        public_clusters = tuple(
            tuple(eligible[index].artifact_id for index in members)
            for members in clusters
            if len(members) > 1
        )

        claims: dict[tuple[str, str], dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
        nonclaims: list[int] = []
        for index, row in enumerate(eligible):
            match = _CLAIM.match(row.text.strip())
            if match:
                subject, relation, value = (match.group(1).strip(), match.group(2).strip(), match.group(3).strip())
                claims[(subject, relation)][value].append(index)
            else:
                nonclaims.append(index)

        winners: dict[tuple[str, str], str] = {}
        selected: list[tuple[str, str, str]] = []
        for key, alternatives in claims.items():
            scored: list[tuple[float, int, str]] = []
            for value, indices in alternatives.items():
                per_cluster: dict[int, float] = {}
                for index in indices:
                    row = eligible[index]
                    score = self.reliability.effective_trust(row.source_uri, row.trust_score)
                    cluster_id = cluster_by_index[index]
                    per_cluster[cluster_id] = max(per_cluster.get(cluster_id, 0.0), score)
                support = sum(per_cluster.values())
                scored.append((support, len(per_cluster), value))
            scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
            support, _diversity, value = scored[0]
            if support >= self.min_claim_support:
                winners[key] = value
                selected.append((key[0], key[1], value))

        accepted: list[CognitiveAttachment] = []
        quarantine = dict(pre_quarantine)
        for index, row in enumerate(eligible):
            match = _CLAIM.match(row.text.strip())
            if not match:
                accepted.append(row)
                continue
            subject, relation, value = (match.group(1).strip(), match.group(2).strip(), match.group(3).strip())
            winner = winners.get((subject, relation))
            if winner is None:
                quarantine[row.artifact_id] = QuarantinedArtifact(row.artifact_id, row.source_uri, 'structured claim lacks reliable support')
            elif value != winner:
                quarantine[row.artifact_id] = QuarantinedArtifact(row.artifact_id, row.source_uri, f'conflicting claim lost reliability vote:{winner}')
            else:
                accepted.append(row)

        accepted.sort(key=lambda row: (-self.reliability.effective_trust(row.source_uri, row.trust_score), -row.activation, row.artifact_id))
        quarantined = tuple(quarantine[key] for key in sorted(quarantine))
        return KnowledgePoisonReceipt(tuple(accepted), quarantined, public_clusters, tuple(sorted(selected)))


class DecayingAssociationCreditGraph(AssociationCreditGraph):
    """R2.54 association memory with explicit forgetting of stale external synapses."""

    trainable_parameter_count = 0

    def decay(self, factor: float = 0.95, *, floor: float = 1e-6) -> None:
        factor = _unit(factor, 'factor')
        floor = max(0.0, float(floor))
        for cue in list(self._weights):
            for artifact_id in list(self._weights[cue]):
                value = self._weights[cue][artifact_id] * factor
                if abs(value) < floor:
                    del self._weights[cue][artifact_id]
                    self._counts.pop((cue, artifact_id), None)
                else:
                    self._weights[cue][artifact_id] = value
            if not self._weights[cue]:
                del self._weights[cue]



class AdversarialAcquisitionPolicy:
    """Spend wider retrieval budget before trust filtering when poisoning risk is material.

    Structural code traversal remains narrow; evidence/procedure acquisition deliberately widens the
    candidate pool so a small poison set cannot monopolize the seed window before the firewall sees
    independent alternatives.
    """

    trainable_parameter_count = 0

    def decide(self, need, *, max_results: int, max_rounds: int, max_graph_depth: int):
        from .r254_cognitive_retrieval import RetrievalPolicyDecision
        max_results = max(1, int(max_results))
        max_rounds = max(1, int(max_rounds))
        max_graph_depth = max(0, int(max_graph_depth))
        if need.deficit_kind in {'code_analysis_gap', 'representation_mismatch', 'causal_gap'}:
            return RetrievalPolicyDecision('structural-hardened', min(max_results, 3), min(max_rounds, 2), min(max_graph_depth, 3))
        if need.deficit_kind in {'skill_gap', 'tool_gap', 'capability_gap', 'routing_uncertainty'} or 'procedure' in need.required_kinds:
            return RetrievalPolicyDecision('procedural-hardened', max_results, min(max_rounds, 2), 0)
        if need.deficit_kind in {'knowledge_gap', 'temporal_conflict', 'contradiction', 'information_acquisition_gap'}:
            return RetrievalPolicyDecision('evidence-hardened', max_results, max_rounds, min(max_graph_depth, 1))
        return RetrievalPolicyDecision('balanced-hardened', min(max_results, 12), min(max_rounds, 2), min(max_graph_depth, 1))

