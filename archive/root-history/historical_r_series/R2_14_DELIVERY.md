# Nolane R2.14 — Active Program Disambiguation

Date: 2026-08-15  
Status: **PHASE-A INTERNAL GATE ACCEPTED / EXTERNAL GENERALITY UNPROVEN**

## Capability added

R2.14 adds **0 neural parameters**, keeping the coding-track neural total at **79,450,489**. It repairs the specific R2.13 program-underdetermination bottleneck by replacing single-shortest-program commitment with a semantic version space and bounded active execution queries:

`ambiguous demonstrations -> semantic hypothesis classes -> minimax discriminator -> execution evidence -> prune -> resolve or abstain`

Programs that are observationally equivalent over the declared finite probe domain are collapsed into one semantic class. Enumeration truncation fails closed. A single surviving hypothesis still requires a falsification/confirmation probe when unseen domain points remain.

## Negative result lineage

R2.13 was rejected at 75% contextual transfer and 75% old-regime retention under an 87.5% frozen threshold. The contextual router selected the intended skill, while the inherited R2.3 shortest-consistent synthesizer could select a spurious program that fit sparse demonstrations but failed unseen XOR-family inputs. R2.13 is retained as a negative result; it is not rewritten as an accepted milestone.

## Frozen protocol

`research/R2_14_PRE_HELDOUT_LOCK.json` was written before heldout and has SHA-256:

`f1760126547b4ec88f524d7cc105df5e4efbb0051739c978504ee7b6225cc001`

The lock freezes the decision-relevant source/spec/test hashes, DEV seeds 22001..22005, heldout seed 32001, finite probe domain, hard three-query oracle budget, and acceptance thresholds.

## Heldout result

- main active identification: **100% (160/160)**
- shortest-consistent baseline: **0%**
- passive-fixed baseline: **21.25%**
- random-budgeted baseline: **71.875%**
- gain over random-budgeted: **+28.125 pp**
- depth-3 active stress: **93.75% (60/64)**
- depth-3 passive baseline: **39.0625%**
- depth-3 random baseline: **56.25%**
- old-regime retention: **100%**
- out-of-class abstention: **100%**
- identity/class-order permutation invariance: **100%**
- false resolved accepts: **0**
- maximum active oracle calls: **3**
- new neural parameters: **0**
- effective neural parameters: **79,450,489**

Budget curve on the frozen main heldout is **0% -> 17.5% -> 91.25% -> 100%** for oracle budgets 0, 1, 2, 3. This matters because the final performance depends on acquiring discriminating evidence rather than merely decoding an answer already fixed by the sparse initial demonstrations.

Heldout raw SHA-256: `65fabbf32c55c897d1cb2b4e2ee5ddcf14ca73fc8d48d0f2154d2c019fbfb2af`  
Aggregate result SHA-256: `1a5cfcf62f151d93ac96dd02db0ccf9df9807d60a87e82ab19ba5ae1bb0ed256`

## AGI engineering-readiness

**19.2/100 -> 20.0/100 (+0.8).**

The increase is deliberately small. R2.14 adds credible internal evidence for active hypothesis disambiguation, epistemic abstention, and continual-skill reliability, but the task remains synthetic, the hypothesis language is finite, the probe domain is known and finite, and the execution oracle is exact. It does not establish broad world knowledge, natural-language competence, multimodal grounding, open-ended autonomous learning, unrestricted program synthesis, or AGI.

## Next bottleneck

The immediate causal limitation is the assumption of an exact oracle and closed finite hypothesis/probe domain. The next research axis should test calibrated active hypothesis testing under noisy/partial evidence and distribution shift before granting stronger continual-learning credit.

## Claim boundary

R2.14 is an internal finite-domain active program-identification result. It does not establish external coding performance, unrestricted software engineering, frontier-model parity, or AGI.
