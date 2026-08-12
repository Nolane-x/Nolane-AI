# R1.6 Conservative Causal-Memory Residual — Dev Result

Date: 2026-08-12 (Asia/Bangkok)

## Training

- Parent: `Nolane-R1.6-NS2-CounterfactualWorld.pt`
- Causal train worlds: **80**
- Teacher transitions: **662**
- Evidence-bearing transitions: **582**
- Trainable parameters: **409,601**
- Epochs: **12**
- Training action accuracy: ~41.1% -> ~41.2%
- Learned bounded residual scale: ~0.00862
- Candidate checkpoint: `Nolane-R1.6-NS2-ConservativeMemoryResidual.pt`
- Checkpoint SHA-256: `822ad00c1a125030fb069d2aed75bc28166f202f5faade0b0a3dc1a6259b251c`
- Candidate effective parameters: `69,543,152`
- Fresh: **not opened**

## Closed-loop dev (18 tasks, refinement=1)

| Checkpoint | Total | Causal | Rule | Resource | Mean steps |
|---|---:|---:|---:|---:|---:|
| CounterfactualWorld | **4/18** | 1/6 | 1/6 | 2/6 | 5.8333 |
| ConservativeMemoryResidual | **4/18** | 1/6 | 1/6 | 2/6 | 5.8333 |

## Verdict

**REJECTED as a capability module.** The residual was genuinely conservative: it preserved the parent exactly on the dev aggregate, but it produced no measurable causal gain. The additional 409,601 parameters are therefore not justified for the retained R1.6 candidate.

This negative result suggests that the next bottleneck is not a missing additive memory score. Training must provide a stronger planning target. The next research direction is explicit distance-to-go / counterfactual remaining-horizon supervision.
