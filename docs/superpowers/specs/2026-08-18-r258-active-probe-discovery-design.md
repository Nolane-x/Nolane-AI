# R2.58 Active Probe/Subgoal Discovery Design

## Goal
Remove the R2.57 harness-selected endpoint probe by letting the learned cognitive vocabulary compile and test its own bounded interventions against an I/O-only oracle, then reuse a verified discovered subgoal to unlock full synthesis.

## Scope and claim boundary
R2.58 is a zero-trainable-parameter bounded capability over the existing finite pure R2.56 evaluator and R2.57 learned vocabulary. It does not inspect oracle source, invent new evaluator semantics, execute effectful tools, or claim general program synthesis / AGI.

## Core mechanism
1. **Exposure-schema discovery.** For each promoted `LearnedAbstraction`, search deterministic constant assignments to every non-target parameter. A schema is admitted only when repeated evaluator checks show the abstraction output equals the unfixed target parameter across a diverse numeric/string/bool validation grid. This converts learned operators into controllability knowledge without semantic names.
2. **Intervention compilation.** Map schema-fixed parameter slots onto task input fields. Apply their constants to existing training/challenge contexts, query a context-callable black-box oracle, and synthesize the induced output over the remaining fields. No field name or manually supplied `fa/fb` probe selection is used.
3. **Independent challenge.** A candidate latent expression must exactly match oracle outputs on independently transformed challenge contexts. A candidate that only fits the intervention-training rows is rejected.
4. **Causal utility test.** Only keep a challenged latent expression if seeding R2.57 vocabulary-aware synthesis with it unlocks the original full target under the frozen full-synthesis candidate budget. This prevents promoting easy but irrelevant probes.
5. **Bounded deterministic ledger.** Count every oracle call and synthesis candidate. Exceeding any budget, invalid/non-finite oracle output, or no challenged causal candidate fails closed.

## Interfaces
Create `cogcoder/r258_active_probe.py` with:
- `ExposureSchema`
- `ProbeBudget`
- `ProbeAttemptReceipt`
- `ActiveProbeReceipt`
- `discover_exposure_schemas(vocabulary, constants=...)`
- `discover_verified_subgoal(...)`

The oracle interface is `Callable[[Mapping[str, object]], object]` so the engine receives only context-to-output behavior.

## Determinism and invariance
All abstraction IDs, field mappings, constants and candidates use canonical sorted order. Selection is based on structural/evidential scores, never user-facing field names. A field-renaming metamorphic test must produce the same success/failure result, oracle-call count, exposure schema identity and relative fixed/remaining role structure.

## Safety / failure behavior
- Unknown abstraction dependencies: reject via existing R2.57 vocabulary rules.
- Non-finite or non-JSON oracle outputs: fail closed.
- Query budget exhaustion: stop immediately and return no usable subgoal.
- Challenge mismatch: candidate rejected; bounded CEGIS may add a challenge counterexample and resynthesize before final rejection.
- Full-target seed does not improve/solve: candidate rejected as non-causal.
- Search order is deterministic from content-addressed exposure schemas and observation-profile field order. Once a candidate passes transformed challenge, causally unlocks full synthesis, and passes the original challenge, accept it and stop; later equivalent alternatives are not required for this bounded acceptance claim.

## Evidence
Authored benchmark must include multiple opaque field-name episodes and decoy mappings. Frozen results must report: exact solves, R2.57 harness-free baseline, false accepts, oracle calls, challenge rejections, renaming invariance and trainable parameter delta. External hosted evidence should replace `_probe_rows()` with active discovery against the pinned I/O-only `ufunclab.linearstep` oracle.

## Nolane World boundary
World convergence remains independent of milestone acceptance. R2.58 may be accepted as a bounded capability while W5 remains FAIL. Critical unknowns about broad domains, effectful discovery, probe-space scaling, hostile oracles and independent challengers remain explicit.
