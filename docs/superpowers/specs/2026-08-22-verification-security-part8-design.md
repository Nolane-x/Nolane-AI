# Verification & Security Part VIII — Design Specification

## Status

Implements Issue #136 on accepted Parts I–VII. The first-generation blueprint already contains nine permanent assurance identities: Verification Chief plus Unit/Property, Integration/E2E, Specification/Acceptance and Fuzz/Regression verifiers; Security Chief plus Threat Model, Supply-Chain and Adversarial specialists.

Part VIII makes these identities independent acceptance/falsification authorities. It does not claim infallible verification or autonomous cybersecurity equivalence. It creates explicit evidence, freshness, independence, blocking and override semantics around the existing organization.

## 1. Authority principles

1. A producer's self-claim never authorizes its own work.
2. Verification and Security may reject/block artifacts produced by specialists, Regional Chiefs or Nolane Central.
3. Central may explicitly override a block, but the resulting state is `OVERRIDDEN`, never `VERIFIED`.
4. False accepts, regressions, stale subject versions and stale sandbox/evidence epochs fail closed.
5. Verification identity is established by AgentRegistry region/agent id, not free-form labels.
6. Verification and Security Chiefs are direct falsification/adversarial workers.
7. Production neural/skill promotion paths require fresh heldout and cross-version evidence before invoking existing low-level promotion primitives.

## 2. Profiles

`AssuranceProfileRegistry` derives exactly nine profiles from `verification-testing` and `security-adversarial`.

Verification domains:
- Verification Chief: cross-domain falsification and acceptance arbitration.
- Unit/Property: invariants, properties, deterministic local behavior.
- Integration/E2E: subsystem and end-to-end behavior.
- Specification/Acceptance: requirements/spec/acceptance conformance.
- Fuzz/Regression: fuzzing, mutation/counterexamples, regression heldouts.

Security domains:
- Security Chief: cross-threat adversarial arbitration.
- Threat Model: assets, trust boundaries, abuse cases.
- Supply Chain: dependencies, provenance, package/build risks.
- Adversarial: attack harnesses, exploit/counterexample attempts.

Profiles serialize current neural versions from AgentRegistry, avoiding stale cached versions.

## 3. Assurance subjects

An `AssuranceSubject` is a content-addressed or otherwise immutable revision being judged:
- subject id;
- artifact id;
- producer agent id;
- subject version;
- policy class;
- required assurance domains;
- evidence refs;
- registration logical sequence;
- digest.

A subject id cannot be rebound. A new code/model/design revision gets a new subject id/artifact revision. This keeps AuthorityGraph blocks revision-scoped and immutable.

## 4. Challenge cases

Verification/Security identities create `ChallengeCase` records before or during evaluation:
- case id;
- subject id;
- creator identity;
- assurance domain;
- falsification/adversarial objective;
- input/corpus artifact refs;
- expected invariant/security boundary;
- evidence refs;
- status (`OPEN`, `FALSIFIED`, `SURVIVED`, `INCONCLUSIVE`).

Chief direct-work acceptance requires each Chief to personally create at least one difficult challenge case and attach resulting evidence.

## 5. Assurance evidence

`AssuranceEvidence` records:
- evidence id;
- subject id/version;
- verifier identity;
- assurance domain;
- passed;
- false accepts;
- regressions;
- sandbox digest;
- heldout digest (optional for ordinary acceptance, mandatory for promotion);
- cross-version refs (optional for ordinary acceptance, mandatory for promotion);
- challenge case refs;
- evidence refs;
- logical observation epoch;
- digest.

Evidence is valid only when:
- verifier belongs to Verification or Security region and domain is permitted by its profile;
- verifier != producer;
- subject id/version matches current registered subject;
- all referenced challenge cases belong to the subject;
- counters are non-negative;
- evidence is not older than the subject registration epoch;
- sandbox digest is explicit.

Evidence ids cannot be rebound.

## 6. Policy and decision engine

`AssurancePolicy` maps a policy class to required domains and blocking behavior. Baseline policies:
- `code-change`: unit/property + integration/E2E + fuzz/regression;
- `acceptance-critical`: unit/property + integration/E2E + specification/acceptance + fuzz/regression;
- `security-sensitive`: acceptance-critical + threat-model + adversarial;
- `dependency-change`: unit/property + integration/E2E + supply-chain + adversarial;
- `promotion`: unit/property + fuzz/regression plus promotion freshness requirements.

`AssuranceControlPlane.assess(subject_id, evidence_ids)` recomputes from current state. A subject is `VERIFIED` only when all required domains have at least one clean passing independent evidence record and no supplied evidence has false accepts/regressions. Missing/failed required evidence produces `REJECTED` and, for blocking policies, creates an AuthorityGraph block on the subject artifact revision.

No decision automatically merges code or promotes a model.

## 7. Blocking and Central override

A `BlockingReceipt` links:
- subject;
- AuthorityGraph block id;
- blocking assurance agent;
- failed/missing policy conditions;
- evidence refs;
- digest.

Verification/Security may block regardless of producer rank, including `nolane.central`.

Central override:
- requires explicit reason and evidence ids;
- uses `AuthorityGraph.central_override`;
- produces `AssuranceOverrideReceipt` linking the original block/decision and AuthorityGraph override id;
- `effective_disposition` becomes `OVERRIDDEN`;
- original rejected/blocking evidence remains unchanged;
- no API may relabel overridden evidence as passed.

## 8. Freshness and stale evidence

Subject registration captures a logical sequence/version. Evidence captures subject version and observation sequence. Evidence fails if it targets a different subject version or predates subject registration.

For changing external dependencies/sandboxes, callers can register a new subject revision or explicitly require a new sandbox digest. Part VIII never infers freshness from a human-written note.

## 9. Promotion assurance

`authorize_promotion` is the production Part-VIII wrapper around low-level promotion primitives. It requires:
- subject policy `promotion`;
- clean required evidence;
- every promotion-authorizing evidence has a non-empty heldout digest;
- at least two distinct verifier identities across the evidence set;
- at least one cross-version reference to the predecessor/current accepted version;
- zero false accepts/regressions;
- subject version equals candidate version.

Only after a `PromotionAssuranceReceipt.authorized=True` may the Part-VIII runtime wrapper invoke existing `VerificationAuthority.promote_candidate` or SkillEvolution promotion. Existing low-level classes remain primitive APIs for backward-compatible Part-I tests; production orchestration uses Part VIII.

## 10. Direct Chief work

Verification Chief must personally:
- own a verification task;
- construct a challenge against a Chief- or Central-originated subject;
- record independent evidence;
- reject/block when the challenge falsifies the claim;
- complete through ordinary `chief_direct_work` with challenge/evidence artifact refs.

Security Chief must personally:
- own a security task;
- construct a threat/adversarial challenge against a security-sensitive subject;
- record threat/adversarial evidence;
- block on discovered security regression;
- complete through ordinary `chief_direct_work`.

## 11. Context, snapshot, memory and learning

Runtime adds `runtime.assurance: AssuranceControlPlane`, persisted subjects/cases/evidence/decisions/blocks/overrides/promotion receipts/counters.

Context Compiler exposes `('assurance-state', runtime.assurance.digest)` only to Verification/Security identities by default. Other regions receive assurance events relevant to their own task/artifact through EventLedger but not the full private assurance state.

Verified falsification/adversarial techniques may create personal skill candidates; promotion remains governed. Failed hypotheses/counterexamples are durable evidence but do not become universal rules automatically.

## 12. Fail-closed rules

- unknown/non-assurance verifier -> reject;
- verifier == subject producer -> reject evidence;
- verifier domain mismatch -> reject evidence;
- stale subject version/epoch -> reject;
- evidence id rebound -> reject;
- missing sandbox digest -> reject;
- false accepts/regressions -> reject decision;
- required policy domain missing -> reject/block;
- Central-originated producer does not bypass verification/security;
- Central override remains `OVERRIDDEN`, never `VERIFIED`;
- promotion without heldout + cross-version + multiple independent verifiers -> reject;
- snapshot counter/digest/reference mismatch -> reject restore;
- no automatic merge/promotion from ordinary assurance decision.

## 13. Acceptance tests

- exactly nine profiles split 5 verification + 4 security with distinct domains;
- deterministic routing by assurance domain;
- producer self-evidence rejected;
- domain/profile mismatch rejected;
- stale version and stale epoch evidence rejected;
- false accepts and regressions rejected;
- required policy-domain omissions reject/block;
- Verification/Security can block artifacts produced by a Chief or Nolane Central;
- Central override produces `OVERRIDDEN` while preserving rejected decision/block evidence;
- promotion authorization requires heldout, cross-version and multiple identities;
- Verification Chief direct falsification case succeeds through ordinary task path;
- Security Chief direct adversarial case succeeds through ordinary task path;
- personal assurance skill remains candidate until normal promotion;
- exact snapshot/restore and assurance context isolation;
- all Parts I–VII regressions remain green on Python 3.11/3.13.
