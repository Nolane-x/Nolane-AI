# R1.6 Production PSRPlanner — Reproduction + Independent Replication

Date: 2026-08-12 (Asia/Bangkok)

## Production checkpoint

The train-only calibrated external PSR rollout weight was integrated into production `forward()` as a single bounded scalar.

- parent weights: `Nolane-R1.6-NS2-PredictiveState.pt`
- alpha: `1.2104157209396362`
- raw scale: `atanh(alpha / 2) = 0.7013245821`
- rollout horizon: 2
- discount: 0.7
- production candidate: `Nolane-R1.6-NS2-PSRPlanner.pt`
- SHA-256: `594e19faaf07094532d86629457dd81322113f06f7a932e05b07367f3c5dbb90`
- effective candidate parameters: **70,993,913**
- fresh: unopened.

## Exact reproduction of original policy gate

Dev indices 24-29/family:

- external diagnostic PSR rollout: **4/18**, causal 0/6, resource 3/6, rule 1/6, mean steps 7.06
- production `forward()` PSRPlanner: **4/18**, causal 0/6, resource 3/6, rule 1/6, mean steps 7.06

Production integration therefore reproduces the calibrated diagnostic exactly at task-level aggregate/family metrics.

## Independent replication gate

A new untouched slice, dev indices **30-35/family**, was then evaluated with the same locked checkpoint and scale.

| Policy | Total | Causal | Resource | Rule | Mean steps |
|---|---:|---:|---:|---:|---:|
| same PSR weights, planning off | **3/18 (16.7%)** | 0/6 | 3/6 | 0/6 | 7.17 |
| locked PSRPlanner | **5/18 (27.8%)** | **1/6** | 3/6 | **1/6** | **6.78** |

## Verdict

**PASS — PSRPlanner retained as the strongest current R1.6 closed-loop candidate.**

The planning gain replicated on two independent held-out dev slices:

1. dev24-29: **2/18 -> 4/18**
2. dev30-35: **3/18 -> 5/18**

The second replication also improved mean action horizon and produced the first causal-identification win on these later untouched policy slices.

This is materially stronger evidence than teacher-forced accuracy: the same learned predictive-state model and locked scalar improve actual interactive completion over a same-weights no-planning control.

Next work should target causal identification specifically while preserving PSRPlanner behavior on resource/rule. Fresh remains unopened until the candidate is either causally strengthened or explicitly locked as the R1.6 final candidate.
