# R2.13 Evidence-Preserving Skill Consolidation — REJECTED

R2.13 upgraded the R2.3 skill memory concept with immutable episode evidence, append-only revision lineage, contextual routing, and ambiguity quarantine. It adds **0 neural parameters** and would keep the neural total at **79,450,489**.

## Frozen gate
DEV was measured first. The source/protocol was then frozen in `research/R2_13_PRE_HELDOUT_LOCK.json` (SHA-256 `7b00877cb7d7058ff2a548f5721dac2382b67d8f5d8e90f6958728840283888c`). No decision-relevant source was changed before the first heldout run.

Heldout requirements included >=87.5% contextual transfer, >=25 percentage-point gain over latest-version memory, >=87.5% old-regime retention, 100% ambiguous abstention, 100% evidence integrity, and +0 neural parameters.

## Heldout result
- R2.13 contextual accuracy: **75.0%**
- R2.3-style latest-version baseline: **37.5%**
- no-memory identity fallback: **6.25%**
- old-regime retention: **75.0%**
- ambiguous-context abstention: **100%**
- evidence integrity during evaluation: **100%**
- new neural parameters: **0**

The transfer and retention gates failed, so R2.13 is **not promoted**.

## Root cause
Both failures were the same XOR-based transformation family. The contextual router selected the intended candidate, but the existing bounded symbolic synthesizer found a short program that exactly fit all four demonstrations while being non-equivalent on the heldout input. Therefore the failure is program underdetermination/generalization, not evidence routing.

This negative result is preserved. The next research axis should be robust program identification through active discriminating examples, equivalence checks, and execution-guided hypothesis sets rather than choosing the first shortest program consistent with sparse demonstrations.

## Claim boundary
This is an internal continual-learning architecture experiment. It failed its frozen heldout gate and provides no basis for an AGI or external coding capability claim.
