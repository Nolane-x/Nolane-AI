# R2.68 Cross-Task Causal Program Transfer — Design

## Status

Research candidate only. This branch is intentionally isolated from the active R2.67.1 correctness hotfix and must not be promoted until the exact accepted parent is known and the full evidence boundary is rebuilt on top of that parent.

## Goal

Add a zero-trainable-parameter capability that can reuse a previously verified three-probe causal program on a distinct target task without copying source field identities, intervention identities, source outputs, target outputs, or a host-selected target binding.

The intended capability is not generic AGI. It is one bounded learning-to-learn step: verified causal structure learned on one task becomes a portable hypothesis prior that can reduce target-side evidence/search cost while preserving fail-closed verification.

## Scientific question

Can Nolane-AI transfer a verified causal composition across task identity, schema permutation, field renaming, intervention renaming and surface representation changes, then adapt that composition with strictly bounded target evidence while refusing negative transfer?

The answer must be established by target-side heldout evidence and a matched-budget scratch baseline, not by reusing source labels or by embedding the target answer in the portable object.

## Architecture

### 1. Portable causal program

A source `ThreeProbeCompositionReceipt` may be converted into `PortableCausalProgram` only when:

- the source receipt passed;
- a selected three-probe structure exists;
- exactly three learned probe expressions exist;
- source false accepts are zero;
- the source program has an executable composition expression;
- the source receipt has no trainable-parameter delta.

The portable representation stores only:

- a canonical composition expression over abstract probe roles `__p0`, `__p1`, `__p2`;
- an expression digest;
- the number of probe roles;
- structural metadata required for auditable replay.

It must not store:

- source field names;
- source intervention IDs;
- source semantic profile IDs;
- source raw examples or outputs;
- source target labels;
- target field names, examples, or labels.

### 2. Target adaptation

The target receives three target probe channels as ordinary examples whose contexts expose abstract probe values `__p0`, `__p1`, `__p2` and whose expected value is the target output.

R2.68 searches a small, deterministic repair neighborhood around the transferred source expression. The neighborhood contains:

- the exact transferred expression;
- all probe-role permutations;
- one-node binary-operator substitutions over a frozen numeric operator vocabulary;
- probe-role permutations of those one-node repairs.

No candidate may be generated from target expected outputs. Target expected outputs are consulted only when evaluating already-generated hypotheses.

The search is content-addressed and order-invariant. Candidate IDs derive from canonical expression data only.

### 3. Evidence ledger

Every target evaluation is charged to a hard target-evidence budget. A candidate becomes a provisional winner only after exact agreement on the selection set.

A provisional winner must then pass an independent terminal set that is disjoint from the selection set by canonical context key. Terminal evidence is mandatory even if only one candidate survives.

The receipt records:

- candidates generated;
- candidates evaluated;
- selection cases attempted/exact;
- terminal cases attempted/exact;
- whether the source expression itself solved the target;
- whether a repaired expression solved the target;
- whether transfer abstained;
- false terminal accepts;
- target evidence calls;
- trainable parameter count.

### 4. Negative transfer

If no transferred-neighborhood candidate is exact on selection evidence, R2.68 abstains. If more than one semantically distinct candidate survives selection, R2.68 abstains unless terminal evidence uniquely validates one candidate. If terminal evidence contradicts the selected candidate, R2.68 abstains.

R2.68 must never silently expand into unrestricted scratch synthesis after transfer failure. Scratch is measured separately as a baseline.

## Matched scratch baseline

A separate scratch baseline receives the same target selection and terminal examples and the same frozen operator vocabulary, but no source program. It enumerates the bounded three-probe expression grammar from depth zero up to the frozen depth/candidate cap.

The transfer claim is only valid when:

- transfer solves a target within its frozen candidate/evidence budget;
- scratch with the same tight candidate budget fails closed or uses strictly more candidates/evidence;
- a roomy scratch control can solve the task, proving the target is not made impossible for the baseline;
- transfer advantage disappears when the source abstraction is ablated.

## Positive benchmark families

The initial authored gate contains at least three target families:

1. **Identity-preserving transfer** — same abstract causal program under field rename, schema permutation and probe-role permutation.
2. **One-operator adaptation** — target differs from source by exactly one binary operator while retaining the same three-probe causal skeleton.
3. **Surface-shift transfer** — source and target use distinct public task identifiers and distinct field/probe identities, with only abstract probe-role contexts shared at the transfer API boundary.

Heldout cases must be disjoint from selection cases.

## Negative benchmark families

At least two negative families are mandatory:

1. target requires a composition outside the one-node repair neighborhood;
2. target is intentionally ambiguous on selection evidence but separated by terminal evidence.

Expected behavior is abstention or terminal rejection with zero false accepts.

## Invariance and anti-smuggling gates

The frozen tests must prove:

1. source field/intervention/profile identifiers do not occur in `PortableCausalProgram` serialization;
2. target field/probe renaming does not change semantic outcome;
3. permutation of candidate enumeration order does not change semantic outcome;
4. changing source raw examples while preserving the verified abstract expression does not change the portable object;
5. target expected outputs are not passed to candidate generation;
6. target task identity is not used as a lookup key for the answer;
7. selection and terminal contexts are disjoint;
8. target evidence accounting uses attempted-case counts only;
9. non-finite/invalid evaluation fails closed;
10. false terminal accepts remain zero.

## Parameter and claim boundary

R2.68 adds `0` trainable neural parameters. It may claim only bounded cross-task reuse/adaptation of a verified three-probe causal expression inside a frozen expression-repair neighborhood.

It does not establish:

- unrestricted program transfer;
- arbitrary-N interventions;
- natural-language understanding;
- open-world skill acquisition;
- broad software engineering autonomy;
- self-modifying neural learning;
- frontier-model parity;
- AGI.

## Release discipline

R2.68 must remain a draft research branch until R2.67.1 is either accepted or superseded. Before any promotion:

- rebase onto the exact accepted parent;
- rerun the R2.68 RED→GREEN contracts on the rebased source;
- freeze source/spec/test hashes before heldout measurement;
- recompute authored evidence from source;
- run the matched scratch baselines;
- run protected parent lineage;
- run cross-Python verification;
- record Nolane World adjudication;
- create a complete release bundle and post-merge exact-main verification.
