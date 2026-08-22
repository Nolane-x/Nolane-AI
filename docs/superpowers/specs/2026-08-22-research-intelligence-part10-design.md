# Research Intelligence Part X — Design Specification

## Status

Implements Issue #138 on accepted Parts I–IX. The first-generation blueprint already contains four permanent Research identities: Research Chief, Repository Archaeologist, Docs/API Researcher, and Algorithm/Prior-Art Researcher.

Part X turns them into an evidence-grounded research organization. It is not a generic search wrapper: findings remain tied to source type, locator, retrieval time, source version, evidence mode, quality, freshness, contradictions and independent engineering verification.

## 1. Authority boundaries

1. Research owns research requests, source provenance, findings, contradiction resolution, synthesis and research handoff state.
2. Research does not own Requirements, Master Plan, Architecture, source code or Verification state.
3. Planning/Architecture/Coding consume research handoffs; they do not overwrite Research provenance.
4. A research finding may be informative without being authorized as engineering truth.
5. Any research synthesis that authorizes an engineering decision must be independently `VERIFIED` by Part VIII. `OVERRIDDEN` is not equivalent to an independent check.
6. Stale or contradictory findings cannot silently become shared truth.

## 2. Research profiles

`ResearchProfileRegistry` derives exactly four identities.

- Research Chief: cross-domain synthesis, source conflict arbitration and direct high-stakes research.
- Repository Archaeologist: repository history, commit lineage, conventions and historical behavior.
- Docs/API Researcher: official docs, SDK/API behavior, package registries, release notes and advisories.
- Algorithm/Prior-Art Researcher: papers, algorithms and prior art.

Specialists are primary for their domain. Research Chief is multi-domain inside Research but primary for cross-research synthesis. Routing accepts requests from any registered region and is deterministic.

## 3. Provenance model

`ResearchSource` records:
- source id;
- source kind;
- locator;
- title;
- retrieval timestamp text;
- source version/revision;
- logical retrieval epoch;
- max age in logical epochs;
- evidence mode;
- source quality;
- evidence refs;
- canonical digest.

`EvidenceMode` is exactly:
- `CURRENT_EXTERNAL` — explicitly retrieved/current external evidence;
- `INTERNAL_OFFLINE` — packaged/internal/offline knowledge.

The two modes never collapse into one flag. A consumer can inspect them in every synthesis.

`SourceKind` includes repository history, official documentation, official API, paper, package registry, release note, advisory and internal/offline knowledge.

`SourceQuality` is ordinal: secondary < primary < authoritative. Quality affects explicit conflict resolution but never erases contrary evidence.

## 4. Findings and domain-specific grounding

`ResearchFinding` records:
- finding id;
- producer identity;
- research domain;
- stable claim key;
- normalized value;
- human-readable statement;
- source ids;
- evidence refs;
- creation epoch;
- digest.

Domain grounding rules:
- Repository Archaeology findings require at least one `REPOSITORY_HISTORY` source and explicit history/convention refs.
- Docs/API findings require at least one official docs/API/package/release/advisory source.
- Prior-Art findings require a paper or explicitly classified prior-art source.
- Research Chief may synthesize across domains, but still cannot create source-less findings.

A finding is fresh only when all of its referenced sources are within their declared logical age at the current Research epoch.

## 5. Contradiction handling

Findings with the same `claim_key` and different normalized values are contradictory while both are live.

`ClaimAssessment` has dispositions:
- `SUPPORTED` — at least one fresh finding and no live contradiction;
- `CONTRADICTED` — two or more fresh incompatible values;
- `STALE` — findings exist but none are fresh;
- `UNKNOWN` — no finding exists.

Contradiction history is immutable. Research Chief may create an explicit `ContradictionResolution` selecting one finding only when:
- the selected finding is fresh;
- a reason and evidence refs are supplied;
- all competing finding ids remain recorded;
- selected source quality is not lower than every live alternative.

Resolution changes the effective research conclusion but does not delete or relabel contradictory findings.

## 6. Evidence synthesis

`ResearchSynthesis` links a bounded set of findings and produces a content-addressed synthesis artifact. It records:
- synthesis id;
- producer identity;
- finding ids;
- claim keys;
- source ids;
- evidence modes present;
- freshness at synthesis time;
- unresolved contradiction ids/claim keys;
- conclusion;
- limitations;
- evidence refs;
- artifact id/digest.

A synthesis is `shareable` only when every finding is fresh and every included contradiction is explicitly resolved. Source mode remains visible even for a shareable synthesis.

A synthesis cannot hide internal/offline knowledge behind a current-external label.

## 7. Repository archaeology

Repository archaeology must show history/convention evidence rather than generic repository guesses. A repository finding stores explicit commit/history/convention refs in addition to its source provenance. A finding labeled repository archaeology without repository-history provenance is rejected.

## 8. Engineering handoff and independent checking

`ResearchHandoff` targets one of:
- Planning;
- Architecture;
- Coding.

For informative handoffs (`authorizes_decision=False`), a shareable synthesis is sufficient.

For authorizing handoffs (`authorizes_decision=True`):
- synthesis must be shareable;
- the synthesis artifact must be registered as a Part-VIII assurance subject;
- Part VIII effective disposition must be exactly `VERIFIED`;
- `PENDING`, `REJECTED`, and `OVERRIDDEN` all reject authorization.

This preserves the difference between Central risk acceptance and independent research checking.

## 9. Direct Research Chief work

Research Chief must personally complete a difficult bounded synthesis that combines at least two research domains, retains source provenance, states limitations and produces a content-addressed artifact. The Chief then completes the assigned task through ordinary `chief_direct_work`.

## 10. Learning, memory, context and snapshot

Verified research lessons can be proposed as personal skill candidates through `SkillEvolutionEngine`; they remain candidates until normal promotion.

Research Context receives `research-state` containing only the Research control-plane digest. Other regions receive research findings through explicit handoffs rather than the entire private Research ledger.

Snapshot round-trips sources, findings, logical epoch, claim assessments/resolutions, syntheses, handoffs, profiles and counters exactly.

## 11. Fail-closed rules

- Unknown or non-Research identities cannot author findings.
- Source-less findings reject.
- Domain/source-kind mismatch rejects.
- Stale sources cannot support shareable synthesis.
- Unresolved contradictions reject shareable synthesis.
- Explicit resolution never deletes contrary evidence.
- Engineering-authorizing handoff requires Part-VIII `VERIFIED`; override is insufficient.
- Research cannot mutate Planning/Architecture/Coding authoritative state directly.
- Offline/internal and current-external evidence modes remain distinguishable.

## 12. Acceptance evidence

Part X is accepted only after RED contracts first fail because production research modules do not exist, followed by exact-head Python 3.11/3.13 GREEN tests for Part X plus Parts I–IX regressions and independent prior-Part workflows on the same head.
