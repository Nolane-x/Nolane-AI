# R2.69 — Autonomous Transfer & Meta-Learning Kernel

## Status

Architectural design for a post-R2.68 zero-trainable-parameter cognitive subsystem. R2.69 starts from accepted R2.68 on `main` at merge commit `fda7f502185266fedb00886d5786c6d28cc0e0eb`.

This milestone owns the non-neural learning-to-learn path. It does not change the neural model, train neural weights, claim AGI, claim W5 convergence, or claim frontier-model equivalence.

PR #70 (`R2.68-T research — cross-task causal prior transfer`) is retained as independent research lineage and a source of falsifiers. It is not an accepted parent and its bounded candidate-budget result is not automatically promoted into R2.69.

## Goal

Turn verified experience from earlier tasks into portable, identity-free, reusable cognitive priors that can reduce the amount of fresh search and fresh oracle evidence required on structurally related unseen tasks, while ensuring that misleading priors cannot silently corrupt terminal decisions.

The core learning-to-learn loop is:

`verified episode -> experience compilation -> structural retrieval -> active target binding -> shared evidence -> transfer or scratch continuation -> independent terminal verification -> credit / quarantine / rollback -> capability-gap update -> later reuse`

R2.69 is successful only if prior experience changes the cost of solving later heldout tasks under matched controls. Accuracy alone is not sufficient evidence of meta-learning.

## Scientific questions

R2.69 tests four questions.

1. Can a verified episode be compiled into a portable prior without storing task IDs, field IDs, intervention IDs, raw source labels, raw source outputs, target answers, or a target-specific lookup key?
2. Can that prior reduce fresh target oracle calls and proof-distinct search work versus a matched scratch solver on unseen structurally related tasks?
3. Can all target observations purchased during attempted transfer remain useful to scratch reasoning, so a bad prior has bounded rather than unbounded negative-transfer regret?
4. Can repeated verifier-backed failure signatures be converted into a typed capability-gap ledger that changes which reusable prior/procedure is promoted for later tasks without benchmark-specific answer caching?

## Design principles

### Evidence before reuse

Only an accepted or independently verified source receipt may be compiled into a reusable prior. A model narrative, successful training loss, unverified candidate, or merely passing local example is not source authority.

### Identity-free transfer

Portable experience may preserve abstract structure but not concrete source identities. Retrieval and target matching may use public target structure, but may not use hidden labels, target outputs, benchmark seed, task ID, family ID, repository name, or any content-addressed value derived from the answer.

### Shared observations, not transfer-only observations

Every target oracle query selected while transfer is active must be legal evidence for the matched scratch solver and must be appended to one immutable `SharedObservationLedger`. If transfer is abandoned, scratch continues from the same ledger. Target evidence is never discarded merely because a prior was wrong.

### Dual-use probe gate

A prior-guided query may be issued only when it satisfies both:

- it is discriminative for the transfer hypothesis space; and
- it meets a frozen minimum scratch information criterion computed before observing the target output.

If the prior-specific query would be useless or materially dominated for scratch, the governor skips it and uses the scratch query instead. This turns negative-transfer safety from a terminal-only property into a resource-governance property.

### Search may propose; authority must verify

Prior retrieval, compatibility scoring, active binding, candidate repair and gap attribution are proposal mechanisms. Independent target evidence and proof/verification receipts authorize promotion or terminal acceptance.

### No automatic readiness increase

CI success, mechanism novelty, or synthetic evidence does not automatically increase the project readiness heuristic. Any readiness movement requires a separately governed assessment with external breadth.

## Architecture

### 1. `VerifiedExperienceEnvelope`

A source episode becomes eligible for compilation only through a verifier-bound envelope containing:

- source receipt type and schema version;
- source receipt digest;
- exact source authority or verifier digest;
- accepted-parent ancestry identifier;
- declared claim scope;
- public structural facts needed for abstraction;
- source search/evidence cost summary;
- zero-trainable-parameter declaration for the R2.69 layer.

The envelope does not expose source task ID or raw target labels to the compiler API.

### 2. `PortableExperience`

The compiler emits a content-addressed portable object with an adapter-typed schema. Phase A supports `causal_basis_v1`, derived from accepted R2.68 proof-carrying adaptive causal-basis receipts.

A portable experience may contain:

- abstract role count and role topology;
- canonical structural dependency graph;
- abstract composition skeleton over role symbols;
- allowed target-side adaptation operators from a frozen trusted DSL;
- applicability constraints expressed only over public structure;
- source proof-scope metadata;
- source authority digest;
- prior strength / uncertainty metadata derived from verified evidence;
- portable object digest.

It must not contain:

- source field names;
- source intervention IDs or semantic profile IDs;
- source task/repository/family names;
- source benchmark seeds;
- raw source examples;
- raw source target values;
- target field names or target outputs;
- precomputed target candidate IDs;
- a hidden answer lookup table.

Direct construction must obey the same validation as helper-based export. A public constructor may not forge its digest, role topology, source authority, trainable-parameter count or claim scope.

### 3. `PublicTaskSignature`

Before any target oracle call, R2.69 derives a public signature from the target interface. For Phase A this may include:

- input arity;
- intervention arity / legal intervention shape;
- type/domain classes;
- public operator/DSL availability;
- public schema relation graph;
- role permutation class;
- legal query-space descriptor;
- budget contract.

It may not include any target output or label-derived statistic.

### 4. `TransferMatcher`

The matcher retrieves candidate portable experiences using only `PublicTaskSignature` compatibility and portable applicability constraints.

The matcher returns a ranked set of prior candidates plus explicit rejection reasons. Ties are resolved by canonical content order, not task identity or insertion history.

A target with no compatible prior immediately enters scratch mode; absence of a prior is not an error.

### 5. `ActiveRoleBinder`

For a compatible prior, the binder constructs target-local role mappings and bounded adaptation candidates. It may use:

- role permutations;
- public schema relations;
- frozen trusted operator substitutions;
- structure-preserving rewrites;
- target-independent candidate canonicalization.

It may not use the expected target output during candidate generation or ordering.

Diagnostic selection is based on disagreement among already-generated hypotheses and the dual-use scratch criterion. The oracle is called only after a query is selected.

### 6. `SharedObservationLedger`

All target observations are immutable, content-addressed and phase-tagged.

Each row binds:

- canonical query/context digest;
- query provenance (`transfer`, `scratch`, or `shared`);
- pre-observation transfer information score;
- pre-observation scratch information score;
- attempted oracle-call index;
- normalized observed result or explicit oracle failure;
- all hypothesis eliminations caused by that observation;
- evidence-reuse eligibility;
- phase (`diagnostic`, `challenge`, `terminal`).

No observation may be counted twice because it is consumed by both transfer and scratch. The ledger counts physical oracle attempts, not logical consumers.

### 7. `NegativeTransferGovernor`

The governor owns whether transfer remains active.

It tracks:

- prior compatibility confidence;
- transfer version-space size;
- scratch version-space size;
- cumulative shared evidence;
- transfer-specific search work;
- scratch-compatible information value of every purchased query;
- contradiction count;
- terminal-risk state;
- scoped historical credit / quarantine state for the prior.

Transfer is suspended or quarantined when any frozen condition is met, including:

- target evidence eliminates every prior-derived candidate;
- prior compatibility falls below threshold;
- a prior-guided query fails the dual-use probe gate;
- oracle behavior is invalid or non-finite;
- target evidence conflicts with the portable claim scope;
- the prior repeatedly incurs measured regret without gain;
- terminal evidence contradicts the surviving transferred hypothesis.

Fallback continues from the same `SharedObservationLedger`; it does not reset evidence.

A quarantined prior remains addressable for audit but cannot influence later targets until separately re-promoted.

### 8. `ScratchContinuation`

The matched scratch solver uses the same target DSL, legal query space, oracle contract, terminal verifier and physical evidence ledger. It receives no source prior.

For fairness, R2.69 reports both:

- **cold scratch** — scratch starting from an empty target ledger; and
- **continued scratch** — scratch after a failed transfer using the already purchased shared observations.

This separation allows measurement of positive transfer efficiency and negative-transfer regret without pretending failed transfer work never occurred.

### 9. `MetaCreditLedger`

After terminal verification, a portable prior receives scoped credit only for causal contribution demonstrated by ablation.

Credit requires all of:

- accepted target receipt;
- source-prior ablation loses the measured advantage under the same budget contract;
- target-ID / family-ID lookup tests pass;
- shuffled or structurally wrong prior does not receive the same advantage;
- terminal evidence remains independent;
- exact physical oracle accounting is known.

Credit is keyed by structural applicability scope, never by target ID.

Negative credit or quarantine is recorded when a prior creates avoidable regret or repeated contradiction.

### 10. `CapabilityGapLedger`

Repeated verifier-backed failure signatures are clustered into typed gaps. Phase A supports the following gap classes:

- `representation_gap`;
- `retrieval_gap`;
- `binding_gap`;
- `search_budget_gap`;
- `experiment_selection_gap`;
- `operator_gap`;
- `verification_gap`;
- `tool_oracle_gap`;
- `negative_transfer_gap`.

A gap record binds:

- failure receipt digests;
- affected public structural signatures;
- falsified prior IDs;
- observation/search-cost symptoms;
- proposed bounded requirement;
- evidence needed to close the gap.

The ledger may propose a typed extension requirement, but it may not directly mutate production code or promote an arbitrary generated procedure.

### 11. `ScopedPromotionController`

A new or modified portable prior/procedure may be promoted only through champion/challenger evidence.

Promotion requires:

- a frozen candidate artifact;
- preregistered target scope;
- heldout champion/challenger comparison;
- no protected-regression loss;
- no target-answer channel;
- exact budget accounting;
- explicit rollback identity;
- independent terminal verification.

Promotion is scoped. A capability that works for `causal_basis_v1` does not become a universal transfer primitive.

## Phase-A implementation scope

R2.69 Phase A is intentionally deep but bounded.

It implements the generic kernel interfaces above and one production adapter: `causal_basis_v1` on top of accepted R2.68.

It does not attempt arbitrary procedure synthesis, arbitrary Python-code self-modification, unrestricted tool creation, neural weight updates, or effectful filesystem/network experimentation. Those are later milestones built on the same kernel.

## Authored benchmark

The authored benchmark is a preregistered task sequence rather than isolated independent cases.

### Source stage

Three verified source episodes produce portable experiences for distinct 2-, 3- and 4-role causal structures. Source episode identities, raw examples and raw labels are destroyed from the target-side runtime after compilation.

### Positive transfer stage

At least 18 heldout targets are generated from structurally related but surface-shifted tasks. Required shifts include:

- field renaming;
- role permutation;
- intervention renaming;
- schema reordering;
- one bounded local operator adaptation;
- equivalent numeric representation changes where authority semantics permit them.

No target family ID or source-target pairing is provided to the matcher.

### Negative transfer stage

At least 12 targets are outside the prior applicability class. They include:

- wrong topology;
- incompatible role cardinality;
- locally misleading prior with early agreement but later diagnostic contradiction;
- terminal-only contradiction;
- oracle failure/non-finite behavior;
- structurally ambiguous public signature with no authoritative compatible prior.

### Sequential meta-learning stage

A mixed sequence interleaves related and unrelated targets. After each accepted target, the experience compiler may emit a new portable experience and the credit ledger may update applicability statistics.

The measured question is whether later related tasks require less fresh evidence/search than cold scratch while unrelated tasks retain bounded regret and zero false accepts.

## Success metrics

Phase A must report exact counts, not only aggregate percentages.

Required positive-transfer evidence:

- zero false terminal accepts;
- all accepted targets pass independent terminal verification;
- target outputs never enter candidate generation/retrieval;
- physical oracle-call ledger exactness;
- transfer-vs-cold-scratch solve comparison under a matched hard oracle budget;
- transfer-vs-cold-scratch proof-distinct candidate/search comparison;
- source-prior ablation;
- structurally shuffled prior ablation;
- target-ID/family-ID lookup rejection;
- rename/permutation invariance;
- process-restart deterministic replay.

The preferred promotion threshold is:

- positive transfer solves at least `17/18` heldout related targets;
- cold scratch solves no more than `12/18` under the same tight fresh-evidence budget, while roomy scratch proves at least `17/18` are expressible without the prior;
- median physical target oracle calls on solved positive targets are at least `30%` lower than matched cold scratch;
- median proof-distinct search work is at least `50%` lower than matched cold scratch;
- source-prior ablation removes at least `80%` of the measured oracle/search advantage;
- negative-transfer false accepts are `0/12`;
- continued scratch after rejected transfer preserves the same terminal correctness as cold scratch;
- extra physical oracle-call regret on negative-transfer targets is bounded to at most one query over the matched cold-scratch path unless the shared query strictly improves the scratch partition score.

If the total-oracle-call reduction threshold fails while candidate-search reduction passes, R2.69 may retain a narrower search-efficiency research result but may not promote the stronger meta-learning evidence-efficiency claim.

## External transfer

Promotion requires one pinned, independently sourced I/O-only task family that was not used to design the authored generator.

The external gate must use a structurally related source/target pair but different surface implementation and identities. Solver access is callable I/O plus public interface metadata only. Source internals and target implementation source are not exposed to the transfer kernel.

The external gate must include matched cold scratch, source-prior ablation, negative-transfer control, exact physical oracle accounting and terminal verification.

A single external family may support a small readiness movement but cannot establish broad AGI transfer.

## Anti-smuggling and authority contracts

Permanent adversarial tests must include at least:

1. portable serialization rejects source task IDs, family IDs, field IDs and raw label/output payloads;
2. direct constructor cannot forge source authority or portable digest;
3. retrieval result is invariant to target task name and insertion order;
4. target outputs are absent before query selection;
5. target expected values cannot be injected into candidate-generation APIs;
6. one physical oracle call cannot be counted as multiple observations when consumed by both transfer and scratch;
7. failed transfer reuses existing observations rather than restarting scratch evidence;
8. prior-guided probes that fail the scratch information floor are not issued;
9. wrong priors cannot force terminal acceptance;
10. terminal evidence cannot resolve diagnostic ambiguity that should have caused abstention;
11. terminal contexts are semantically disjoint from earlier target oracle queries;
12. oracle exceptions and non-finite outputs fail closed with exact attempted-call accounting;
13. source-prior ablation and shuffled-prior controls cannot inherit cached answers;
14. process restart cannot change semantic result or query trace under the same public evidence;
15. quarantine state cannot be bypassed through direct prior construction;
16. capability-gap clustering cannot use target IDs or hidden labels as features;
17. promotion cannot occur without challenger evidence and a rollback identity.

## Data and information boundaries

R2.69 distinguishes five information classes:

- **source authority data** — verifier-bound and available only to compilation;
- **portable abstract data** — identity-free and reusable;
- **target public structure** — available before oracle calls;
- **target diagnostic evidence** — shared between transfer and scratch after selected queries;
- **target terminal evidence** — acceptance-only and never used to train/retrieve/reorder priors.

APIs must make illegal crossings difficult by construction rather than relying on caller discipline.

## Failure states

Receipts must distinguish at least:

- `no_compatible_prior`;
- `transfer_binding_inconclusive`;
- `transfer_hypothesis_eliminated`;
- `dual_use_probe_rejected`;
- `prior_quarantined`;
- `continued_scratch_success`;
- `continued_scratch_abstained`;
- `target_oracle_error`;
- `target_evidence_overlap`;
- `terminal_contradiction`;
- `terminal_verification_failed`;
- `accepted_transfer`;
- `accepted_scratch_after_transfer`;
- `capability_gap_recorded`.

A failed transfer is not a failed task if continued scratch later succeeds, and a scratch success after transfer must not be misreported as transfer credit.

## Observability and receipts

Every R2.69 result carries replayable receipts for:

- prior retrieval candidates and rejection reasons;
- selected portable prior;
- target role binding candidates;
- every physical oracle query;
- pre-query transfer/scratch information scores;
- shared hypothesis eliminations;
- transfer stop/quarantine decision;
- scratch continuation state;
- terminal verification;
- source-prior and shuffled-prior ablation results;
- credited prior contribution;
- capability-gap changes;
- trainable parameter count (`0`).

Content digests must bind semantic evidence rather than incidental Python object identity or dictionary order.

## TDD strategy

Production implementation follows hosted RED -> GREEN.

The first RED contracts must establish the missing capability, not implementation details:

1. no portable experience compiler exists on accepted R2.68;
2. no shared transfer/scratch observation ledger exists;
3. no dual-use probe safety gate exists;
4. no safe continued-scratch negative-transfer path exists;
5. no verifier-backed capability-gap/credit ledger exists;
6. no sequential meta-learning benchmark demonstrates reduced fresh target evidence cost.

Each correction keeps the challenger test and adds protected parent regressions.

## Release discipline

R2.69 is promotable only after all of the following hold on one exact source tree:

- exact accepted R2.68 ancestor;
- design and implementation-plan provenance;
- source/test/protocol freeze before final measurement;
- authored sequential meta-learning evidence recomputed from source;
- external I/O-only transfer gate;
- source-prior and shuffled-prior ablations;
- negative-transfer bounded-regret gate;
- Python 3.11 and 3.13 verification;
- protected R2.68 through historical lineage gates required by the repository release policy;
- independent challenger evidence;
- Nolane World 0.8.0 bounded adjudication without forcing W5 convergence;
- exact source/test/evidence blob identities;
- verified COMPLETE repository ZIP;
- exact-main post-merge replay and post-merge COMPLETE ZIP.

Any production-source change after freeze invalidates the final evidence lock and requires remeasurement.

## Claim boundary

If all Phase-A gates pass, R2.69 may claim:

> A zero-trainable-parameter external runtime can compile verifier-backed causal experience into identity-free portable priors, retrieve and actively bind those priors on unseen structurally related tasks, reuse all purchased target evidence across transfer and scratch, reduce fresh oracle/search cost against matched cold scratch on the declared heldout families, bound negative-transfer regret through a dual-use probe governor, and update scoped credit/capability-gap ledgers for later reuse.

R2.69 does not establish:

- unrestricted cross-domain transfer;
- arbitrary program induction;
- arbitrary tool or code self-modification;
- open-ended language/representation invention;
- stateful temporal/filesystem/network experimentation;
- human-level natural-language/world knowledge;
- broad autonomous software engineering;
- unrestricted lifelong learning;
- W5 convergence;
- AGI;
- frontier-model parity.

## Follow-on boundary

If R2.69 succeeds, the intended next architectural step is an effectful experiment runtime that applies the same transfer/gap/credit kernel to stateful filesystem, process, dependency, temporal and network-controlled environments. R2.69 must therefore keep its kernel interfaces domain-typed and independent of the causal-basis adapter internals.