# A17 Observation Fitness / Measurement Integrity Truth v11 — Design

## Status

**DESIGN FOR IMPLEMENTATION — NOT PRODUCTION ACCEPTANCE.**

A17 extends the accepted A1–A16 Family-A Truth / Knowledge stack without changing the five canonical authorities and without mutating accepted v1–v10 object meanings.

## Problem

A16 correctly distinguishes an observed result from missing, censored, unavailable, timed-out, or interfered observation opportunities. However, an `OBSERVED` A16 result is considered observation-complete as soon as it binds the exact expected `TruthEvidence` identity/content/channel.

That does not answer a different epistemic question: whether the measurement that produced that observed evidence is fit for the truth decision being made.

Examples include a sensor that returned a value while out of calibration, a checksum-valid capture whose acquisition path was corrupted, a measurement whose resolution is insufficient for the required distinction, clock desynchronization that invalidates temporal interpretation, or detected interference that degrades an otherwise present observation.

A17 closes this gap.

## Central law

> **OBSERVED is not equivalent to EPISTEMICALLY USABLE.**

An observation can exist, be authentic, context-correct, temporally applicable, provenance-bound, and still be epistemically unfit for a particular required observation.

A17 therefore separates:

1. occurrence/completeness — owned by A16 observation results;
2. measurement-fitness requirements — owned by Knowledge;
3. evidence-backed fitness assessment — owned by Evidence;
4. epistemic consequence — owned by Epistemic;
5. receipt staleness and independent verification — owned by Verification;
6. risk-sensitive live closure — owned by Assurance.

## Non-goals

A17 does **not** introduce a scalar confidence score, probability, Bayesian posterior, generic source reputation, or long-horizon calibration model.

A17 does **not** globally revoke `TruthEvidence` when one observation use is unfit.

A17 does **not** change evidence polarity.

A17 does **not** make fitness metadata a new source of verifier independence.

A17 does **not** create a sixth Family-A authority.

## Canonical authority invariant

The implementation is five additive sidecars only:

1. `knowledge_observation_fitness_truth.py` → `PARENT_COMPONENT_ID = "external.knowledge"`
2. `evidence_observation_fitness_truth.py` → `PARENT_COMPONENT_ID = "external.evidence"`
3. `epistemic_observation_fitness_truth.py` → `PARENT_COMPONENT_ID = "external.epistemic"`
4. `verification_observation_fitness_truth.py` → `PARENT_COMPONENT_ID = "external.verification"`
5. `assurance_observation_fitness_truth.py` → `PARENT_COMPONENT_ID = "external.assurance"`

No A17 sidecar may define `COMPONENT_ID`.

## v11 binding mode

Canonical v11 binding mode:

`fitness-observation-context-dependence-defeasible-justification-provenance-lineage-temporal-v11`

v11 wraps exact v10 observation truth. It does not reinterpret v10 state.

## Knowledge-owned fitness requirements

A17 uses categorical checks rather than a scalar confidence value:

- `CALIBRATION`
- `INTEGRITY`
- `RESOLUTION`
- `SYNCHRONIZATION`
- `INTERFERENCE`

A fitness requirement revision binds an exact immutable A16 `ObservationRequirement` snapshot and a non-empty unique set of required checks.

The registry is append-only. Revision lineage cannot rebind the underlying observation requirement.

No A17 fitness requirement for an observation means **unconstrained by A17**, preserving exact A16 behavior for legacy and intentionally unconstrained observations.

## Evidence-owned fitness assessments

A fitness assessment may exist only for an exact current `OBSERVED` A16 `ObservationResultRevision`.

Each required check has one categorical status:

- `PASS`
- `FAIL`
- `UNKNOWN`

Every required check must be assessed exactly once. Unexpected or missing checks fail closed.

An assessment exact-binds:

- fitness requirement digest;
- A16 observation requirement digest;
- A16 observed result digest;
- observed evidence id and content digest;
- categorical check statuses;
- supporting basis Evidence ids;
- append-only revision/predecessor lineage.

The target observed Evidence cannot be the sole proof of its own fitness. A fitness assessment must bind at least one active basis Evidence item distinct from the observed target Evidence. This prevents self-attested measurement validity.

Fitness basis Evidence is audit support only. It does not mint verification independence and does not alter the target Evidence polarity or active/revoked state.

## Epistemic v11

`ObservationFitnessEpistemicJudge` recomputes exact A16/v10 state first.

Fitness is projected only over A16 observation requirements in the exact target supporting lineage. Unrelated claims/observations do not affect target fitness state.

For each lineage observation that is both:

- currently `OBSERVED`, and
- constrained by an enabled A17 fitness requirement,

A17 requires an exact fitness assessment for the current observed result.

Classification:

- no exact assessment → `unassessed` fitness debt;
- any required `FAIL` → `failed` fitness debt;
- no failure but one or more `UNKNOWN` → `indeterminate` fitness debt;
- all required checks `PASS` → fit.

If v10 would mark the target `SUPPORTED` but any required fitness debt exists, v11 marks the target `UNKNOWN`.

Fitness never creates `REFUTED` evidence and never upgrades a v10-unsupported target.

## Verification v11

Verification v11 receipts bind exact:

- v11 scope digest;
- TruthContext and TemporalContext;
- A16 observation-requirement/result projections;
- A17 fitness-requirement/assessment projections;
- verifier Evidence/context/provenance/dependence state.

A17 does not reimplement source independence. The v11 ledger adapts exact-current v11 receipts into the already accepted A16/v10 verification engine for controller-root/common-basis collapse and channel accounting.

Thus fitness ids, checks, statuses, basis Evidence ids, or assessment revisions can never split one dependent verifier into multiple independent corroborators.

A relevant fitness mutation stales the v11 scope and its receipts. An unrelated fitness mutation outside the target projection does not.

v10 receipts cannot masquerade as v11 receipts.

## Assurance v11

Assurance v11 preserves the accepted risk thresholds exactly:

- LOW/STANDARD → 1 independent verifier component + 1 channel;
- HIGH → 2 independent verifier components + 2 channels;
- CRITICAL → 3 independent verifier components + 3 channels.

The v11 gate recomputes current v11 epistemic truth and v11 verification coverage live.

Required unassessed/failed/indeterminate fitness blocks closure with explicit reasons.

The v11 certificate binds both A16 and A17 projections and is not self-authenticating. Validation rebuilds live state.

v10 certificates cannot masquerade as v11 certificates.

## Compatibility law

With empty A17 fitness requirement/assessment registries:

- the nested v10 `ObservationTruthScope` is exact;
- target epistemic disposition is identical to v10;
- no A17 debt exists;
- v11 verification inherits v10 validity/independence semantics;
- v11 assurance inherits v10 risk thresholds and closure semantics, apart from the intentionally distinct v11 protocol identity.

A17 does not mutate accepted `TruthEvidence`, `KnowledgeClaim`, A16 observation requirement/result, v10 receipt, or v10 certificate shapes.

## Fail-closed restoration law

All v11 serialized forms reject:

- foreign protocol or binding mode;
- unexpected fields;
- digest tampering;
- duplicate serialized revisions/receipts;
- revision gaps;
- predecessor mismatch;
- observation-requirement rebind;
- observed-result rebind inside one assessment lineage;
- missing or unexpected categorical checks;
- self-certifying target Evidence;
- v10/v11 cross-version masquerade.

## Nolane World transfer boundary

Nolane World 0.12.0 is used as an external adversarial reasoning harness only. Its separation of provenance, evidence hierarchy, and calibration motivates the categorical-fitness boundary, but Nolane World is not a canonical Nolane AI Truth authority.

Transferred invariants must exist as Nolane AI code/tests; no runtime authority is delegated to Nolane World.

## Acceptance boundary

A17 is not accepted merely because code exists. Production acceptance requires:

1. focused RED proof before implementation;
2. GREEN Truth-A proof on Python 3.11 and 3.13;
3. repository authority audit GREEN;
4. exact five-authority invariant;
5. adversarial restore/tamper and compatibility contracts;
6. clean integration onto latest `main` without rolling back concurrent B/C/D/E/F work;
7. full merge-state Refoundation proof;
8. race guard and expected-head production merge;
9. separate acceptance record after the actual production merge.
