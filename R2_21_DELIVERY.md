# Nolane-AI R2.21 — Confidence-Adaptive Evidence Acquisition

**Decision:** ACCEPTED (bounded Phase A evidence)  
**Parent GitHub main before integration:** `db2e005b6782ee5c38dd6b1feca154e863e6e17f` (R2.19)  
**R2.20 status:** REJECTED, preserved as negative evidence, zero readiness credit  
**AGI engineering-readiness:** **22.8 → 23.4 / 100 (+0.6)**

> `23.4/100` is a project engineering-readiness rubric, not a scientific probability that Nolane-AI is “23.4% AGI”.

## What R2.21 adds

R2.20 synthesized representation operators outside R2.19's fixed grammar, but its fixed 15-query evidence cap failed one frozen noisy-verifier seed. R2.21 does not retroactively tune that failed milestone. Instead it adds a new sequential evidence policy with a base budget of 12 and a hard maximum of 24. After the base budget, evidence acquisition continues only while unresolved hypotheses retain posterior-weighted disagreement and a live hypothesis remains recoverable. It stops early on justified acceptance and abstains when remaining information value is too low.

The known R2.20 diagnostic seed `73459` remains a frozen failure under fixed-15 but is recovered by R2.21 at 17 queries. Fresh held-out seeds `82013`, `82717`, and `83431` all pass every preregistered gate with noisy evidence costs `11`, `17`, and `14`, respectively, versus the always-max ablation's 24 queries.

## Evidence discipline

- R2.21 pre-heldout lock: 17 frozen files, fresh seeds fixed before execution.
- Fresh heldout: 3/3 accepted.
- Independent verifier: 47/47 checks PASS, 3/3 exact canonical replays.
- Final R2.21 focused suite: 19/19 PASS.
- R2.20 frozen integrity: 16/16 hashes unchanged.
- No tracked R2.18/R2.19/R2.20 core edit was introduced by R2.21.
- R2.20 remains explicitly REJECTED at 22.8; R2.21 alone receives +0.6.

## Nolane World v5

World preregistered six predictions before fresh heldout. The positive discriminating experiment was accepted only after heldout and independent verification. Final World audit is valid with 57 events, VM 13/13, two fresh independent verifications, one survived challenger, six robust scenarios, and five verified representations.

World is intentionally **not converged**. Hard blockers remain for trusted active residency, independent attested compute, one critical unknown, insufficient validated information gain, and remaining value-of-thought. These counters were not fabricated to obtain a green convergence label.

## Boundary and next falsifier

R2.21 is still bounded to a finite-state operator language and a human-specified evidence-acquisition policy. The next stronger target is **learned/transferable value-of-information control** across heterogeneous verifier-noise and evidence-cost regimes, with the task solver held fixed. That would test whether the small system can learn *how much thinking/evidence to buy* rather than relying on manually chosen continuation thresholds.
