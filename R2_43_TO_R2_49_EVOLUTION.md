# Nolane-AI R2.43 → R2.49 capability evolution

This document records the bounded capability progression completed on 2026-08-17.

- **R2.43 — Cross-family composition:** learned predicate macros can be composed under counterexample filtering instead of treated as terminal actions. Frozen result: 6/6 exact; bounded search 484 semantic candidates → 4 learned-composition candidates.
- **R2.44 — Recursive abstraction ladder:** successful compositions can be promoted across episodes and reused recursively with ancestry/quarantine propagation. Generation 2, arity 8, 6/6 exact on 256-row worlds; flat 40,320 bindings vs ≤11 hierarchical candidates in the role-scoped protocol.
- **R2.45 — Role-free binding:** removed privileged per-macro atom scopes; all Boolean base macros see the same opaque 8-atom pool with role permutation. 6/6 exact; flat 40,320 vs ≤1,067 candidates, ≥37.79× contraction.
- **R2.46 — Sparse feedback:** replaced dense truth-table guidance with 8 target-independent tests plus fail-fast counterexamples. Fixed epistemic alias collapse by preserving structural aliases with distinct atom footprints. 6/6 exact; at most 13/256 labels observed before final certification.
- **R2.47 — Executable Python patch CEGIS:** learned 13 generic AST edit macros from renamed before/after demonstrations, composed three edits, compiled Python, and learned from sparse failing tests. 6/6 exact; ≤6/729 observed tests; final 729-test certification.
- **R2.48 — Contextual multi-site localization:** learned edit type plus a fixed def-use/control-flow role so the system edits the right AST site rather than every matching site. Contextual system 6/6 while R2.47 global-apply baseline is 0/6; ≤5/2,401 observed tests.
- **R2.49 — Relational context predicate induction:** replaced the single fixed localization role with a minimal predicate learned from changed positive sites and unchanged decoys using identifier-invariant relational program-graph features. The learner selects `guard_body:returns_lineage`; R2.49 is 6/6 while the R2.48 fixed-context baseline is 0/6 on nested/deep alias reshaping.

## Acceptance boundary

R2.49 is accepted as a **bounded capability milestone**, not as AGI convergence. Nolane World W5 remains closed. The next scientifically important frontier is to learn/expand the relational feature vocabulary itself and transfer to interprocedural, multi-file, externally sourced repository bugs with incomplete/noisy tests and open-ended edit structures.
