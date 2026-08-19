# R2.67 Verified Three-Probe Causal Composition — Design

## Status

Proposed direct continuation from accepted R2.66 merge commit `e2eef08f15e7c0a5e79f58579282db90c157cb4a` on `main`.

R2.67 is intentionally narrow: it removes the **exactly-two-intervention ceiling** from the accepted causal-composition line for one bounded, falsifiable three-probe capability. It does not introduce stateful effects, network/filesystem experiments, unbounded search, or arbitrary primitive-language invention.

## Parent capability and gap

R2.66 can autonomously discover two complementary pure-input interventions, learn a contextual composition over their outputs plus fields untouched by both interventions, prove neither singleton probe suffices, synthesize executable probe expressions, and independently re-observe the selected probes on terminal contexts before granting authority.

Its accepted claim boundary explicitly excludes `3+ intervention scaling`.

R2.67 targets exactly that boundary. The system must discover **three** semantically complementary interventions and synthesize one verified program whose target behavior provably requires all three selected probe outputs under the same bounded DSL and evidence budget.

## Capability statement

Given:

- a pure deterministic oracle over a finite positional schema,
- discovery, validation, and disjoint terminal contexts,
- a finite set of authorized intervention anchor values,
- the existing trusted R2.56 expression DSL,
- hard intervention, composition, ablation, and oracle budgets,

R2.67 may return a three-probe causal program only when all of the following hold:

1. three legal nondegenerate intervention profiles are selected without a host supplying their semantic identities;
2. a single composition expression exactly matches the learning evidence and uses `__p0`, `__p1`, and `__p2`;
3. no one-probe or two-probe ablation can solve the same evidence under the matched ablation grammar and declared budgets;
4. every selected probe output can itself be synthesized from fields that intervention leaves free;
5. the final substituted expression contains no hidden oracle call and no overwritten-value channel;
6. independent terminal contexts re-observe all three selected interventions before the final expression receives terminal authority;
7. every oracle observation is counted in one end-to-end ledger;
8. invalid/non-finite oracle behavior fails closed;
9. field renaming and positional permutations cannot change the semantic result solely through identifier/hash scheduling;
10. added trainable parameters remain exactly zero.

## Authority boundary

### Trusted language

Reuse the finite R2.56/R2.66 expression language:

- scalar fields and finite JSON-compatible constants;
- unary `abs`, `neg`, `not`;
- trusted binary numeric/comparison/boolean operators;
- `IfElse`.

R2.67 does **not** invent new primitive operator semantics.

### Pure-input interventions only

An intervention is still an `InterventionSpec` over the input mapping. R2.67 does not execute filesystem, network, process, clock, mutable-state, or irreversible actions.

### No overwritten-value smuggling

For a selected triplet, the composition may use only:

- `__p0`, `__p1`, `__p2`; and
- original positional fields untouched by **all three** selected interventions.

If any selected intervention overwrites a position, that original position is unavailable to the composition expression.

### Terminal authority

Discovery and validation evidence may select and synthesize the program, but cannot authorize it. A non-empty terminal set must be semantically disjoint from every oracle input already queried during learning. On each terminal context, R2.67 must:

1. apply each of the three selected interventions;
2. validate each intervened context before the oracle call;
3. obtain a fresh oracle observation for each selected intervention;
4. compare that observation to the synthesized probe expression;
5. obtain the fresh original-context oracle target;
6. compare it to the fully substituted final expression.

Any mismatch, invalid context, non-finite value, exception, or evidence reuse fails closed.

## Core invariants

### I1 — Exact three-probe use

The accepted composition expression must reference all of `__p0`, `__p1`, and `__p2`.

### I2 — Strict lower-order falsification

Before acceptance, run matched ablation searches for every proper non-empty subset of the selected probes:

- three singleton searches;
- three pair searches.

Every one must fail to synthesize an exact target program under the declared ablation grammar and budget. If any lower-order subset succeeds, the triplet is not evidence of a three-probe capability and must be rejected.

### I3 — Executable probes

For each selected intervention, synthesize its oracle output from only the fields left free by that intervention. Each probe expression must pass held-out validation evidence for that intervention.

### I4 — Triplet-order invariance

Triplet search order must be semantic-first. A hard global budget must not make pass/abstain depend solely on positional field order or content-addressed intervention IDs. A fixed budget may cause both permutations to abstain; it may not make semantically equivalent permutations disagree merely because a valid triplet was enumerated earlier in one layout.

### I5 — End-to-end accounting

Receipts expose at least:

- intervention candidates considered;
- legal and rejected profiles;
- triplets considered;
- composition candidates considered;
- singleton-ablation candidates considered;
- pair-ablation candidates considered;
- probe synthesis candidates considered;
- learning oracle calls;
- total oracle calls including terminal authority;
- terminal probe cases/exact count;
- terminal final cases/exact count;
- false terminal accepts.

### I6 — Numeric-semantic identity

Use the existing `semantic_vector_key` normalization so numerically equivalent public observations (for example `1` and `1.0`) cannot bypass evidence-disjointness or semantic scheduling invariants.

### I7 — No host-selected trio answer

Tests and external gates may specify the **structural contract** (three one-field interventions, complete partition, strict lower-order falsification) but must not assert one specific semantic position triplet as the only valid answer.

## Search architecture

### Phase A — profile interventions

Reuse positional canonicalization and authorized intervention enumeration. Profile every legal intervention on discovery and validation contexts with fail-closed oracle handling. Degenerate profiles are removed.

Profiles are scheduled by public semantic behavior first, with intervention ID only as a deterministic tie-break after semantic identity.

### Phase B — fair triplet search

Enumerate semantic triplets of profiles. For each triplet:

1. compute positions overwritten by the union of all three interventions;
2. expose only `__p0`, `__p1`, `__p2` plus shared untouched positions;
3. run bounded contextual-expression synthesis;
4. reject expressions that do not use all three probes;
5. run all six lower-order ablation searches;
6. accept the structural candidate only if every ablation fails and the full expression is exact.

Global budget accounting must be explicit. The implementation must use deterministic semantic scheduling and a fair allocation rule rather than letting early triplets consume the entire global cap by position/hash order alone.

### Phase C — synthesize probes

For the selected triplet, synthesize each intervention profile from its own free input positions. Probe synthesis uses discovery evidence and is checked on validation evidence. A probe that cannot be independently synthesized makes the whole receipt fail closed.

### Phase D — substitute and terminally verify

Substitute the three synthesized probe expressions into the learned composition. Re-observe all three selected interventions on every terminal context, then verify the substituted final expression on fresh original terminal targets.

## Authored causal family: tri-bilinear sum

Use the pure family:

`tri_bilinear_sum(a, b, c, d, e, f) = a*b + c*d + e*f`

Authorize zero-valued one-field interventions.

The intended causal structure is not supplied to the learner, but the family has a useful three-probe witness:

- zero `a` → `p0 = c*d + e*f`
- zero `c` → `p1 = a*b + e*f`
- zero `e` → `p2 = a*b + c*d`

Then:

`target = (p0 + p1 + p2) / 2`

The union of the three interventions hides `a`, `c`, and `e` from composition, leaving only `b`, `d`, and `f` as shared original fields. With independently varied signed examples, no singleton or pair of probes identifies the omitted bilinear component under the matched bounded grammar, while all three do.

The authored corpus must vary all six scalars independently across discovery, validation, terminal, rename, and positional-permutation cases. It must include zero, sign changes, unequal magnitudes, and non-symmetric rows to prevent accidental shortcuts.

## External transfer

Use pinned NumPy `2.4.6` and expose only callable I/O semantics of `numpy.dot` on two length-three vectors:

`dot([a, c, e], [b, d, f])`

The adapter is fixed before running the held-out gate and does not expose NumPy source code or a selected intervention trio to the synthesizer.

Required external evidence:

- source: `numpy.dot` from pinned `numpy==2.4.6`;
- source exposure: I/O only;
- independent challenge and held-out rows not used for synthesis;
- exact result on all accepted cases;
- all singleton and pair ablations fail;
- zero false terminal accepts;
- zero added trainable parameters.

This is a narrow external semantic transfer. It does not establish blind task discovery because the external callable and scalar-to-vector adapter are researcher-selected.

## Required falsifiers

At minimum freeze tests for:

1. missing or empty terminal contexts;
2. terminal context duplicated by numeric alias from learning evidence;
3. terminal selected-intervention input reused from learning profiling;
4. context validator rejection before any terminal oracle call;
5. non-finite original oracle output;
6. non-finite intervention-only oracle output;
7. one synthesized probe corrupted only on terminal contexts;
8. one successful singleton ablation;
9. one successful pair ablation;
10. composition that ignores one of the three probes;
11. hard global triplet budget under semantic positional permutations;
12. field rename replay;
13. end-to-end oracle ledger mismatch;
14. receipt case-unit mismatch (`terminal_probe_validation_cases == 3 * len(terminal)`);
15. repeated/semantically duplicate selected interventions;
16. illegal shared-field access to a position overwritten by any selected intervention.

## Verification and release discipline

R2.67 follows the accepted R2.66 evidence discipline:

1. exact parent is accepted R2.66 `main`;
2. design and plan are frozen before production implementation;
3. explicit hosted RED exists before the public R2.67 module is added;
4. Python 3.11 and 3.13 focused suites are green;
5. authored benchmark is recomputed from code, not copied from old artifacts;
6. external NumPy-dot transfer is recomputed from the pinned dependency;
7. independent challenger tests are adopted into the final frozen boundary;
8. protected R2.66→R2.41 lineage is green;
9. source/evidence blobs are locked only after production stops changing;
10. a complete repository ZIP and SHA-256 are generated and integrity-tested;
11. the exact release artifact is independently downloaded and verified;
12. the final complete ZIP is persisted to the ChatGPT Library.

## Claim boundary

R2.67 may claim only:

> bounded discovery, synthesis, lower-order falsification, executable-probe reconstruction, and independent terminal verification of one three-probe pure-input causal composition over the existing finite trusted DSL, with semantic-order invariance, explicit budgets, fail-closed oracle handling, a pinned NumPy-dot I/O-only transfer, and +0 trainable parameters.

It may not claim:

- arbitrary `N`-probe scaling;
- adaptive/sequential experiment policies;
- stateful/filesystem/network experiments;
- blind external task discovery;
- arbitrary primitive-language invention;
- unrestricted program synthesis;
- broad repository autonomy;
- W5 convergence;
- frontier-model equivalence;
- AGI.
