# C9 Reasoning Ecology Runtime Design

## Status

This design extends the canonical `external.reasoning_invention` family from v0.0.2 to v0.0.3 with an additive episode/runtime protocol. Existing C1 and C8 wire schemas remain unchanged.

Nolane World 0.12.0 is design provenance only. Nolane AI owns the runtime types, identities, state transitions, replay validation and authority boundaries described here.

## Problem

C1–C8 make the important reasoning artifacts explicit and tamper-evident: invention receipts, epistemic frontiers, metareasoning proposals and budgets, Pareto control decisions, fresh-context reviews, closed-loop evaluation and descriptive meta-learning evidence.

The remaining gap is temporal integrity. Today a caller can construct a valid frontier A and a valid frontier B, but the C layer has no canonical artifact proving that B is the authorized successor of A because a specific C8 action was selected from a specific Pareto control decision, consumed a specific amount of reasoning budget, and produced a specific evidence set. There is also no canonical replay rule proving that a serialized multi-step reasoning trajectory reconstructs exactly the same current frontier and remaining budget.

That gap matters because otherwise a downstream caller could accidentally or adversarially:

- reuse a stale control decision after the frontier changed;
- spend the same action authority twice;
- reset or under-report a reasoning budget between steps;
- silently swap objectives, Cognitive Library snapshots or hard constraints mid-episode;
- claim that a critical unknown was resolved without evidence;
- restore a forged current frontier or terminal status from serialized state;
- treat compute exhaustion as successful epistemic closure.

C9 closes that gap without becoming a planner, executor, Assurance governor or mutable knowledge store.

## Design provenance from Nolane World

Three World mechanisms inform this design:

1. **Replay integrity:** a snapshot is valid only when it matches the exact journal prefix that produced it. C9 therefore reconstructs the episode from its root and ordered transition chain instead of trusting serialized counters or a claimed current frontier.
2. **Formal transition fencing:** stale epoch/fence operations and reused operation IDs are rejected. C9 analogously binds every transition to the exact current frontier, exact current budget and unused control/action identities.
3. **Critical unknown veto:** unresolved decision-overturning unknowns block ordinary closure. C9 therefore preserves C8 `ABSTAIN_UNRESOLVED` semantics and never converts budget exhaustion into acceptance.

These are conceptual inputs, not imports or runtime dependencies.

## Architecture

C9 adds one focused module:

`nolane/external_core/reasoning_episode.py`

It composes existing immutable C8 objects. It does not modify the semantics of `ReasoningFrontier`, `MetareasoningBudget`, `ReasoningControlDecision` or `ReasoningActionProposal`.

```text
root ReasoningFrontier
        |
        v
 open_reasoning_episode
        |
        v
  ReasoningEpisode -------------------------------+
        |                                          |
        | current_budget                           | canonical replay
        v                                          |
 plan_next_reasoning_actions                       |
        |                                          |
        v                                          |
 ReasoningControlDecision                          |
        | select one Pareto-authorized proposal    |
        v                                          |
 external evidence-producing work                  |
        |                                          |
        v                                          |
 next ReasoningFrontier + evidence IDs             |
        |                                          |
        v                                          |
 advance_reasoning_episode -> FrontierTransition --+
        |
        +--> next generation / next budget
        |
        +--> budget overrun => fail-closed abstention
        |
        +--> terminal C8 decision => close_reasoning_episode
```

No arrow grants execution or promotion authority.

## Component revision

C9 advances only `external.reasoning_invention` from canonical revision `2` to `3`, exposed as component version `0.0.3`.

All modules in the Reasoning/Invention family report `COMPONENT_VERSION = "0.0.3"`:

- `reasoning_invention.py`
- `reasoning_evaluation.py`
- `reasoning_frontier.py`
- `reasoning_metacontrol.py`
- `reasoning_review.py`
- `reasoning_meta_learning.py`
- `reasoning_episode.py`

Existing schema identifiers remain unchanged. The new schema is `reasoning-episode-v1`.

## ReasoningEpisodeStatus

The episode has four states:

- `ACTIVE`
- `HALTED_NO_FURTHER_VALUE`
- `ABSTAINED_UNRESOLVED`
- `ABSTAINED_BUDGET_OVERRUN`

There is intentionally no `ACCEPTED`, `SUCCESS`, `PROMOTED` or equivalent state.

`HALTED_NO_FURTHER_VALUE` means only that C8 found no reasoning action worth its declared marginal cost and no decision-overturning unknown remained. It does not validate the underlying engineering claim.

## ReasoningFrontierDelta

A frontier delta is an immutable, content-addressed explanation of the semantic set difference between two consecutive frontiers.

It contains:

- `previous_frontier_id`
- `next_frontier_id`
- `resolved_unknown_ids`
- `introduced_unknown_ids`
- `retired_hypothesis_ids`
- `introduced_hypothesis_ids`
- `revised_hypothesis_ids`
- `retired_assumption_ids`
- `introduced_assumption_ids`
- `evidence_ids`
- derived `delta_id`

A stable hypothesis ID can be present in both frontiers but change its canonical rival content. That is a **revision**, not a retire+introduce pair. The runtime compares `rival_id` under the stable `hypothesis_id` to detect this case.

`evidence_ids` must be non-empty. A semantic frontier mutation without any evidence identity is rejected.

The delta is derived by the runtime and must exactly match the before/after frontiers. Serialized restoration recomputes it; callers cannot forge resolution labels.

## Continuity invariants inside one episode

Every successor frontier must preserve:

- `reasoning_receipt_id`
- `objective_id`
- `cognitive_library_digest`
- `hard_constraint_ids`
- `branch_budget`

The episode treats changes to those fields as a new epistemic context requiring a new root episode. In particular, hard-constraint drift is not a normal C reasoning transition because D owns goal/design authority.

Unknowns, rivals and assumptions may change only through an evidence-carrying transition.

## ReasoningFrontierTransition

Each transition binds:

- stable `episode_key`
- exact monotonically increasing `generation`
- exact `previous_frontier_id`
- full immutable `next_frontier`
- exact C8 `ReasoningControlDecision`
- exact selected `ReasoningActionProposal`
- exact derived `ReasoningFrontierDelta`
- `observed_cost`
- derived `budget_overrun`
- derived `transition_id`

The transition is content addressed. Restored state must reproduce the exact transition identity.

### Authorization checks

`advance_reasoning_episode` accepts a transition only when all of these hold:

1. the episode is `ACTIVE`;
2. the supplied control decision is `CONTINUE`;
3. control `frontier_id` equals the episode current frontier;
4. control `budget_id` equals the episode's exact current derived budget;
5. selected action `frontier_id` equals the current frontier;
6. selected action ID is one of the exact control decision's Pareto action IDs;
7. selected action's declared estimated cost fits the remaining declared budget;
8. neither the control decision ID nor action ID has already been consumed in the episode;
9. the successor frontier satisfies all episode continuity invariants;
10. the derived frontier delta contains at least one evidence identity.

This makes stale decisions fail closed after one advancement, even when their objects remain individually valid.

## Budget conservation

`ReasoningEpisode` owns immutable initial budget parameters:

- `action_limit`: positive integer;
- `cost_limit`: positive finite number;
- `minimum_actionable_gain`: finite score in `[0, 1]`.

Spent actions and spent cost are never caller-supplied fields. They are derived from the transition chain:

- `spent_actions = len(transitions)`
- `spent_cost = sum(transition.observed_cost)`

The current budget is derived as:

- `remaining_actions = max(action_limit - spent_actions, 0)`
- `remaining_cost = max(cost_limit - spent_cost, 0.0)`

and is bound to the current frontier.

### Estimated cost versus observed cost

Before a transition executes externally, the selected proposal's `estimated_cost` must fit the current remaining cost. After evidence-producing work completes, the caller supplies the observed cost.

Observed cost may exceed the remaining cost because estimation can be wrong. C9 records the real cost rather than clipping or rewriting history. If observed cost exceeds the pre-transition remaining cost, the transition is still recorded but the episode automatically becomes `ABSTAINED_BUDGET_OVERRUN` and cannot advance again.

This preserves evidence of the overrun while preventing further reasoning authority from being manufactured out of a negative budget.

Exactly exhausting a budget is different from overrunning it. An exactly exhausted episode may remain active long enough to derive a zero-budget C8 control decision, which must then be explicitly closed as `HALT_NO_FURTHER_VALUE` or `ABSTAIN_UNRESOLVED` according to C8 semantics.

## ReasoningEpisode

An episode binds:

- `root_frontier`
- `current_frontier`
- initial budget parameters
- ordered transition chain
- optional terminal control decision
- derived status
- stable `episode_key`
- derived full-state `snapshot_id`

### Stable episode key

`episode_key` is derived only from the root frontier and initial budget contract. It identifies one logical reasoning episode across generations.

### Snapshot identity

`snapshot_id` hashes the complete canonical episode state, including transition chain, current frontier and terminal state. It changes after every valid transition.

Consumers needing a particular generation must bind the exact `snapshot_id`, not only the stable `episode_key`.

## Open, advance and close operations

### `open_reasoning_episode`

Creates generation zero from one root frontier and one explicit initial budget contract. No transition exists yet and status is `ACTIVE`.

### `advance_reasoning_episode`

Records exactly one authorized reasoning transition and returns a new immutable episode snapshot. It never calls tools, experiments, reviewers or models.

The caller is responsible for obtaining real evidence through the relevant subsystem and then supplying the evidence identities and successor frontier.

### `close_reasoning_episode`

Accepts only a terminal C8 control decision bound to the exact current frontier and exact current budget.

- C8 `HALT_NO_FURTHER_VALUE` maps to episode `HALTED_NO_FURTHER_VALUE`.
- C8 `ABSTAIN_UNRESOLVED` maps to episode `ABSTAINED_UNRESOLVED`.
- C8 `CONTINUE` is rejected.

A budget-overrun episode is already terminal and cannot be manually relabeled.

## Replay and persistence

`ReasoningEpisode.to_state()` serializes the complete root, transition chain, current frontier and terminal state.

`ReasoningEpisode.from_state()` does not trust claimed derived fields. It must:

1. restore the root frontier;
2. reconstruct the initial budget contract;
3. start a fresh generation-zero episode;
4. replay transitions in order through the same internal transition verifier used by live advancement;
5. verify generation continuity and unique consumed control/action identities;
6. recompute each frontier delta;
7. recompute budget usage and overrun status;
8. apply the terminal control decision if present;
9. require reconstructed current frontier, status, `episode_key`, transition IDs and `snapshot_id` to match the serialized state exactly;
10. reject any non-canonical ordering or extra fields.

This mirrors replay-prefix integrity: a snapshot is evidence only when the event/transition prefix deterministically reconstructs it.

## Stale-state fencing

C9 has no wall-clock epoch and does not need one. The effective fence is the pair:

`(current_frontier_id, current_budget_id)`

Every control decision is already bound to both. Once a transition changes the frontier or budget, the old pair can no longer authorize another transition.

This avoids adding a redundant mutable epoch counter whose correctness would itself need to be trusted.

## Interaction with C8 reviews and evaluation

C9 intentionally treats transition evidence as opaque stable IDs. Examples include:

- experiment verification receipt IDs;
- causal challenge/program evidence IDs;
- fresh-context review receipt IDs;
- C7 evaluation receipt IDs;
- externally captured observation/evidence IDs.

C9 does not reinterpret their authority. It only records that they were cited to justify the frontier transition.

## Authority boundaries

C9 MUST NOT:

- invoke tools, shells, models or E Acting;
- mutate Cognitive Library state;
- create Capability Acquisition lifecycle state;
- accept or revoke Transfer/Meta reuse;
- mint Assurance;
- mutate D Goal/Design state;
- mutate Neural state;
- choose a hidden scalar optimum among Pareto actions;
- claim truth from halt, abstention or budget exhaustion.

C9 is a proof-carrying temporal composition layer over C artifacts, not a new governor.

## Fail-closed rules

C9 rejects:

- empty identities;
- bool-as-number budget/cost smuggling;
- NaN or infinity;
- non-positive action or cost limits;
- minimum actionable gain outside `[0, 1]`;
- advancing a terminal episode;
- non-`CONTINUE` decisions used for advancement;
- `CONTINUE` decisions used for closure;
- wrong-frontier or wrong-budget control decisions;
- actions not present in the control Pareto set;
- actions bound to another frontier;
- selected action estimated cost above remaining budget;
- duplicate/reused action IDs;
- duplicate/reused control-decision IDs;
- successor changes to receipt/objective/library/hard-constraints/branch-budget;
- evidence-free frontier changes;
- forged frontier delta identities;
- non-monotonic or skipped generation numbers;
- transition chains whose predecessor frontier is not the reconstructed current frontier;
- forged current frontier, status, terminal decision, episode key, transition ID or snapshot ID;
- any replay state that cannot be reproduced exactly.

## Testing strategy

C9 is developed RED → GREEN.

### RED proof

Before `reasoning_episode.py` exists, commit tests that require:

- episode open/budget derivation;
- authorized advancement and exact semantic delta;
- stale control rejection;
- Pareto authorization;
- continuity fencing;
- budget overrun behavior;
- terminal close semantics;
- canonical replay and forged-state rejection;
- authority backdoor absence;
- coherent v0.0.3 revision cutover.

Run those tests in hosted GitHub Actions and retain the exact failure evidence showing the missing runtime/version cutover.

### GREEN acceptance

After minimal production implementation:

1. C9 focused tests pass;
2. C8 tests remain green;
3. full `tests/test_refoundation_*.py` passes on Python 3.11 and 3.13;
4. 67/67 dossiers and repository audit remain fresh;
5. downstream Truth/Knowledge and organization/campaign/execution regressions remain green;
6. exact PR synthetic merge is verified after the last resync with current `main`;
7. historical frozen-release failures, if any, are classified separately from C behavior.

## Non-goals

C9 does not implement autonomous tool execution, a task planner, a scheduler, a global utility function, self-modifying meta-policy, arbitrary branch search, model training, capability promotion, transfer acceptance or final Assurance. It makes the temporal reasoning trajectory auditable, budget-conserving, stale-safe and replayable.