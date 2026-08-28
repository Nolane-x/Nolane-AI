# Nolane-AI R2.57 Delivery — Verified Cognitive Vocabulary Growth

Status: **ACCEPTED_BOUNDED_CAPABILITY**

R2.57 grows the cognitive language available to the zero-parameter R2.56 synthesizer. Instead of adding named semantic opcodes by hand, it mines repeated verified expression structure across distinct tasks, anti-unifies that structure into parameterized content-addressed abstractions, admits only positive-compression abstractions, and exposes the learned vocabulary as first-class synthesis primitives.

The learned library is still bounded by the underlying R2.56 pure evaluator. R2.57 does **not** invent arbitrary Python, new effect semantics, filesystem/network actions, or an open-ended evaluator language.

## Mechanism

- structural anti-unification over verified expressions with opaque task/field names
- distinct-task support requirements and MDL/compression gain
- content-addressed learned-abstraction IDs and DAG/no-cycle constraints
- expansion budgets and fail-closed unknown dependencies
- fair learned-abstraction scheduling to prevent one library entry from monopolizing search
- verified working-memory seed reuse for multi-stage subgoals
- live verification with learned-vocabulary withdrawal/rollback on failure

## Authored frozen benchmark

- 3 learned abstractions: clamp, lerp and normalize structural families
- compression gains: **1, 11, 11**
- minimum support: 6 distinct tasks per admitted family
- heldout composition episodes: **6/6 exact**
- R2.56 base under the same bounded setting: **0/6**
- 0 false accepts
- bad abstraction quarantine: PASS
- live rollback/revocation: PASS

## Fresh hosted evidence

Capability commit: `a5835c7e9e20ab268870f3e2cbe56f10536aef44`

Hosted run: `32098662916`; main job `95594817850` — success.

- focused R2.57 tests: **15/15**
- protected local relevant lineage: **175/175**
- hosted parent steps R2.56→R2.41: all success
- Python 3.11 / 3.13: success / success
- frozen R2.57 Phase-A recomputation: success
- added trainable parameters: **0**

## Independent ufunclab transfer

Pinned oracle: `WarrenWeckesser/ufunclab@f1fbe6769850823a1976ccc28d14cd966130b645`, callable `ufunclab.linearstep`.

The learner receives only callable I/O observations. Source implementation is not parsed into the synthesis grammar.

- R2.56 base: FAIL under frozen bounded search
- grown R2.57 vocabulary: PASS
- independent challenges: **8/8**
- post-promotion heldout: **24/24**
- verified subgoal/progress search: 4,760 candidates
- full composition after seed reuse: 179 candidates
- learned composition is equivalent to lerp(fa, normalize(clamp(a, x, b), a, b), fb)

The harness chooses an endpoint probe to expose the normalized-progress subgoal. Therefore this is evidence for vocabulary reuse and search contraction, not evidence that the system autonomously discovers every useful intervention or task decomposition.

## Nolane World

Fresh world `world4_bd574d91fb284e3a` reached epoch 8. Audit digest `3ae5182269c9edd6750cb7b5549dd674b9cbb753b99b5915537800222347d664` is valid, while W5 remains **FAIL**, score **0**. Non-convergence is preserved.

## Readiness

Internal Coding-AGI engineering-readiness: **47.5/100**, up **+0.7** from R2.56's 46.8. The movement is deliberately small because the external causal transfer is meaningful but covers one pure numeric family and still uses a host-designed base evaluator plus a harness-selected probe. This is not an AGI probability.
