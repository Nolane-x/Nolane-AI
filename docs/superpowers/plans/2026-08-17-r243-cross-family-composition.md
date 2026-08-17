# R2.43 Counterexample-Guided Cross-Family Macro Composition — Implementation Plan

**Goal:** Add a bounded synthesis layer that composes two independently learned, trusted predicate macros into a new boolean verifier probe for a target family, while preserving R2.41 quarantine semantics and requiring counterexample survival.

**Architecture:** R2.43 sits above R2.39 `ProbeMacro`/typed probe DSL and consumes R2.41 `MacroCompetitionState`. It instantiates each macro only within an explicit family argument scope, ranks applications by posterior partition entropy, synthesizes cross-macro Boolean compositions, requires positive information synergy over the best parent, semantic-deduplicates candidates, and filters candidates through a counterexample callback. It abstains when two trusted macros are unavailable or all candidates are falsified.

**Causal protocol:** Frozen dev seeds 1201–1283 and held-out seeds 1301–1327. Source abstractions are distinct (`AND` and `OR`) and the target structure is new: `AND(AND(a,b), OR(c,d))`. Target atoms are renamed per episode. Candidate correctness is checked against the complete 16-row Boolean truth table. Raw recombination is not forbidden; its semantic search-space size is reported as a bounded efficiency baseline.

## Tasks

1. Add failing tests for positive cross-family information synergy, quarantine exclusion, determinism, and counterexample fallback.
2. Implement `cogcoder/r243_macro_composition.py` minimally until focused tests pass.
3. Add frozen multi-episode benchmark with exhaustive truth-table counterexample checking and raw recombination-space baseline.
4. Run focused R2.43 tests locally, then run R2.39/R2.41 compatibility tests in GitHub Actions.
5. Only after fresh CI evidence, create accepted evidence/release docs, complete repository ZIP, SHA-256 manifest, and persist the ZIP to Library.

## Acceptance boundary

Accept only if all frozen held-out episodes are exact, false accepts are zero, every accepted composition has positive information synergy over both parents, no quarantined macro can participate, deterministic replay matches exactly, and the CI compatibility gate is green. This milestone does **not** claim universal program synthesis, raw-reasoning inferiority, or scientific AGI attainment.
