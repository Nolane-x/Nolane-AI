# R2.64.1 → R2.65 Evolution

R2.64.1 corrected the bounded repository-search frontier but still required the host to supply the exact trusted `PatchMacro` vocabulary needed for expansion. R2.65 removes that exact-macro channel inside a deliberately closed authority boundary: it derives candidate binop-replacement primitives from repository structure plus a finite host-authorized grammar, admits behavioral evidence only through public diagnostics and independent challenges, and promotes a primitive only after separate terminal verification.

## New capability boundary

R2.65 can recover an exact missing target-specific binop replacement without receiving the target repository or exact `PatchMacro`. The grammar itself remains host authorized and finite (`Add`, `Sub`, `Mult`, `Div`, `FloorDiv`, `Mod` replacement hypotheses), so this is verified primitive induction, not unrestricted patch-language invention.

The implementation preserves the inherited `PatchMacro` runtime contract, exposes semantic read-only aliases through `PatchPrimitiveMacro`, enumerates hypotheses deterministically from structurally observed source operators, and performs target-output-free candidate generation. Generation is hypothesis-fair under a real global candidate cap rather than allowing an early high-site hypothesis to starve later primitives.

## Misspecification and promotion hardening

Adversarial work by the concurrent Council and Nolane World exposed several real defects before acceptance. R2.65 now continues bounded diagnostic checking when the initial version space is a singleton, when multiple candidates are unanimously wrong, and when discriminative probing collapses to a single wrong survivor. Fallback diagnostics are canonicalized by probe ID so caller ordering cannot alter the bounded semantic result. Primitive promotion also fails closed unless at least one independent challenge is required and available.

These defects were preserved as explicit RED contracts before the final source lock. The final schema-8 lock binds the PatchMacro field contract, hypothesis fairness, true global generation cap, initial-singleton misspecification, unanimous misspecification, post-selection singleton misspecification, diagnostic-order invariance, and mandatory independent-challenge promotion.

## Evidence

The frozen authored Phase-A contains six positive repository episodes spanning six source/target operator transitions, 3–5 files and relay depth 0–2. R2.64.1 abstains in all six because no exact expansion macro is supplied; R2.65 derives and promotes the expected primitive in 6/6, with at least four independent challenges and 35 disjoint final verification cases per episode. Eight negative cases abstain and false terminal accepts remain zero.

The pinned external transfer uses NumPy 2.4.6 `numpy.multiply` through callable I/O only. The exact target repository and exact Add→Mult macro are withheld. R2.64.1 abstains with `no_expansion_macros`; R2.65 derives Add→Mult, passes 8/8 independent challenges and 225/225 disjoint terminal cases, with no target-output generation channel and zero false terminal accepts.

Fresh canonical hosted run `32139543942` verifies source lock schema 8, exact authored/external recomputation, 20/20 R2.65 tests, 247/247 protected R2.64→R2.41 parent tests, and Python 3.11/3.13. The complete repository bundle run `32139543857` independently rechecks the frozen boundary, exact evidence, protected lineage and ZIP integrity.

## Remaining boundary

R2.65 does not learn arbitrary syntax or effects. It does not establish stateful/filesystem/network/concurrency patch induction, blind real-repository issue repair, unrestricted program synthesis, broad patch-language growth, or AGI. Nolane World 0.8.0 keeps W5 false.
