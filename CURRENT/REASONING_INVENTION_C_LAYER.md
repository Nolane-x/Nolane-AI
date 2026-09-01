# Reasoning / Invention C-Layer

## Status

`external.reasoning_invention` is the canonical post-Epoch-0 Reasoning / Invention protocol family at **v0.0.4**.

The v0.0.4 cutover is additive. The original `reasoning-invention-v1` wire/state schema and every C8 schema remain unchanged, so prior serialized identities remain backward compatible. v0.0.4 retains the separate `reasoning-episode-v1` temporal protocol and adds `reasoning-policy-evolution-v1` rather than widening frontier, control or review artifacts into a mutable monolith.

Nolane World 0.12.0 is design provenance only. Nolane AI owns the runtime contracts, identities, authority boundaries and verification rules.

## C-layer authority map

The C family remains split across independently governed authorities:

1. `external.cognitive_library` — reusable cognitive primitives, abstractions and read-only fit/coverage diagnostics.
2. `external.candidate_synthesis` — stateless proposal generation.
3. `external.capability_acquisition` — candidate/probation/promotion/quarantine lifecycle.
4. `external.causal` — bounded causal challenge/program evidence.
5. `external.experimentation` — explicit experiment design, active probes and independently verified experiment receipts.
6. `external.transfer_meta` — verified portable experience and governed destination reuse.
7. `external.reasoning_invention` — immutable invention, frontier, metareasoning, fresh-review and closed-loop evaluation protocols.

Reasoning/Invention is deliberately **not** a seventh mutable governor. It composes the other C authorities through immutable, content-addressed evidence and intent envelopes.

## Architecture: Reasoning Ecology

v0.0.4 composes C1–C10 into a bounded, replayable reasoning ecology:

```text
Cognitive Library / evidence / observations
                    |
                    v
          Reasoning/Invention receipt
                    |
                    v
        +-------------------------+
        |    Epistemic Frontier   |
        | unknowns + assumptions  |
        | structurally distinct   |
        | rival hypotheses        |
        +------------+------------+
                     |
       +-------------+-------------+
       |             |             |
       v             v             v
  Target unknown  Assumption   Representation
                  inversion       shift
       |             |             |
       +-------------+-------------+
                     |
                     v
          Metareasoning proposals
      decision value / info gain /
      uncertainty / cost / risk
                     |
                     v
              Pareto frontier
                     |
        +------------+------------+
        |                         |
        v                         v
  causal / experiment       fresh-context
      challenge             adversarial review
        |                         |
        +------------+------------+
                     |
                     v
           C7 closed-loop evaluation
                     |
                     v
       Metareasoning learning evidence
                     |
                     v
       explicit downstream caller only
```

No arrow grants write authority. The graph is a protocol graph, not a permission graph.

## C1 — Evidence-bound invention protocol

Schema: `reasoning-invention-v1`.

`nolane.external_core.reasoning_invention` owns immutable protocol objects:

- `ReasoningEvidenceRef`
- `VerificationPlan`
- `PredictedDelta`
- `InventionHypothesis`
- `InventionAssessment`
- `InventionCandidate`
- `HypothesisChallenge`
- `CapabilityGap`
- `TransferIntent`
- `ReasoningInventionReceipt`

Discovery, independent challenge and final Assurance are distinct evidence phases. Hypotheses carry explicit assumptions, generalized variables, invariants, predicted deltas and a falsification plan before challenge. Candidate comparison is multi-objective Pareto dominance over evidence alignment, anomaly coverage, gain, robustness, transferability, uncertainty, complexity and verification cost.

A `CapabilityGap` can nominate a candidate for downstream acquisition; it cannot admit or promote it. A `TransferIntent` can describe a destination-bound reuse trial; it cannot accept reuse or issue Assurance.

## C2 — Explicit Experiment Design

Experimentation v0.0.2 separates experiment design from execution receipts. Designs bind exact metrics, baselines, perturbations, negative controls, ablations, stop policies, information metadata and hard budgets. Shadow execution and independent verification remain evidence producers rather than promotion authorities.

## C3 — Causal Challenge

Causal v0.0.2 exposes bounded, proof-carrying challenge envelopes and proper-subset/ablation evidence. Causal support is scoped to the exact accepted program/evidence row; a causal-program ID is never interpreted as a universal causal law.

## C4 — Typed Capability Probation

Capability Acquisition v0.0.2 uses typed probation evidence rather than loose summary claims. Probation remains downstream of candidate synthesis and reasoning. Promotion stays behind the existing exact Assurance/evidence/baseline firewall.

## C5 — Governed Cognitive Library

Cognitive Library v0.0.2 exposes provenance-backed capability descriptors and deterministic fit/coverage diagnostics against an exact library digest. Reasoning can therefore demonstrate a capability gap without gaining a registration API.

## C6 — Destination Transfer Trials

Transfer/Meta v0.0.2 binds generalized variables and invariants to a destination-specific trial matrix, records negative transfer by target regime, and retains explicit Assurance authorization and revocation semantics.

## C7 — Closed-loop Reasoning Evaluation

`nolane.external_core.reasoning_evaluation` was introduced with the Reasoning/Invention v0.0.2 family and is retained under the current v0.0.4 family. It evaluates fixed-budget invention cycles and emits immutable evidence over false acceptance, abstention quality, information efficiency, generalization, robustness and regressions. It does not create one scalar global score and cannot promote a capability or accept transfer.

## C8 — Bounded Epistemic Frontier

Schema: `reasoning-frontier-v1`.

`nolane.external_core.reasoning_frontier` makes the unresolved reasoning state explicit.

### `DecisionUnknown`

Each unknown records:

- description and `UnknownKind`;
- impact;
- uncertainty;
- decision relevance;
- one or more discovery paths;
- whether resolving the unknown could overturn the current decision.

Unknown hunting is therefore directed at decision-relevant missing information rather than trivia accumulation.

### `RivalHypothesisRef`

Every live rival binds:

- exact hypothesis ID;
- hypothesis category;
- structural-family ID;
- predictions;
- falsifiers;
- supporting and opposing evidence IDs.

A frontier has an explicit branch budget in **`[1, 7]`** and cannot contain more live rivals than that budget. This imports Nolane World's bounded structural-diversity discipline without turning a heuristic portfolio into truth authority.

### `ReasoningFrontier`

A frontier binds:

- exact `ReasoningInventionReceipt` identity;
- objective identity;
- exact Cognitive Library digest;
- canonical unknown set;
- canonical rival set;
- assumptions;
- hard constraints;
- branch budget.

It is a snapshot, not Epistemic or Cognitive Library authority.

### Assumption inversion

`AssumptionInversion` can only be bound to an assumption already present in the frontier. It records the inverted premise, consequences, surviving invariants and challenger hypothesis IDs. Inversion creates a falsifiable challenger; it does not declare the original assumption false.

### Representation shift

`RepresentationShift` records source and target representations, explicit mappings, new affordances, lost information and resulting challengers. Source and target must differ. Information loss is explicit so claims cannot silently survive a lossy re-encoding.

## C8 — Value-of-Thought Metacontrol

Schema: `reasoning-metacontrol-v1`.

`nolane.external_core.reasoning_metacontrol` asks a narrower question than a planner: **which reasoning actions are still worth considering under the declared reasoning budget?**

### Reasoning action kinds

- target a decision-relevant unknown;
- generate a structurally distinct challenger;
- invert an assumption;
- shift representation;
- design a discriminating experiment;
- request a causal challenge;
- request a fresh-context review.

### Explicit action vector

Each `ReasoningActionProposal` keeps the following dimensions separate:

- expected decision value — maximize;
- expected information gain — maximize;
- expected uncertainty reduction — maximize;
- estimated cost — minimize;
- residual risk — minimize.

There is no canonical weighted sum. `pareto_action_frontier` returns every non-dominated viable action in deterministic identity order.

### Explicit budget

`MetareasoningBudget` binds an exact frontier plus remaining action count, remaining cost and minimum actionable gain. A proposal bound to another frontier is rejected.

### Stop semantics

`ReasoningControlDecision` has only three dispositions:

- `CONTINUE` — one or more budget-feasible non-dominated reasoning actions remain;
- `HALT_NO_FURTHER_VALUE` — no action clears the declared marginal-value floor and no known decision-overturning unknown remains;
- `ABSTAIN_UNRESOLVED` — reasoning cannot continue within budget while a decision-overturning unknown remains.

`HALT_NO_FURTHER_VALUE` is **not** acceptance. `ABSTAIN_UNRESOLVED` prevents exhausted compute from being misrepresented as confidence.

## C8 — Fresh-context adversarial review

Schema: `reasoning-review-v1`.

`nolane.external_core.reasoning_review` makes reviewer information boundaries explicit and tamper-evident.

### `FreshContextReviewRequest`

A request binds:

- goal and candidate IDs;
- distinct producer/reviewer agent IDs;
- distinct producer/reviewer session IDs;
- evidence packet available to the reviewer;
- full review context;
- explicitly withheld producer-rationale IDs;
- required review checks.

The evidence packet must be contained in the review context, while review context and withheld rationale must be disjoint. This contract cannot prove that an external model has literally forgotten earlier context; it makes the intended partition auditable and rejects obvious same-agent/session reuse.

### Specification-gaming evidence

`SpecificationGamingFinding` records the exact requirement, loophole, gaming behavior, intent violation and whether the finding is blocking.

A `SUPPORTED_FOR_SCOPE` review cannot carry objections, counterexamples or a blocking gaming finding. The binder also requires every requested check and at least one reproduced evidence identity from the exact evidence packet.

The verdict is scope-bounded review evidence. It is not Assurance, promotion or transfer acceptance.

## C8 — Descriptive metareasoning learning

Schema: `reasoning-meta-learning-v1`.

`nolane.external_core.reasoning_meta_learning` closes the observation loop without creating self-edit authority.

`MetareasoningActionOutcome` binds an executed reasoning action to:

- frontier and control-decision identities;
- action kind and action identity;
- C7 evaluation receipt;
- outcome evidence;
- decision correctness;
- observed information gain;
- actual cost;
- regression count;
- generalization and robustness observations.

`compile_metareasoning_learning_evidence` requires at least two distinct outcomes and compiles descriptive metrics including action-kind counts, correct decisions, information efficiency, regressions, generalized outcomes and robust outcomes.

The resulting evidence has **no policy-update method, model-write method, promotion method or transfer-acceptance method**. C10 consumes this descriptive evidence only through its explicit evidence-split/proposal path; the evidence object itself still has no policy-update authority.

## C9 — Replayable Reasoning Episodes

Schema: `reasoning-episode-v1`.

`nolane.external_core.reasoning_episode` closes the temporal-integrity gap between individually valid C8 artifacts. A `ReasoningEpisode` binds one root frontier, the exact current frontier, immutable initial action/cost limits, an ordered content-addressed transition chain, an optional terminal C8 control decision and a stable episode key.

Every `ReasoningFrontierTransition` binds the exact generation, previous frontier, full next frontier, C8 control decision, selected Pareto-authorized action, derived semantic frontier delta, observed cost and overrun state. A transition is admitted only from the current frontier and current derived budget; stale control decisions, reused control/action authority and cross-frontier actions fail closed.

### Continuity and evidence

Within one episode the `reasoning_receipt_id`, objective, Cognitive Library digest, hard constraints and branch budget are immutable. Changing any of them starts a new epistemic context rather than laundering a context switch into an ordinary reasoning step. Unknowns, rivals and assumptions may evolve only through an evidence-carrying derived delta. A stable hypothesis whose rival content changes is recorded as a revision rather than silently retired and reintroduced.

### Budget conservation

Spent actions and cost are derived from the transition chain, never trusted as caller-supplied counters. Estimated cost must fit before a transition is authorized; observed cost is recorded without clipping. An observed overrun is preserved as evidence and terminalizes the episode as `ABSTAINED_BUDGET_OVERRUN`. Exact exhaustion still requires an explicit zero-budget C8 terminal decision, so compute exhaustion cannot masquerade as epistemic success.

### Replay authority

`to_state()` serializes the root plus ordered journal. `from_state()` replays that journal and requires the reconstructed current frontier, budget, terminal decision, status and derived identities to match exactly. Forged snapshots, skipped generations, duplicate authority consumption, non-canonical deltas and stale replay prefixes are rejected.

Episode statuses are deliberately limited to `ACTIVE`, `HALTED_NO_FURTHER_VALUE`, `ABSTAINED_UNRESOLVED` and `ABSTAINED_BUDGET_OVERRUN`. There is no `ACCEPTED`, `SUCCESS` or `PROMOTED` state. C9 is reasoning-history authority only; it is not D planning authority, E execution authority, Cognitive Library write authority or Assurance.

## Global authority invariants

### I1 — Proposal is not authority

Candidate Synthesis can emit proposals; it cannot admit, probation, promote, quarantine, persist or install them.

### I2 — Hypothesis/frontier is not knowledge

Reasoning can describe hypotheses, unknowns, rivals, assumptions and representation shifts. It cannot register Cognitive Library state.

### I3 — Experiment/review is not Assurance

Experiment and fresh-review receipts are evidence. Neither can mint final Assurance or promotion authority.

### I4 — Causal evidence is bounded

A Causal program strengthens an exact evidence claim only within its accepted scope.

### I5 — Acquisition is explicit

Only an explicit caller acting through Capability Acquisition can create acquisition lifecycle state.

### I6 — Transfer is explicit and destination-bound

Only Transfer/Meta owns reuse lifecycle state; Assurance remains the acceptance authority required by that governor.

### I7 — No self-verification loop

Discovery, challenge, fresh review and final Assurance remain distinct evidence roles. Stronger authority cannot be minted by relabeling weaker evidence.

### I8 — Metacontrol is not execution authority

A metacontrol decision names worthwhile reasoning actions; it does not execute tools, mutate ledgers or choose a hidden global optimum.

### I9 — Stop is not success

No-further-value means no declared reasoning action is worth its cost under the current budget. It does not mean the underlying engineering claim is true.

### I10 — Meta-learning is descriptive

Outcome aggregation cannot modify its own policy, neural state, Cognitive Library, Transfer/Meta or Capability Acquisition.

## Canonical schemas

The component version is `0.0.4` while schemas remain independently versioned:

| Module | Schema |
| --- | --- |
| `reasoning_invention.py` | `reasoning-invention-v1` |
| `reasoning_frontier.py` | `reasoning-frontier-v1` |
| `reasoning_metacontrol.py` | `reasoning-metacontrol-v1` |
| `reasoning_review.py` | `reasoning-review-v1` |
| `reasoning_meta_learning.py` | `reasoning-meta-learning-v1` |
| `reasoning_episode.py` | `reasoning-episode-v1` |
| `reasoning_policy_evolution.py` | `reasoning-policy-evolution-v1` |
| `reasoning_evaluation.py` | existing C7 evaluation schema |

The v1 core schema, all C8 schemas and `reasoning-episode-v1` are intentionally retained during the component revision cutover so earlier serialized states and content identities do not change merely because C9/C10 exists.

## Fail-closed behavior

C1–C10 reject, as applicable:

- empty semantic identities;
- duplicate set-like identities;
- forged derived identities;
- caller-order drift in canonical sets;
- bool-as-number smuggling;
- NaN and infinity;
- bounded scores outside `[0, 1]`;
- branch budgets outside `[1, 7]`;
- live-rival counts above branch budget;
- duplicate live hypothesis IDs;
- representation shifts with identical source and target;
- assumption inversions against assumptions absent from the frontier;
- action proposals or budgets bound to the wrong frontier;
- terminal `HALT_NO_FURTHER_VALUE` states that hide a known overturning unknown;
- same producer/reviewer identity or session in fresh-context review;
- review-context leakage of explicitly withheld rationale;
- incomplete required review checks;
- reproduced review evidence not present in the request packet;
- `SUPPORTED_FOR_SCOPE` with objections, counterexamples or blocking specification gaming;
- duplicate metareasoning outcomes;
- meta-learning bundles too small to compare behavior;
- stale frontier/control/budget authority and reused control or action identities;
- episode continuity drift across objective, receipt, library, constraints or branch budget;
- evidence-free frontier mutation, forged frontier deltas and skipped generations;
- caller-invented spent-budget counters or replay states inconsistent with the transition journal;
- continued reasoning authority after observed budget overrun;
- overlapping C10 development/holdout episode identities;
- policy revision skips, parent-lineage mismatch or forged derived policy identities;
- policy constraints that relax parent bounds or expand allowed reasoning-action kinds;
- policy review provenance that reuses producer/reviewer agent, session or context authority, or leaks withheld rationale;
- adoption/rollback authorization issued by Reasoning/Invention itself;
- adoption or rollback receipts bound to the wrong parent/candidate lineage;
- non-canonical restored state.

## Cross-component integration contract

Reasoning/Invention consumes stable IDs and immutable snapshots rather than mutable governor instances:

- Cognitive Library through exact digest and item IDs;
- Candidate Synthesis through proposal/candidate IDs;
- Causal through accepted program IDs;
- Experimentation through design/shadow/verification receipt IDs;
- Capability Acquisition through caller-mediated `CapabilityGap` handoff only;
- Transfer/Meta through caller-mediated destination intent/trial evidence only;
- Assurance remains downstream and unchanged;
- C7 evaluation supplies outcome evidence to descriptive meta-learning;
- C9 episodes consume exact C8 frontier/control/action identities and emit replayable transition history without executing the selected action.
- C10 policy evolution consumes exact episode/evaluation evidence plus external adoption/rollback authorization and emits immutable proposal/review/adoption/rollback receipts without owning a mutable current-policy governor.

This boundary is intentionally narrow so A, B, D, E, F, Memory and Truth can evolve independently without C silently absorbing their authority.

## Verification contract

C8–C10 were developed RED -> GREEN. The closure gate requires:

1. coherent `external.reasoning_invention == 0.0.4` across all Reasoning/Invention modules and the canonical revision map;
2. canonical round-trip and forged-ID rejection for every C8/C9/C10 artifact;
3. branch-budget and structural-rival constraints;
4. Pareto/order-invariant metacontrol;
5. continue/halt/abstain fail-closed semantics;
6. fresh-context partition and anti-spec-gaming gates;
7. descriptive-only meta-learning;
8. exact frontier-generation continuity and stale control/action rejection;
9. transition-derived budget conservation, observed-overrun terminalization and critical-unknown preservation;
10. root-plus-journal replay that rejects forged current snapshots, status, deltas or counters;
11. disjoint C10 development/holdout evidence and Pareto-non-regressing shadow evaluation;
12. monotonic policy constraints that cannot relax parent limits, expand allowed action kinds or escalate caller-owned reasoning budgets;
13. fresh-context policy review plus external-only adoption/rollback authorization with exact lineage;
14. source scans preventing mutable C/Assurance/model/execution authority backdoors;
15. exact-head repository Refoundation gates on Python 3.11 and 3.13 plus resynchronization with latest `main` before certification if the base advances.

## Non-goals

This architecture does not claim AGI, unrestricted autonomous science, global truth, arbitrary self-modification, hidden scalar utility, automatic capability promotion, automatic transfer acceptance, automatic Assurance or proof that an external model truly erased withheld context. It establishes a stronger, falsifiable and bounded reasoning substrate whose outputs remain attributable and reversible.

## C10 — Governed Metareasoning Policy Evolution

Schema: `reasoning-policy-evolution-v1`.

C10 turns C8/C9 metareasoning evidence into a governed proposal surface without granting Reasoning/Invention self-edit authority. `MetareasoningPolicy` revisions are immutable and content-addressed; every non-root policy binds an exact parent, and proposals advance exactly one revision. Policy deltas are monotonic constraints only: they may tighten remaining action count or cost, raise the minimum actionable-gain floor, and remove allowed reasoning-action kinds, but cannot expand caller authority or relax safety thresholds.

Policy learning uses an explicit multi-episode `PolicyEvidenceSplit` with disjoint development and holdout episodes. Shadow evaluation keeps decision accuracy, information gain, uncertainty reduction, cost, residual risk and regression count as separate Pareto dimensions, so an improvement on one axis cannot compensate for a regression on another. Fresh-context review binds distinct producer/reviewer agents and sessions, auditable review context, withheld rationale, completed checks, reproduced evidence, and explicit objection/specification-gaming/leakage findings. A supported review cannot hide a blocker.

Adoption and rollback remain externally authorized operations. C cannot mint adoption authority, expose a mutable current-policy governor, or self-promote a learned policy. Adoption requires proposal, Pareto-non-regressing shadow evidence, fresh-context review and exact external authorization to bind the same parent/candidate lineage. Rollback is lineage-exact and restores the immutable parent under separate external rollback authorization.

C10 therefore closes policy evolution as **proposal + evidence + external authorization**, not autonomous self-modification. Existing `reasoning-invention-v1`, C8 schemas and `reasoning-episode-v1` identities remain unchanged.
