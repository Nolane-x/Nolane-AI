# Candidate Synthesis v0.0.3 — Progressive Multi-Depth Frontier Search

Status: approved design, implementation not started
Base: `main@8eac73b4cd7cec388b77363cfb8e909261025285`
Component: `external.candidate_synthesis`
Target component version: `0.0.3`
State schema: `candidate-synthesis-v1` (unchanged)

## 1. Purpose

Candidate Synthesis v0.0.2 can deterministically search ordered unary pairs from a canonical unordered source pool. v0.0.3 extends that capability to finite multi-depth composition while preserving every Refoundation authority boundary.

The goal is not to make Candidate Synthesis judge truth, usefulness, safety, or promotion-worthiness. The goal is narrower: allow the discovery layer to form a deeper standalone proposal when all shallower composition frontiers fail to yield a novel candidate.

The core rule is:

> Use the shallowest fully searched synthesis frontier that can produce at least one novel proposal.

This is a progressive-search policy, not a claim that shallow candidates are semantically superior. It avoids introducing an unverified cross-depth utility heuristic into discovery.

## 2. Scope

### In scope

- Add a new `SynthesisMode.PROGRESSIVE_MULTI_DEPTH_SEARCH`.
- Canonicalize its source pool exactly as bounded search does.
- Enumerate ordered source sequences without replacement at depths `2..len(source_pool)`.
- Search one complete depth frontier at a time.
- Preserve the existing hard global hypothesis budget.
- Select the deterministic best novel candidate within the first depth that produces any novel candidates.
- Fully expand each hypothesis against the exact Cognitive Library vocabulary before constructing the final `CapabilityCandidate`.
- Preserve Cognitive Library immutability and lifecycle separation.
- Preserve v0.0.1 composition and v0.0.2 pair-search behavior exactly.

### Out of scope

- Beam search, best-first search, learned search policy, stochastic search, or score-guided frontier expansion.
- Reusing a source more than once inside one hypothesis.
- Feeding a generated intermediate candidate back into the same synthesis call as a new source.
- Mutation of Cognitive Library, Capability Acquisition state, Assurance state, or Neural state.
- Independent-challenge or final-Assurance evidence in synthesis generation or ranking.
- Claims about semantic correctness or task utility beyond existing structural candidate metadata.
- New caller-controlled depth limits or search-policy fields.

## 3. Compatibility and versioning

Target:

- `COMPONENT_VERSION = "0.0.3"`
- implementation ledger revision for `external.candidate_synthesis` advances from 2 to 3.
- `SCHEMA_VERSION = "candidate-synthesis-v1"` remains unchanged.

A schema bump is intentionally not required. The new mode is completely determined by fields already serialized in v1:

- mode
- canonical source pool
- generation budget
- evidence/provenance IDs
- candidates considered
- selected candidate identity/fingerprint or abstention reason

The mode itself fixes the depth policy to `2..len(source_pool)`, so no new serialized field is needed.

Existing v1 request and receipt states must continue to decode canonically. Existing modes must preserve their identities and behavior.

## 4. Source-pool semantics

For `PROGRESSIVE_MULTI_DEPTH_SEARCH`, `source_item_ids` is an unordered source pool.

Construction rules:

1. Require at least two distinct source IDs.
2. Reject duplicate source IDs.
3. Canonicalize by sorted abstraction identity.
4. Resolve every source against the exact current Cognitive Library vocabulary before search.
5. Every source must be unary (`parameter_count == 1`).
6. Every source must pass the existing reserved synthesis-field collision check.
7. Missing, non-unary, or reserved-field-collision sources retain fail-closed behavior.

Caller ordering is therefore non-semantic in this mode.

## 5. Search-space semantics

Let the canonical source pool contain `n` sources.

The progressive search space is the ordered permutations without replacement for each depth:

`P(n, 2), P(n, 3), ..., P(n, n)`.

For canonical pool `[A, B, C]`, the deterministic frontier structure is:

Depth 2:

- `A -> B`
- `A -> C`
- `B -> A`
- `B -> C`
- `C -> A`
- `C -> B`

Depth 3:

- `A -> B -> C`
- `A -> C -> B`
- `B -> A -> C`
- `B -> C -> A`
- `C -> A -> B`
- `C -> B -> A`

Within a hypothesis, source sequence order remains semantic.

Source reuse is forbidden in v0.0.3. Therefore chains such as `A -> A`, `A -> B -> A`, or indefinite `A -> A -> ...` are outside the search space. This keeps the frontier finite, auditable, and exactly computable from the request.

## 6. Progressive-depth rule

The engine searches depth frontiers in ascending depth order.

For each depth `d`:

1. Enumerate hypotheses deterministically.
2. Apply the global generation budget before filtering.
3. Generate and fully expand every considered hypothesis.
4. Skip source-equivalent, already-installed, and semantic duplicate candidates.
5. Accumulate all novel candidates discovered within that depth.
6. If the entire depth frontier is completed and at least one novel candidate exists, rank only those candidates and return the best one.
7. Only if the entire depth frontier is completed and contains no novel candidate may the engine proceed to depth `d + 1`.

A partially searched depth never authorizes descent to a deeper depth.

This prevents the budget from silently changing search semantics. The engine may return the best candidate from a partially searched current depth if a candidate was actually observed there, but it may not claim that deeper depths were unnecessary or exhausted.

## 7. Candidate construction

Each hypothesis uses the existing canonical composition path:

1. Start with the reserved synthesis parameter field.
2. Wrap transient `AbstractionCall` nodes in hypothesis sequence order.
3. Fully expand the transient IR against the exact current Cognitive Library vocabulary.
4. Bind the reserved field to `TemplateParam(0)`.
5. Compute support-task IDs as the sorted union of support-task IDs from all sources in the hypothesis.
6. Create a standalone unary `LearnedAbstraction` using `make_abstraction(...)`.
7. Convert the resulting standalone abstraction through `CapabilityCandidate.for_learned_abstraction(...)`.

Generated intermediates are never inserted into Cognitive Library or reused as same-call vocabulary entries.

Thus `A -> B -> C` is a single direct hypothesis whose final expanded payload is standalone. It is not implemented as `X = A -> B`, install/use `X`, then `X -> C`.

## 8. Hard budget accounting

`generation_budget` remains a global hard hypothesis cap for the entire synthesis call.

Budget accounting occurs before source-equivalence filtering, installed-candidate filtering, or semantic deduplication.

For every enumerated hypothesis that the engine attempts:

1. Check whether the global count has reached `generation_budget`.
2. If yes, stop generation immediately.
3. Otherwise increment `candidates_considered`.
4. Only then generate and filter the hypothesis.

Invariant:

`0 <= candidates_considered <= generation_budget`.

If the total bounded search space contains fewer hypotheses than the budget, `candidates_considered` equals the actual number of hypotheses enumerated, not the budget.

A budget of zero performs no generation.

## 9. Ranking

Ranking remains structural and deterministic. No Assurance signal, challenge result, final-verification evidence, or lifecycle state participates.

Within the selected depth frontier, lower tuple wins:

1. `generated.template.cost` ascending
2. `-len(generated.support_task_ids)` ascending (broader support first)
3. `candidate.candidate_id` ascending as canonical tie-break

Candidates from different depths do not compete in one global ranking.

The first completely searched depth with one or more novel candidates is the selected depth. This prevents a deeper candidate from winning merely because of an arbitrary cross-depth heuristic and prevents shallow structural cost from making multi-depth search useless in practice.

## 10. Novelty and deduplication

For every considered hypothesis:

- If generated abstraction identity equals an original source identity, skip it.
- If that exact abstraction is already installed in Cognitive Library, skip it.
- If a library abstraction has the generated identity but different payload, raise the existing collision error.
- Convert novel generated abstractions to `CapabilityCandidate`.
- Deduplicate by canonical candidate identity across the entire synthesis call, not only within one depth.

Deduplication does not refund budget. A duplicate was still a considered hypothesis.

## 11. Abstention semantics

Canonical abstention meanings for the new mode:

### `generation_budget_exhausted`

Used when no candidate can be returned and the generation budget is exhausted before the complete bounded search space has been proven exhausted.

This means: search stopped due to compute bound, not because the configured frontier was fully disproven.

Budget zero is a special case of this reason with `candidates_considered == 0`.

### `no_novel_candidate`

Used only when the engine has completely enumerated every allowed frontier from depth 2 through depth `len(source_pool)` and no novel candidate exists.

This is strictly stronger than budget exhaustion.

Existing abstention reasons for source validation and existing modes remain unchanged.

If a novel candidate exists in the current explored depth before the budget is reached, the engine may return the best novel candidate among the hypotheses actually considered in that depth. The receipt must bind the actual count. It must not claim that the remainder of the depth was searched.

## 12. Receipt and identity invariants

The existing `SynthesisReceipt` shape remains unchanged.

Its canonical semantic identity already binds:

- schema version
- synthesis mode
- objective
- canonical source pool
- evidence IDs
- experiment-receipt IDs
- causal-program IDs
- generation budget
- actual candidates considered
- winning candidate ID and semantic fingerprint, or abstention reason

For the new mode, these fields are sufficient because depth policy and frontier order are protocol constants defined by the mode and component version.

Tampering with budget accounting, selected identity, fingerprint, abstention, mode, or pool must continue to invalidate receipt identity.

## 13. Authority boundary

Candidate Synthesis v0.0.3 remains a stateless discovery proposal generator.

It may:

- resolve canonical Cognitive Library sources;
- compose transient synthesis IR;
- enumerate a finite search frontier;
- generate standalone proposals;
- deduplicate and structurally rank proposals;
- abstain;
- emit content-addressed receipts.

It must not:

- persist a generated abstraction into Cognitive Library;
- admit a candidate;
- enter probation;
- run Assurance;
- promote or quarantine;
- mutate Neural state;
- consume `INDEPENDENT_CHALLENGE` or `FINAL_ASSURANCE` evidence for generation, expansion, pruning, ranking, or selection;
- create hidden mutable same-call vocabulary from generated proposals.

The engine must continue to snapshot Cognitive Library digest before synthesis and verify that the digest is unchanged on every result path.

A proposal enters lifecycle state only through an explicit separate caller invocation of `CapabilityAcquisitionGovernor.admit(...)`, and that operation must still produce only `CapabilityState.CANDIDATE`.

## 14. Determinism requirements

For equal semantic input state:

- caller permutation of the source pool must not alter request canonical state;
- hypothesis enumeration order must be deterministic;
- depth progression must be deterministic;
- global budget truncation must be deterministic;
- semantic dedup must be deterministic;
- ranking must be deterministic;
- winning candidate identity and synthesis receipt identity must be deterministic.

No random seed, wall-clock state, execution-order race, or noncanonical mapping iteration may affect the result.

## 15. Required RED contracts

Implementation must begin with failing tests that prove the intended missing capability rather than setup or collection failure.

The RED suite must lock at least these contracts:

1. Component advances to v0.0.3 while schema stays `candidate-synthesis-v1`.
2. New progressive mode exists and canonicalizes unordered source pools.
3. Existing v0.0.1 composition behavior remains unchanged.
4. Existing v0.0.2 bounded pair-search behavior remains unchanged.
5. Depth-2 frontier is searched before depth 3.
6. If every depth-2 result is already installed, the engine can produce a standalone depth-3 candidate.
7. A depth-3 candidate is built directly from original sources; no intermediate generated abstraction appears in Cognitive Library.
8. Source reuse inside a hypothesis is absent.
9. The hard global hypothesis budget spans depth boundaries correctly.
10. A budget ending within depth 2 cannot authorize search at depth 3.
11. Caller source-pool reordering cannot change candidate or receipt identity.
12. Ranking within one depth remains deterministic under the existing structural tuple.
13. Deduplication works across distinct source sequences that collapse to the same semantic candidate.
14. Installed candidates are skipped without refunding budget.
15. Zero budget abstains with `generation_budget_exhausted` and zero considered.
16. Budget exhaustion before complete frontier exhaustion is distinguishable from full-space `no_novel_candidate`.
17. Full search through depth `n` with no novel candidate emits `no_novel_candidate`.
18. Challenge and final-Assurance evidence remain rejected before generation.
19. Search does not mutate Cognitive Library or Capability Acquisition state.
20. Explicit post-synthesis admission still yields exactly `CapabilityState.CANDIDATE`.
21. Request and receipt v1 round-trip remains canonical.
22. Receipt tamper rejection covers progressive-mode budget/result state.
23. Final returned candidate is standalone-decodable with no unresolved `AbstractionCall`.

RED evidence must show failures caused by the missing v0.0.3 behavior/version/mode, not test bugs.

## 16. GREEN and verification requirements

After RED is proven:

- implement only the minimum production changes needed for the approved semantics;
- run focused progressive-search tests;
- run all existing Candidate Synthesis tests;
- run component version/implementation metadata tests;
- run `git diff --check` or equivalent repository whitespace verification;
- run the canonical Refoundation workflow on Python 3.11 and 3.13 from the exact final feature head;
- require dossier freshness, repository audit, all Refoundation contracts, zero-loss evidence generation, broad coding-AGI regressions, and frozen Neural R2.3 verification to pass;
- remove any temporary workflow/test carrier before the final exact-head CI run;
- open the implementation PR non-draft from the beginning;
- merge only with an expected-head guard;
- post-merge verify that `main` contains the exact tested feature tree and v0.0.3 production constants.

No GREEN claim is valid from a different head than the one proposed for merge.

## 17. Files expected to change

The implementation should remain tightly scoped. Expected files are:

- `nolane/external_core/candidate_synthesis.py`
- `nolane/metadata/component_versions.py`
- `tests/test_refoundation_component_versions.py`
- existing Candidate Synthesis tests only where version expectations must advance
- one new focused progressive-frontier test module
- `CURRENT/EXTERNAL_CORE.md`

Additional production files require an explicit design justification before implementation.

## 18. Acceptance criteria

v0.0.3 is complete only when all of the following are true:

- Progressive multi-depth synthesis can generate a novel standalone depth-3-or-greater proposal when every shallower frontier contains no novel proposal.
- No source is reused in one hypothesis.
- No generated intermediate enters the library or same-call source vocabulary.
- Search is globally hard-budgeted and deterministic.
- The engine never descends past a partially searched shallower frontier.
- Cross-depth selection uses shallowest successful complete frontier, not a fabricated utility score.
- Discovery-only evidence separation remains intact.
- Lifecycle authority remains outside Candidate Synthesis.
- v0.0.1 and v0.0.2 behavior regressions remain green.
- Serialization schema stays v1 and remains canonical.
- Exact-head canonical CI is green on Python 3.11 and 3.13.
- The merged `main` tree is verified to contain the exact tested implementation.

## 19. Deferred next frontier

Only after v0.0.3 is empirically useful should Candidate Synthesis consider a v0.0.4 search-policy layer such as beam/best-first expansion, reuse, learned heuristics, or evidence-informed proposal prioritization. Those features would alter which hypotheses become observable under bounded compute and therefore deserve a separate authority and evaluation design rather than being smuggled into v0.0.3.
