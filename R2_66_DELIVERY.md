# R2.66 — Learned Contextual Causal Composition

Status: **ACCEPTED_BOUNDED_CAPABILITY**

Accepted capability merge: `e2eef08f15e7c0a5e79f58579282db90c157cb4a`

Frozen capability/evidence head: `7b707c22e05bdf2b33dc8d846965c0310834fb84`

Parent release: R2.65 `768e500d6b3e8d1d8ec747e37aae6302ab6747d1`

## Capability

R2.66 removes the fixed host-selected `add/sub/rsub/mul/min/max` composition channel inherited from the bounded R2.62 causal-program line. It can learn a finite trusted-DSL contextual composition over the outputs of exactly two complementary pure-input interventions plus only context positions untouched by both interventions. The two probe behaviors are synthesized into executable expressions and terminal acceptance is separated from learning evidence.

## Frozen authored evidence

`R2_66_PHASE_A_RESULT.json` is exact-recomputed by the canonical gate. Three semantic configurations succeed 3/3. Selection is 72/72 exact, probe validation is 36/36, disjoint terminal verification is 18/18, the fixed-operation baseline fails all three configurations, both singleton ablations fail all three, and false accepts are zero.

## Pinned external transfer

`R2_66_EXTERNAL_TRANSFER.json` uses `WarrenWeckesser/ufunclab:ufunclab.step` at commit `f1fbe6769850823a1976ccc28d14cd966130b645` through callable I/O only. The host does not select the intervention pair. R2.62's fixed composition family does not solve the selected behavior, neither singleton is sufficient, the learned composition passes 12/12 challenge cases and 36/36 heldout cases, and false accepts are zero.

## Council hardening

Independent Council challengers found real pre-release defects rather than only confirming the design. The frozen schema-4 boundary incorporates regressions for semantic pair-budget scheduling, global fail-closed intervention-oracle errors, numeric-semantic evidence identity, terminal evidence uniqueness/disjointness, selected-probe terminal re-observation, validator-safe terminal interventions, semantic profile identity, hard total oracle caps and end-to-end oracle accounting. Historical RED challenger evidence is retained rather than rewritten as if the bugs never existed.

## Hosted verification

Canonical GitHub Actions run `32152862847` passes the schema-4 Git-blob lock, exact authored and external recomputation, 21/21 R2.66 tests, 267/267 protected R2.65→R2.41 parent tests, and Python 3.11/3.13. Pre-integration release-bundle run `32152862858` independently repeats the release boundary and produces a verified COMPLETE repository bundle.

## Nolane World adjudication

Nolane World 0.8.0 world `world4_aa51b60d5a7e4555` has a valid audit digest `de32990437181d2f0c33e8a9db226aadd06121a3e435cafc2a0bfdaca6b62712`, two fresh verifier lineages and survived material challenger evidence. **W5 remains false**. The runtime still blocks convergence on residency/epoch depth, unresolved breadth, challenger/robust-world depth, representation diversity and remaining value-of-thought. No convergence was forced.

## Readiness

Internal engineering-readiness: **49.9/100**, +0.2 over R2.65. This is deliberately small and is not an AGI probability. The external transfer is distinct and the host-supplied fixed composition channel is removed, but evidence remains researcher-selected, pure-input, exactly-two-intervention and finite-DSL.

## Explicit non-claims

R2.66 does **not** establish open-ended composition-language invention, three-or-more intervention scaling, stateful/temporal/filesystem/network experimentation, blind task discovery, broad real-repository autonomy, W5 convergence, or AGI.

## Final release condition

The capability is merged. The final downloadable snapshot is governed by the Council-authored `.github/workflows/r266-post-merge-release-bundle.yml`, which must succeed again after these release-authority records are integrated so the final ZIP contains the hosted receipt, World audit, manifest and delivery record. The resulting artifact must then be independently checksum/integrity verified.
