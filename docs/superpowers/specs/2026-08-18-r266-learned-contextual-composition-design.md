# R2.66 Learned Contextual Causal Composition — Design

## Status
Approved continuation of the previously designed contextual-composition lineage after accepted R2.65. This branch starts from exact accepted `main` commit `768e500d6b3e8d1d8ec747e37aae6302ab6747d1`; it does not rewrite R2.65 production code.

## Parent and capability gap

R2.65 can induce a missing target-specific repository binop replacement primitive from a finite host-authorized grammar, but the causal-experiment line still composes complementary probe outputs only through host-provided fixed one-step operators. That leaves a solution channel in which the host supplies the composition semantics.

R2.66 removes that channel inside a bounded authority boundary: discover two complementary pure-input interventions, synthesize a deterministic contextual expression over their probe outputs plus only original positions untouched by both interventions, prove neither probe alone suffices under the same grammar, prove no inherited fixed R2.62 composition suffices, synthesize executable probe expressions, and verify the fully substituted program on separate cases.

## Authority boundary

R2.66 does not invent arbitrary primitive semantics. It uses the finite trusted expression DSL already present in R2.56: scalar fields/constants, unary `abs/neg/not`, trusted binary numeric/comparison/boolean operators, and `IfElse`. Added trainable parameters: exactly 0.

A composition program may reference an original field only when neither selected intervention overwrites that positional field. External names are canonicalized by position before search, so lexical field names cannot influence identity.

## Core invariants

1. **No intervened-value smuggling.** Composition may see probe outputs and only positions untouched by both interventions.
2. **Two-probe necessity.** Matched single-probe composition searches must both fail.
3. **Inherited fixed-op falsifier.** `add/sub/rsub/mul/min/max` over the same selected probe pair must all fail as universal explanations.
4. **Probe executability.** Each selected intervention output must itself be synthesized from positions left free by that intervention.
5. **Rename invariance.** Pure field renaming preserves program identity.
6. **Positional-role invariance.** Field-order permutations may change positional IDs, but the selected semantic intervention roles must remain equivalent under roomy matched budgets.
7. **Hard accounting.** Candidate ledgers and oracle calls are bounded and explicit; invalid/non-finite oracle behavior fails closed.
8. **Terminal verification.** A fully substituted program must pass separate validation/heldout contexts before acceptance.
9. **No false terminal accept.** Every negative/falsifier path abstains.

## Search architecture

The contextual-expression synthesizer performs semantic deduplication over atoms and one-step trusted transforms, then recursively constructs bounded `IfElse` programs from boolean semantic predicates and useful leaves. This makes small contextual routers reachable without enumerating the full generic Cartesian DSL.

Interventions are content-addressed and profiled on discovery plus validation contexts. Candidate intervention pairs are evaluated under a per-pair cap and a global composition budget. Passing programs are ranked by expression depth, expression cost, semantic probe-output identity, composition digest, then intervention IDs. The selected program must use both probe outputs.

## Authored causal family

Use a signed band selector:

`band_select(x, lo, hi, left, middle, right)`

- `x < lo` -> `left`
- `lo <= x <= hi` -> `middle`
- `x > hi` -> `right`

Mixed-sign branch values make all inherited fixed numeric compositions fail. The causal intervention pair zeros complementary branch outputs; their union leaves gate variables and the middle value untouched. A learned conditional must route between the two probes while each singleton ablation remains insufficient.

Freeze canonical-name, rename-replay, and positional-permutation cases plus negative budget, non-finite-oracle, missing-context, and hidden-terminal-contradiction cases.

## External transfer

Retain the independently sourced pinned `WarrenWeckesser/ufunclab@f1fbe6769850823a1976ccc28d14cd966130b645` `ufunclab.step` callable-I/O transfer from the deferred lineage. Re-run it only after rebasing on R2.65; do not reuse old pass results as current evidence.

The external source is researcher-selected, so it does not establish blind task discovery.

## Verification and release

- TDD RED on exact R2.65 parent before the R2.66 production module exists.
- Hosted Python 3.11/3.13 focused checks.
- Exact authored Phase-A recomputation.
- Fresh pinned external callable-I/O recomputation.
- Protected R2.65→R2.41 lineage.
- Independent challenger preservation.
- Source/evidence lock only after production is final.
- Nolane World 0.8.0 audit; W5 remains false unless runtime gates genuinely pass.
- Complete repository ZIP, SHA-256, integrity test, GitHub artifact, independent download verification, and Library persistence.

## Claim boundary

R2.66 may claim only bounded learned contextual composition of two complementary pure-input experiments over a finite trusted DSL, with no access to overwritten values, matched singleton/fixed-op causal baselines, executable probe synthesis, positional invariance, bounded accounting, terminal verification, and a fresh pinned external transfer.

It may not claim primitive-language invention, 3+ intervention scaling, stateful/filesystem/network experiments, blind external task discovery, unrestricted program synthesis, broad repository autonomy, W5 convergence, frontier-model equivalence, or AGI.
