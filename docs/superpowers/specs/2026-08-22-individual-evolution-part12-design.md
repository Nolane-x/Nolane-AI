# Individual Evolution Part XII — Design Specification

## Status

Implements Issue #140 on accepted Parts I–XI.

Part XII makes improvement distributed across all 67 permanent identities. Nolane Central, every Regional Chief, every senior specialist and every specialist keeps its own experience history, skill candidates, self-model evidence, neural accepted-version lineage and longitudinal improvement evidence. The subsystem composes existing `SkillEvolutionEngine`, `SelfModelRegistry`, `VerificationAuthority`, Part-VIII `AssuranceControlPlane`, Part-XI memory, and `AgentRegistry`; it does not replace them with a central learning service.

## 1. Architectural laws

1. Every permanent identity learns; no identity is a routing-only shell.
2. Learning stays personal by default and may widen only through progressively stronger evidence.
3. Unverified or negatively verified skills never become active knowledge.
4. Self-model claims require clean evidence external to the producer.
5. Production neural promotion requires both low-level candidate acceptance and Part-VIII promotion assurance.
6. False accepts, regressions or physical parameter count `>= 100,000,000` reject a neural challenger.
7. Accepted neural versions form immutable per-agent lineage and can roll back exactly to an accepted predecessor.
8. Learning must not silently mutate an agent's role, region, external-core bindings, memory namespace or skill namespace.
9. Longitudinal improvement claims require comparable-regime measurements and external clean evidence.
10. Central may learn and evolve, but does not own every other agent's personal learning state.

## 2. Evolution identity manifest

`EvolutionProfileRegistry` derives a live profile for every identity in `AgentRegistry`.

Each profile records:
- agent id;
- region;
- role;
- rank;
- personal memory namespace;
- personal skill namespace;
- current self-model version;
- current neural version;
- physical parameter count;
- external-core bindings;
- specialization signature;
- learning capability.

The first-generation manifest must contain exactly 67 profiles. Memory namespaces and skill namespaces must be unique. Every profile must be learning-capable and below the physical parameter ceiling.

The specialization signature is content-addressed from role, region, rank and external-core bindings. Evolution governance never rewrites that signature.

## 3. Experience and attribution

`ExperienceLedger` stores immutable per-agent experiences.

An `ExperienceRecord` contains:
- experience id;
- agent id;
- domain;
- outcome (`SUCCESS`, `FAILURE`, `MIXED`);
- summary;
- task/object refs;
- evidence refs;
- logical event anchor;
- canonical digest.

Any registered permanent identity may record its own experience. An identity may not author experience on behalf of another identity.

`AttributionReceipt` turns an experience into a bounded learning attribution. It records:
- experience id;
- attributed agent id;
- learning layer (`EPISODIC`, `SEMANTIC`, `PROCEDURAL`, `STRATEGY`, `TOOL_USE`, `NEURAL`);
- lesson;
- positive/negative disposition;
- verifier id;
- evidence id;
- canonical digest.

Positive attribution requires passing external evidence with zero false accepts and zero regressions. Self-verification or dirty evidence cannot create positive learning. Failed/dirty evidence is retained as negative attribution rather than deleted.

## 4. Skill synthesis and progressively stronger sharing

Part XII wraps `SkillEvolutionEngine` with stricter governance.

Flow:

`Experience -> Attribution -> Skill Candidate -> Independent Evidence -> Personal -> Regional -> Global`

A synthesized skill remains `CANDIDATE` until governed promotion.

Promotion requirements:
- `PERSONAL`: at least 1 clean verifier external to the skill owner;
- `REGIONAL`: at least 2 distinct clean external verifiers;
- `GLOBAL`: at least 3 distinct clean external verifiers, verifier evidence spans at least 2 regions, and at least one verifier is outside the skill owner's region.

Any failed evidence, false accept or regression attached to a candidate causes fail-closed quarantine before active promotion.

Promotion never changes skill ownership, region, content digest or the owner's specialization signature.

## 5. Specialization preservation

Every agent remains operationally distinct after learning.

Part XII records the immutable specialization signature from:
- region;
- role;
- rank;
- external-core bindings;
- memory namespace;
- skill namespace.

Skill sharing does not copy another agent's private memory, self-model or neural delta. Regional/global skills become visible through existing scope rules, but identity specialization remains unchanged.

A test must demonstrate that a specialist can gain a shared skill while its specialization signature and namespaces remain identical to baseline.

## 6. Self-model evolution

`SelfModelRegistry` remains authoritative for self-model state. Part XII adds attribution and longitudinal receipts around updates.

A self-model competence update requires:
- target agent and domain;
- new bounded score `[0,1]`;
- clean external `EvidenceRecord`;
- related experience or benchmark reference.

Self-verification, failed evidence, false accepts or regressions reject the update. Accepted updates create an immutable `SelfModelEvolutionReceipt` containing previous/new self-model versions, score, domain and evidence id.

Part XII never allows a self-model claim to become stronger merely because the producer says so.

## 7. Neural challenger governance

Neural evolution uses two gates.

### Gate A — low-level bounded candidate

`VerificationAuthority.evaluate_candidate(CandidateEvaluation)` remains authoritative for:
- `<100M` physical parameters;
- passed evaluation;
- zero false accepts;
- zero regressions;
- non-empty evidence.

A rejected low-level candidate is recorded but can never be promoted.

### Gate B — Part-VIII production assurance

Production promotion requires a Part-VIII promotion subject and an authorized `PromotionAssuranceReceipt` containing:
- heldout evidence;
- predecessor cross-version reference;
- multiple independent verifier identities;
- clean required verification domains.

`IndividualEvolutionControlPlane.promote_neural_challenger` calls `AssuranceControlPlane.promote_neural_candidate`; it never calls `VerificationAuthority.promote_candidate` directly for production promotion.

## 8. Accepted-version lineage and rollback

Every permanent identity begins with one immutable `INITIAL` lineage event reflecting its accepted neural version and physical parameter count.

Lineage event kinds:
- `INITIAL`
- `PROMOTED`
- `ROLLED_BACK`

A promoted event records:
- previous version;
- new version;
- low-level receipt id;
- assurance receipt id;
- evidence refs;
- physical parameter count;
- canonical digest.

Rollback calls the existing verification rollback primitive and records exactly the version restored. Historical lineage is never rewritten.

`AgentRegistry.accepted_versions(agent_id)` and Part-XII lineage must remain mutually coherent.

## 9. Longitudinal improvement evidence

`LongitudinalObservation` stores externally verified benchmark measurements:
- agent id;
- benchmark id;
- regime id;
- sample digest;
- score `[0,1]`;
- verifier id/evidence id;
- neural version;
- self-model version;
- canonical digest.

Observations are immutable by id.

An `ImprovementReceipt` can declare improvement only when:
- at least two observations exist for the same agent, benchmark and regime;
- latest score is strictly greater than baseline score;
- both observations are externally verified and clean;
- there is no explicit regression/false-accept evidence on the latest observation;
- specialization signature is unchanged.

Cross-regime comparisons remain informative but cannot authorize an improvement claim.

## 10. Per-agent distributed state

Part XII maintains per-agent views of:
- experience ids;
- attribution ids;
- owned skill ids;
- self-model evolution receipts;
- neural lineage;
- benchmark observations;
- improvement receipts.

Central has its own view exactly like every other identity. It may inspect organization-level summaries through authority, but personal learning ownership is not collapsed into Central.

## 11. Memory integration

Experiences may reference Part-XI memory ids, but Part XII does not bypass Part-XI visibility or lifecycle rules. A quarantined/contradicted memory cannot be promoted into active skill knowledge merely by being referenced by an experience.

Verified lessons can be stored later through normal Memory/Skill promotion paths; Part XII owns the governance receipt, not a second memory store.

## 12. Negative evidence and quarantine

Negative evidence is first-class state.

If a skill candidate receives evidence where:
- `passed=False`, or
- `false_accepts > 0`, or
- `regressions > 0`,

Part XII records the evidence, quarantines the skill and records a negative governance receipt. Quarantine history is preserved through snapshot/restore.

A quarantined skill cannot be promoted even if later clean evidence is attached until an explicit future remediation subsystem exists; Part XII does not silently unquarantine it.

## 13. Snapshot and backward restore

Runtime state adds `individual_evolution` with safe default `{}`.

Snapshot round-trip preserves exactly:
- 67 evolution profiles;
- all experiences;
- all attributions;
- skill-governance receipts;
- self-model evolution receipts;
- initial/promoted/rollback lineage;
- neural challenger records;
- longitudinal observations;
- improvement receipts;
- counters.

Old runtime state without `individual_evolution` restores by generating fresh INITIAL lineage events from the restored accepted registry state and no historical experience/attribution receipts.

## 14. Adversarial acceptance

Part XII must explicitly test:
- self-verification skill promotion attempt;
- failed/false-accept/regression skill evidence;
- regional sharing with only one verifier;
- global sharing without cross-region evidence;
- self-model inflation by producer evidence;
- neural challenger at exactly/above 100M;
- neural challenger with false accepts/regressions;
- promotion attempt without Part-VIII assurance;
- exact rollback after promotion;
- specialist specialization signature drift attempt;
- longitudinal score increase under a different regime;
- latest benchmark regression.

## 15. Acceptance evidence

Part XII is accepted only after:
1. RED contracts first fail because Part-XII production modules/runtime integration do not exist;
2. exact-head Python 3.11 and 3.13 GREEN run Part XII plus Parts I–XI organization regressions;
3. independent prior-Part workflows pass on the same head;
4. all 67 identities have valid manifests and INITIAL lineage;
5. skill/self-model/neural adverse evidence fails closed;
6. exact rollback and exact snapshot tests pass;
7. longitudinal improvement tests pass without specialization drift.

No claim is made that these mechanisms prove open-ended autonomous self-improvement, recursive intelligence explosion, or AGI. They implement bounded, evidence-gated, reversible per-agent evolution semantics.