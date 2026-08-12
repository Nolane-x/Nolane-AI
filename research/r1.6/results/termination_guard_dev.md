# R1.6 Factorized Termination Guard — Dev Result

Date: 2026-08-12 (Asia/Bangkok)

## Protocol

- Parent: `Nolane-R1.6-NS2-CounterfactualWorld.pt`
- Candidate: `Nolane-R1.6-NS2-TerminationGuard.pt`
- Dev: 18 procedural tasks, 6 per family
- Fresh: **not opened**
- Candidate checkpoint SHA-256: `cd116982d6a586b944704495742032a7c95f895ebc9cda1fc75a4e9c2516baa9`
- Candidate effective parameters: `69,133,551`

## Closed-loop results

| Checkpoint | Refinement | Total | Causal | Rule | Resource |
|---|---:|---:|---:|---:|---:|
| CounterfactualWorld | 1 | **4/18** | 1/6 | 1/6 | 2/6 |
| CounterfactualWorld | 3 | **3/18** | 1/6 | 0/6 | 2/6 |
| TerminationGuard | 1 | **2/18** | 0/6 | 0/6 | 2/6 |
| TerminationGuard | 3 | **3/18** | 0/6 | 0/6 | 3/6 |

TerminationGuard refinement=1 used 108 aggregate causal steps across six causal tasks and still solved none.

## Verdict

**REJECTED.**

The factorized terminal-action/readiness heads fit their cached training targets (`best_cached_loss ≈ 0.2022`) but did not create closed-loop capability. They removed the parent's causal and rule wins and increased causal horizon substantially. The branch is retained as negative evidence; `CounterfactualWorld` remains the strongest stable R1.6 parent at 4/18 dev.

This result is intentionally preserved so later work does not repeat the same termination-factorization idea without a materially different credit-assignment mechanism.
