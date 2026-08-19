# R2.68 Cross-Task Causal Program Transfer — Design

## Status

Research candidate only. This branch is intentionally isolated from the active R2.67.1 correctness hotfix and must not be promoted until the exact accepted parent is known and the full evidence boundary is rebuilt on top of that parent.

## Goal

Add a zero-trainable-parameter capability that can reuse a previously verified three-probe causal program on a distinct target task without copying source field identities, intervention identities, source outputs, target outputs, or a host-selected target binding.

The intended capability is not generic AGI. It is one bounded learning-to-learn step: verified causal structure learned on one task becomes a portable hypothesis prior that can reduce the **target hypothesis-search candidate budget required for success** while preserving fail-closed verification.

The current Phase-A gate does **not** claim fewer total target oracle/evidence calls than an unconstrained roomy scratch solver. Oracle-cost reduction is a separate hypothesis that requires its own matched experiment.

## Scientific question

Can Nolane-AI transfer a verified causal composition across task identity, schema permutation, field renaming, intervention renaming and surface representation changes, then adapt that composition under a strictly bounded target search/evidence budget while refusing negative transfer?

The answer must be established by target-side heldout evidence, a matched tight scratch baseline, a roomy scratch control and a source-prior ablation. It must not be established by reusing source labels or embedding the target answer in the portable object.

## Source boundary

The Phase-A R2.68 benchmark begins at the **verified expression-prior boundary**. It tests portability/adaptation of an abstract three-probe composition; it does not independently re-prove the entire parent R2.67.1 source-learning pipeline on every benchmark invocation.

Before promotion, R2.68 must be rebased on the exact accepted R2.67.1-or-successor parent and the portable export must be bound to that parent's verified receipt type/evidence boundary. Until then, R2.68 is not an end-to-end claim that it learned the source program itself.

## Architecture

### 1. Portable causal program

A portable program contains only:

- a canonical composition expression over abstract probe roles `__p0`, `__p1`, `__p2`;
- an exact expression digest;
- exactly the canonical three probe roles;
- a zero trainable-parameter declaration.

It must not store:

- source field names;
- source intervention IDs;
- source semantic profile IDs;
- source raw examples or outputs;
- source target labels;
- target field names, examples, or labels.

This authority boundary must hold for **direct construction as well as helper-based export**. Public constructor use may not bypass identity checks, digest integrity, canonical probe-role identity, or the zero-parameter boundary.

### 2. Target adaptation

The target exposes only abstract probe-value contexts `__p0`, `__p1`, `__p2` to the transfer API. Expected target outputs are obtained only through the target oracle after the solver has selected a diagnostic context.

R2.68 searches a small deterministic repair neighborhood around the transferred source expression. The neighborhood contains:

- the exact transferred expression;
- all probe-role permutations;
- one-node binary-operator substitutions over a frozen numeric operator vocabulary;
- probe-role permutations of those one-node repairs.

Candidate generation has no target-output argument. Candidate IDs derive from canonical expression data only.

### 3. Active evidence ledger

Every target oracle call is charged explicitly. Diagnostic choice is computed only from disagreement among already-generated candidates, before observing the target output for that context.

A candidate or surviving version space then faces an independent terminal set that is canonically disjoint from the diagnostic pool. No terminal success is recorded until all required terminal calls are attempted and agree.

The receipt records:

- generated candidate count;
- live version-space size;
- attempted selection queries;
- attempted terminal queries and exact count;
- selected expression/candidate identity;
- source-expression versus repaired-expression selection;
- false terminal accepts;
- query trace;
- trainable parameter count.

### 4. Negative transfer

If no transferred-neighborhood candidate remains after observed evidence, R2.68 abstains. If terminal evidence contradicts the surviving hypothesis space, it abstains. If multiple semantically distinct candidates remain after the declared evidence boundary, it abstains.

R2.68 must never silently expand into unrestricted scratch synthesis after transfer failure. Scratch is measured separately as a control.

## Matched scratch baseline

A separate scratch baseline receives the same target diagnostic/terminal contexts, the same target oracle contract, the same active context-selection rule and the same terminal verifier, but no source prior. It enumerates a frozen bounded three-probe expression grammar.

The candidate-budget transfer claim is valid only when:

- transfer solves all positive targets within the frozen tight candidate cap;
- matched scratch under that same tight candidate cap fails closed;
- roomy scratch can solve the same targets, proving the target remains expressible without the prior;
- an explicit structurally shuffled source-prior ablation, using the same transfer machinery and candidate cap, removes the transfer success;
- negative-transfer families abstain with zero false accepts.

A difference in total oracle calls is reported but is **not** promoted as an evidence-efficiency claim unless separately preregistered and tested.

## Positive benchmark families

The authored Phase-A gate contains three bounded families:

1. **Probe-role permutation** — the same abstract source structure under a nontrivial probe-role binding.
2. **One-operator multiplication adaptation** — the target differs by one internal binary operator.
3. **One-operator subtraction adaptation** — a distinct one-node repair within the same causal skeleton.

Terminal contexts are disjoint from the diagnostic pool.

## Negative benchmark families

Two negative families are mandatory:

1. a target outside the one-node repair neighborhood;
2. a target that agrees with a legal hypothesis on diagnostics but deliberately contradicts it on terminal evidence.

Expected behavior is abstention/terminal rejection with zero false accepts.

## Invariance and anti-smuggling gates

The tests must prove at least:

1. portable serialization contains only canonical probe roles and no source identities;
2. direct constructor use cannot bypass identity or digest checks;
3. the trainable-parameter field cannot be changed from zero;
4. target expected outputs are absent from candidate generation;
5. target task identity is not a lookup key for an answer;
6. diagnostic ordering does not change the semantic selected result/query sequence;
7. selection and terminal context sets are disjoint before any oracle use;
8. invalid/non-finite oracle behavior fails closed;
9. source-prior ablation removes the tight-budget advantage;
10. negative transfer produces zero false accepts.

## Parameter and claim boundary

R2.68 adds `0` trainable neural parameters. Phase A may claim only:

- identity-free portability of a bounded verified three-probe expression prior;
- target-label-free local adaptation inside the frozen permutation/one-node-repair neighborhood;
- successful positive transfer under a tighter hypothesis candidate budget than the matched scratch search used by this gate;
- fail-closed negative transfer and terminal contradiction handling.

It does not establish:

- fewer total oracle calls than general scratch learning;
- unrestricted program transfer;
- arbitrary-N interventions;
- end-to-end source-program learning in the R2.68 Phase-A benchmark;
- natural-language understanding;
- open-world skill acquisition;
- broad software engineering autonomy;
- self-modifying neural learning;
- frontier-model parity;
- AGI.

## Release discipline

R2.68 must remain a draft research branch until R2.67.1 is either accepted or superseded. Before any promotion:

- rebase onto the exact accepted parent;
- bind portable export to the exact accepted parent receipt/evidence boundary;
- rerun all R2.68 RED→GREEN authority, ablation and transfer contracts;
- freeze source/spec/test hashes before heldout measurement;
- recompute authored evidence from source;
- run matched tight/roomy scratch controls and source-prior ablation;
- run protected parent lineage;
- run cross-Python verification;
- record Nolane World adjudication;
- create a complete release bundle and post-merge exact-main verification.
