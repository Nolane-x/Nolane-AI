# Nolane-AI R2.18 — Cross-Domain Transfer + Open-Ended Library Governance

**Decision:** ACCEPTED (bounded Phase A evidence)  
**Parent GitHub main:** `01d162a49a332dc4aa9bd0cff670fa4c9cc09884` — R2.17 Hierarchical Library-Growing CEGIS  
**Neural parameters:** 79,450,489 effective; **0 new neural parameters**  
**AGI engineering-readiness:** **21.7 → 22.2 / 100 (+0.5)**  

> The readiness number is a project engineering rubric, not a scientific probability that the system is “22.2% AGI”.

## What R2.18 actually adds

R2.17 could mine, validate, promote, reuse, quarantine and roll back reusable macro schemas inside its accepted program family. Its own next bottleneck was cross-domain concept transfer plus open-ended library governance. R2.18 attacks that bottleneck without modifying sealed R2.17 decision logic and without adding neural parameters.

R2.18 adds a typed immutable transfer layer:

- skill identity is based on **kind + mechanism tags + behavior digest**, not domain name;
- new domains receive bounded **trial** routes rather than automatic trust;
- clean evidence windows promote a domain route to active;
- false accept, correctness regression or guarded budget regression causes **domain-local quarantine**;
- a failure in domain C does not erase a skill still validated in domains A/B;
- behavior-equivalent duplicates merge provenance without consuming capacity twice;
- capacity is bounded deterministically using evidence value density;
- rollback restores an exact prior record snapshot in a **new audit version** rather than rewriting history.

## Cross-domain execution evidence

The same generic periodic guarded-recurrence verifier is first established on a synthetic source recurrence and then applied through a domain adapter to the external AES-128 key schedule fixture from NIST FIPS 197-upd1 Appendix A.1. The frozen NIST answer is used as fixture provenance/oracle validation only; it is not an equality predicate in candidate filtering.

The AES cohort contains four hard core-rule decoys (`no_rot`, `no_sub`, `wrong_rcon`, `rcon_low_byte`) that preserve seed, exact length and normal recurrence. With all invariants enabled, only `target_nist_fips197` survives. When the special periodic rule is ablated, at least all four hard decoys survive, demonstrating that the discriminating gate carries causal information.

## Pre-registration and heldout discipline

World v5 registered four predictions before heldout execution. The pre-heldout lock froze 11 decision/test/prereg files and seeds `42831`, `43117`, `43991` with lock SHA-256 `5330d126569afb15d5a1d1aef3ea1b78e17fbd6f1db40f69db88ecf7e53dfc86`.

All three frozen heldout executions passed every gate. The heldout payload SHA-256 is `fb380104fcf1cf3ebc535114e56f472ad4b529c69f426eaa90e731a7b65ed63c`. The independent verifier reproduced all three executions exactly and passed **25/25** checks.

World constitution also accepted the experiment in the correct order: prediction registration event 12 preceded experiment acceptance event 23. This fixes the protocol failure found in the earlier AES attempt, where World rejected post-hoc experiment registration.

## World research outcome

World v5 completed the full W4 cognitive program **13/13** for this milestone, including robustness, adversarial falsification, independent challenger reconstruction, synthesis and independent verification. It recorded two fresh verification principals, one challenger with independence 1.0, six verified stress scenarios, four verified representations and zero remaining critical unknowns.

World itself is **intentionally not marked converged**. Its convergence court still reports hard blockers for trusted active residency, independent attested compute, validated information-gain floor and remaining value-of-thought. R2.18 does not fabricate those counters merely to obtain a green convergence label.

## Regression reality

- R2.18 focused contracts: **17/17 PASS**.
- R2.17 frozen focused regression: **29/29 PASS**.
- Independent R2.18 verifier: **25/25 PASS**, three exact heldout replays.
- Syntax compile: PASS.
- R2.17 `test_r217_protocol.py` still exhibits the previously documented outer-runner / descendant-pipe lifetime hang under a bounded probe. It is explicitly **not counted as a PASS** and R2.18 does not claim to fix it.

## Why the readiness score moves only +0.5

The locked rubric awarded +0.15 for mechanism-level cross-domain transfer, +0.10 for safe negative-transfer isolation, +0.10 for merge/capacity governance, +0.05 for exact rollback, +0.05 for external NIST-grounded execution, and +0.05 for World preregistration discipline. No credit is awarded merely for documentation, test count, or manually adding another adapter.

## Next falsifiable milestone

**R2.19 should target autonomous representation discovery under partial/noisy verification.** The current transfer is real but still bounded by a manually supplied recurrence representation on both sides. The decisive next experiment should use a structurally different family where Nolane-AI must infer an alignment/representation, manage uncertain verifier feedback, and decide whether to reuse, split, create or abstain from a skill under a fixed library/compute budget.

That is a stronger route toward a small system that improves through reusable abstractions rather than accumulating benchmark-specific rules.
