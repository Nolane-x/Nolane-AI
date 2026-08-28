# Nolane-AI R2.38 — Compositional Probe-Language Synthesis

**Decision:** ACCEPTED (bounded Phase A evidence)  
**AGI engineering-readiness:** **24.6 → 25.6 / 100 (+1.0)**

> `25.6/100` is an internal engineering-readiness rubric, not a scientific probability that Nolane-AI is “25.6% AGI”.

## Capability added

R2.37 could synthesize a novel atomic state-pair query outside a strict initial pool. R2.38 expands the action language: the small system can synthesize a bounded verifier-query program with two atomic leaves and one of `XOR`, `EQUIV`, `AND`, or `OR`. The AST is selected by posterior-weighted disagreement; proposal posterior updates, acceptance thresholds and independent counterexample authority remain frozen.

The generator is parameter-free and has no inference field for seed, task family, target, truth, heldout identity or evaluator-only reliability.

## Development evidence

Nonlinear-local width-3 development:
- compositional: **6/6 correct**;
- atomic-only: **4/6 correct**;
- pool-only: **0/6 correct**;
- compositional mean calls: **13.83** versus atomic-only **14.17**;
- **47** composite probes generated.

A disjoint width-4 `global_asym` dry-run passed **4/4** compositional episodes before heldout identities were locked.

## Frozen heldout

Fresh width-4 `global_asym` seeds `521/523/541` under clean + noisy verification:
- compositional: **6/6 correct**;
- atomic-only: **6/6 correct**;
- pool-only: **0/6 correct**;
- compositional mean verifier calls: **20.00**;
- atomic-only mean verifier calls: **20.17**;
- **48** composite probes generated;
- zero false accepts;
- identical total query-budget contract;
- **6/6 independent canonical replays exact**.

Final verifier: **8/8 checks PASS**.

## Nolane World v5

World preregistered six predictions before experiment execution. Deep final review reached:
- audit valid, **70 events**;
- Cognitive VM **13/13**;
- **2** fresh independent verifications;
- **1** independent challenger survived;
- **12** robustness records;
- **13** verified representations.

World remains intentionally **non-converged**. Hard blockers retained: trusted active residency, independent attested compute, one critical unknown, and remaining value-of-thought.

## Boundary and next falsifier

The evidence supports bounded binary compositional query-program synthesis in finite bit-state worlds. It does not support unrestricted scientific experimentation or AGI. The next strong target is a **recursive typed probe DSL with explicit composition costs** and transfer to a non-bit-state task family, where the system must invent useful intermediate predicates/macros rather than only choose one binary operator over two atoms.
