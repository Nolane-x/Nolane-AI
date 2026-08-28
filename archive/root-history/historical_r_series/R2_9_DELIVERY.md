# Nolane R2.9 — Verifier-Guided Patch Search

Date: 2026-08-15  
Status: **PHASE-A INTERNAL EXECUTABLE GATE PASSED / EXTERNAL CODING GATES PENDING**

## Why this milestone exists

R2.8 can reason about repository topology, competing fault hypotheses, information gain, and edit risk, but it still stops before the most important coding step: selecting and refining concrete source-code patches. R2.9 adds a parameter-free search layer that treats patch generation as an inference-time search problem rather than a one-shot guess.

R2.9 deliberately does **not** claim to add a general source-code decoder. Initial and refined candidates are supplied by proposal callbacks/symbolic operators; the new capability is the verifier-guided search, memory, deduplication, risk-aware ranking, and execution-feedback refinement that a future neural proposer can plug into.

## Architecture added

- immutable language-agnostic text patch algebra;
- canonical content-derived patch fingerprints independent of candidate ids;
- safe application with missing-file/span/overlap rejection;
- hard-budget deterministic best-first patch search;
- executable verification callback as the only authority for terminal success;
- failed-patch memory and canonical deduplication;
- execution-evidence-driven refinement callbacks;
- R2.8 graph-derived blast-radius penalty for risky edits;
- deterministic trace invariance under candidate-id renaming.

## Research basis

The design follows three useful current directions without copying their implementations: iterative/global patch search rather than local one-shot retry; execution-level evidence rather than binary symptoms alone; and adaptive test-time search under explicit budget. For Nolane's compact-model objective, these mechanisms are external cognition-time infrastructure, so the neural core remains unchanged.

## Neural parameter accounting

- R2.8 parent: **79,401,400** effective neural parameters;
- R2.9 new neural parameters: **0**;
- R2.9 candidate: **79,401,400** effective neural parameters.

R2.9 intentionally creates no new neural checkpoint.

Parent weight: `Nolane-R2.7-CodeWorld-Generalist-Phase-A-ONE-WEIGHT.pt`

- SHA-256: `16552d8565ba696dce3c2b853c27097f74e727bbfb8e2d6ff35064af308adcf5`

## Locked Phase-A result

The thresholds were stored in `research/R2_9_PRE_DEV_LOCK.json` before the measurement script was run.

The executable micro-repository protocol contains four cases across Python and JavaScript:

1. an initially plausible patch passes only part of targeted verification and must be refined from execution evidence;
2. two patches satisfy behavior, but the lower-blast-radius patch is evaluated first;
3. content-equivalent patches under different ids are canonicalized and evaluated once;
4. a tempting patch passes the target test but fails regression verification, so terminal acceptance is blocked and refinement must continue.

Measured result:

- verified solves: **4/4**;
- false terminal accepts: **0**;
- duplicate evaluator calls: **0**;
- candidate-id rename invariance: **4/4**;
- maximum evaluator calls observed: **2 per case** (locked ceiling: 8);
- new neural parameters: **0**;
- result SHA-256: `1a99aa59e391988520c87baa82a5bb1e5e1aab5b8b5b299cf1a54073d756d2dd`.

## What R2.9 now enables

Nolane now has a reusable inference-time mechanism that can:

`propose candidates → rank by evidence/risk → execute → remember failure → refine → re-rank → verify → accept/reject`

This is useful specifically for a small model because additional competence can come from structured search and reliable external feedback rather than only from parameter growth.

## Remaining major gap

R2.9's candidate source is still weak. It can search well among supplied candidates but cannot yet generate arbitrary high-quality patches from unfamiliar repository context. The next research axis is therefore **R2.10 Neural/Source-Aware Edit Proposal**: a compact proposer conditioned on issue text, localized code, R2.8 hypotheses/world graph, and R2.9 execution history.

## External gate roadmap

External coding claims remain locked. After a source-aware proposer exists, evaluation should move to fresh executable repository tasks, prioritizing continuously updated or large-scale multilingual collections such as SWE-bench-Live and SWE-rebench V2, with process-quality checks to guard against lucky passes.

## Claim boundary

R2.9 Phase A does not establish AGI, arbitrary source-code generation, broad real-world repository issue resolution, or parity/superiority to frontier models. It establishes only the implemented verifier-guided patch-search behaviors under the locked executable micro-repository protocol.
