# Reasoning / Invention Closed-Loop Metareasoning Design

## Status

This design extends `external.reasoning_invention` from the C1–C7 evidence/invention spine to revision **0.0.2** without changing ownership boundaries. It is additive and backward compatible with `reasoning-invention-v1` serialized objects.

Nolane World 0.12.0 is design provenance only. Nolane AI remains the runtime authority.

## Problem

C1–C7 already provide:

- evidence-bound hypotheses and falsification plans;
- candidate Pareto comparison;
- causal challenge and ablation evidence;
- explicit experiment design and independently verified shadow receipts;
- typed capability probation;
- Cognitive Library fit/coverage diagnostics;
- destination-bound transfer trials;
- fixed-budget closed-loop evaluation.

The remaining architectural weakness is **metareasoning**. The C-layer can represent and evaluate a reasoning pass, but it cannot yet represent, in canonical public artifacts:

1. the decision-relevant unknowns and structurally distinct rivals still alive;
2. when to challenge an assumption or change representation instead of producing another near-duplicate candidate;
3. the expected value of another reasoning action under a remaining budget;
4. a fresh-context review whose evidence context is explicitly separated from the producer's prior rationale;
5. specification-gaming findings as first-class adversarial review evidence;
6. outcome evidence that can later teach a meta-policy without allowing the reasoning layer to rewrite its own policy.

Without these contracts, a closed loop can be formally correct while still wasting compute, converging by groupthink, repeatedly exploring the same representation, or validating against a narrative that already biased the verifier.

## Design objective

Add a bounded **Reasoning Ecology** around the existing C1–C7 cycle:

```text
                 Cognitive Library / evidence
                           |
                           v
                  +------------------+
                  | Epistemic Frontier|
                  | unknowns + rivals |
                  +---------+--------+
                            |
           +----------------+----------------+
           |                |                |
           v                v                v
   Assumption Inversion  Representation   Candidate /
                        Shift             Challenger
           \                |                /
            +---------------+---------------+
                            |
                            v
                  Metareasoning Actions
          value-of-thought + explicit budgets
                            |
                    Pareto action frontier
                            |
            +---------------+---------------+
            |                               |
            v                               v
       Causal / Experiment             Fresh-context
          challenge                    adversarial review
            |                               |
            +---------------+---------------+
                            v
                    Existing C7 evaluation
                            |
                            v
                  Meta-learning evidence
                            |
                explicit downstream caller
                            v
              Cognitive Library / Transfer-Meta
              (existing authorities only)
```

No arrow grants write authority. Every boundary crossing is an immutable, content-addressed artifact or evidence bundle.

## Authority invariants

### M1 — Frontier is a snapshot, not epistemic authority

A `ReasoningFrontier` records the exact reasoning receipt, Cognitive Library digest, bounded rival set, assumptions, hard constraints and decision-relevant unknowns. It cannot mutate Epistemic state, Cognitive Library, Candidate Synthesis or any ledger.

### M2 — Branch budget is structural, not a hidden optimizer

The frontier carries an explicit branch budget capped at seven live rival hypotheses. Rival categories include local, dependency, environment, framing, adversarial and unknown families. The cap bounds branching; it does not rank or accept hypotheses.

### M3 — Unknowns must be decision-relevant

Every `DecisionUnknown` carries explicit impact, uncertainty, decision relevance, discovery paths and whether resolving it could overturn the current decision. Unknown hunting therefore targets unknowns that matter instead of collecting trivia.

### M4 — Representation changes are explicit and lossy by default

`RepresentationShift` identifies source/target representations, mappings, new affordances and information that may be lost. A representation change cannot silently preserve claims whose supporting information was discarded.

### M5 — Assumption inversion creates challengers, not truth

`AssumptionInversion` records the inverted assumption, predicted consequences, surviving invariants and challenger hypothesis IDs. It cannot falsify or verify the incumbent by itself.

### M6 — Value of thought is multi-objective

`ReasoningActionProposal` exposes expected decision value, information gain, uncertainty reduction, estimated cost and residual risk separately. No canonical scalar utility is introduced. `pareto_action_frontier` returns all non-dominated viable actions.

### M7 — Stop is not acceptance

Metareasoning may return `CONTINUE`, `HALT_NO_FURTHER_VALUE`, or `ABSTAIN_UNRESOLVED`. `HALT_NO_FURTHER_VALUE` means only that no action clears the declared marginal-value threshold and no known overturning unknown remains. It is not Assurance, promotion or acceptance. If an overturning unknown remains and no viable action exists, the only fail-closed terminal disposition is `ABSTAIN_UNRESOLVED`.

### M8 — Fresh context is an auditable partition contract

A `FreshContextReviewRequest` binds distinct producer/reviewer identities and sessions, the evidence packet the reviewer may see, the review context, and withheld prior-rationale IDs. Review context and withheld rationale must be disjoint. The contract cannot prove model-memory erasure, but it can make the intended information partition explicit and tamper-evident.

### M9 — Adversarial review is first-class evidence

Specification-gaming findings identify a requirement, loophole, gaming behavior and intent violation. A fresh-context receipt cannot claim `SUPPORTED_FOR_SCOPE` while carrying blocking gaming findings, objections or counterexamples.

### M10 — Meta-learning cannot self-edit policy

Action outcomes and evaluation receipts may be compiled into `MetareasoningLearningEvidence`. The bundle is descriptive evidence only. It exposes no method to mutate Candidate Synthesis policy, Cognitive Library, Transfer/Meta, model weights or routing policy.

## Modules

### `nolane.external_core.reasoning_frontier`

Owns immutable frontier artifacts only:

- `UnknownKind`
- `HypothesisCategory`
- `DecisionUnknown`
- `RivalHypothesisRef`
- `ReasoningFrontier`
- `AssumptionInversion`
- `RepresentationShift`

All set-like fields are canonicalized. Derived identities are recomputed on restore. The live rival count cannot exceed the explicit branch budget, and the branch budget must be in `[1, 7]`.

### `nolane.external_core.reasoning_metacontrol`

Owns next-reasoning-action contracts only:

- `MetaActionKind`
- `ControlDisposition`
- `ReasoningActionProposal`
- `MetareasoningBudget`
- `ReasoningControlDecision`
- `dominates_action`
- `pareto_action_frontier`
- `plan_next_reasoning_actions`

Maximize dimensions: expected decision value, expected information gain, uncertainty reduction.

Minimize dimensions: estimated cost, residual risk.

`plan_next_reasoning_actions` filters proposals by exact frontier identity, remaining budget and minimum actionable gain, then returns the non-dominated action IDs. It never picks one winner from a trade-off frontier.

### `nolane.external_core.reasoning_review`

Owns review-partition and adversarial-review artifacts only:

- `FreshReviewVerdict`
- `FreshContextReviewRequest`
- `SpecificationGamingFinding`
- `FreshContextReviewReceipt`
- `bind_fresh_context_review`

A supported-for-scope receipt requires all requested checks, at least one reproduced evidence identity, no objections, no counterexamples and no blocking specification-gaming finding.

### `nolane.external_core.reasoning_meta_learning`

Owns descriptive action-outcome evidence only:

- `MetareasoningActionOutcome`
- `MetareasoningLearningEvidence`
- `compile_metareasoning_learning_evidence`

The compiler requires at least two distinct outcomes and at least one C7 evaluation receipt. It reports action-kind counts, successful-decision counts, information efficiency and regression count without producing a policy update or mutation method.

## Compatibility and revision policy

`external.reasoning_invention` advances from **0.0.1** to **0.0.2** because C7 evaluation already declares 0.0.2 and the new metareasoning contracts complete that revision.

The existing core schema remains `reasoning-invention-v1`. Existing serialized `VerificationPlan`, `InventionHypothesis`, `InventionCandidate`, `HypothesisChallenge`, `CapabilityGap`, `TransferIntent` and `ReasoningInventionReceipt` states therefore remain valid and retain their content identities.

New modules use independent additive schemas:

- `reasoning-frontier-v1`
- `reasoning-metacontrol-v1`
- `reasoning-review-v1`
- `reasoning-meta-learning-v1`

The canonical component revision map advances `external.reasoning_invention` to revision `2`. No unrelated component revision changes.

## Failure behavior

The new contracts fail closed on:

- empty semantic IDs;
- bool-as-number smuggling;
- NaN or infinite numeric values;
- duplicate set-like identities;
- tampered derived IDs or non-canonical state;
- branch budgets outside `[1, 7]`;
- live rival count above the branch budget;
- representation shifts where source equals target;
- fresh-review producer/reviewer identity or session reuse;
- overlap between review context and withheld rationale;
- review receipts that do not cover every required check;
- supported review verdicts with objections, counterexamples or blocking gaming findings;
- action proposals bound to the wrong frontier;
- action selection that exceeds remaining cost/action budget;
- a no-action terminal result that hides an unresolved overturning unknown;
- single-outcome meta-learning bundles or bundles with no C7 evaluation receipt.

## Tests and evidence

TDD must establish RED before production code. Focused tests cover:

1. canonical identity and tamper rejection for every artifact;
2. branch budget and rival diversity constraints;
3. decision-relevant unknown semantics;
4. assumption inversion and representation-shift invariants;
5. multi-objective action dominance and deterministic Pareto frontier;
6. budgeted continue/halt/abstain behavior;
7. fresh-context partition independence;
8. anti-spec-gaming review gates;
9. meta-learning evidence without self-modification authority;
10. revision consistency across core module, evaluation module and canonical revision map;
11. source scans forbidding imports/calls that would acquire Cognitive Library, Capability Acquisition, Transfer/Meta, Assurance or neural write authority.

Exact final-head hosted verification must include the repository's canonical Python 3.11 and 3.13 Refoundation gates before the PR can be called certified complete.

## Non-goals

This revision does not implement unrestricted autonomous science, global epistemic truth, model-weight self-editing, hidden scalar utility, automatic capability promotion, automatic transfer acceptance, automatic Assurance, or proof that an external model truly forgot withheld context. It provides the public, falsifiable control artifacts required to make those boundaries observable and enforceable.