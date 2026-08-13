# R2.0b Full-Trajectory Recursive Executive — Train Gate REJECTED

Date: 2026-08-13
Checkpoint SHA-256: `bd2c340319f00240c104905edc274542cc389b60fe6555023eff6c86578b4f88`
Effective parameters: **78,762,581**

R2.0b kept the exact R2.0a architecture and changed only supervision coverage from the first three states to complete trajectories up to 16 states. It used new train indices and a new locked gate (`580..599` per family).

## Aggregate exact solve rate
- random: 3/80 = **3.75%**
- greedy_parent: 0/80 = **0.00%**
- fixed_depth_1: 5/80 = **6.25%**
- fixed_depth_2: 4/80 = **5.00%**
- fixed_depth_8: 0/80 = **0.00%**
- adaptive: 4/80 = **5.00%**

Adaptive minus the preregistered fixed-depth-1 baseline = **-1.25 percentage points**, far below the required +10 points. `causal_prerequisites` remained **0/20** for every neural mode.

## Decision
**REJECTED.** DEV and FRESH remain unopened. R2.0b is frozen as a negative result.

## Scientific consequence
Full-trajectory supervision removed the early-state coverage limitation, but it did not make recursive imagination useful in closed loop. This falsifies the simple hypothesis that trajectory truncation was the primary cause of R2.0a failure.

The next candidate may not tune this checkpoint or reuse its gate. The next architecture must expose public per-action evidence/progress/reliability memory to the shared action scorer so that imagined futures can be conditioned on what actions have already been tried and how reliable/effective they were in the current context.
