# R2.11 Differential Multi-File Localization Design

Date: 2026-08-15
Status: accepted internal design under standing autonomous research instruction

## Goal

Add a zero-neural-parameter multi-file fault-localization layer that uses public test coverage and differential runtime behavior before handing the selected symbol to R2.10 proposal and R2.9 verification.

## Why this milestone

R2.10 repairs constrained expressions well when the correct function is already in view, but it does not decide which file/symbol in a repository is faulty. Early DEV experiments showed that forcing R2.10 edit-gain to act as a localizer was unreliable (56.25% then 34.38% Hit@1). R2.11 therefore separates localization from repair and uses evidence native to localization.

## Architecture

### 1. Anonymous repository graph

R2.8 topology is reused. Node IDs and file paths route observations and patches but are never scoring features. Only symbols reachable from the failing test through `tests/calls/depends_on/imports/contains` edges are eligible.

### 2. Spectrum evidence

For each candidate symbol, compute Ochiai-style suspiciousness from public pass/fail coverage:

`failed_covered / sqrt(total_failed * (failed_covered + passed_covered))`.

A healthy shadow implementation is deliberately given the same coverage spectrum as the faulty implementation, preventing spectrum alone from solving the locked task.

### 3. Differential runtime behavior

For peer implementations of the same public contract, collect public runtime observations for the same probes. Without using the gold location or hidden correct patch, infer the per-probe majority observation and score a symbol by how often its observed behavior disagrees with peer consensus.

### 4. Graph/risk terms

Add small topology proximity and blast-radius terms from R2.8. R2.10 edit-gain is disabled for Phase A because DEV ablation showed it harms localization out of distribution.

### 5. Repair handoff

Take the top localized symbol, enumerate R2.10 constrained edits, rank them with the accepted R2.10 proposer, then run unchanged R2.9 verification with patch budget 2. R2.11 cannot set terminal success.

## Frozen Phase-A protocol

- JavaScript multi-file repositories: 64
- providers per repo: 8
- off-path distractor symbols: 2
- public coverage tests: 8
- one healthy shadow provider has identical spectrum to the target
- two public runtime probes
- random file/function/parameter/node identities
- identity-permuted twin repositories required
- patch evaluation budget: 2
- behavior weight: 0.5
- R2.10 edit-gain weight in localization: 0.0
- new neural parameters: 0

Acceptance was frozen before heldout measurement in `research/R2_11_PRE_MEASURE_LOCK.json`.

## Claim boundary

Passing Phase A establishes only internal differential multi-file localization plus constrained repair on the frozen executable protocol. It does not establish fresh real-repository localization, arbitrary patch generation, AGI, or frontier-model parity.

## Next axis if accepted

R2.12 should test the localization layer on fresh/recent real repositories, initially measuring file/symbol localization separately from patch generation. If that transfers, only then promote end-to-end external issue repair.
