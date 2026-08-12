# R1.6 Effect-Conditioned Structured-Atom Binder — Closed-Loop Gate

Date: 2026-08-12 (Asia/Bangkok)

Untouched slice: **dev indices 48-53/family**, 18 interactive worlds.

| Checkpoint | Total | Causal | Resource | Rule | Mean steps |
|---|---:|---:|---:|---:|---:|
| same-source PSRPlanner, binder scale=0 | **4/18** | 0/6 | 3/6 | **1/6** | 7.7778 |
| CausalEvidenceBinder | **3/18** | 0/6 | 3/6 | 0/6 | **5.9444** |

Family horizon changed substantially:

- causal mean steps: **13.17 -> 8.50** but solved remains 0/6;
- resource mean steps: 7.0 -> 6.0 with solved unchanged 3/6;
- rule: lost the control's only solved task.

## Verdict

**REJECTED.**

This is an important negative result because train-internal teacher accuracy looked strong (51.6% -> 67.7%, causal 39.1% -> 60.9%), yet interactive capability regressed. The module learned a decision boundary that shortens trajectories but does not perform successful causal correction and harms at least one compositional case.

Rejected checkpoint:

- `Nolane-R1.6-NS2-CausalEvidenceBinder.pt`
- SHA-256: `5bb02576ea4909462478bad0fe21e4abe780882730e3e3e60553ca164b10958a`
- effective experimental parameters: `71,322,619`

The retained closed-loop policy remains `Nolane-R1.6-NS2-PSRPlanner.pt` (`594e19fa...`, 70,993,913 effective parameters in its retained architecture lineage).

Next action: inspect task-level action traces to identify why the binder terminates causal episodes earlier without solving. No additional attention/capacity should be added until the behavioral failure mode is isolated.

Fresh remains unopened.
