# Nolane R2.0g Compute-Utility Selector — Train Gate Rejected

Date: 2026-08-13

**REJECTED.** On locked FIGG-18 train indices 1680..1699, frozen R2.0e depth1 solved 27/80 (33.75%) while the 9,778-parameter per-step adaptive depth1/2 selector solved 22/80 (27.5%), a -6.25 pp regression. Family deltas were conditional -5 pp, regime -10 pp, implicit -5 pp, causal -5 pp. DEV/FRESH remain closed.

The selector achieved 90.23% routing accuracy on routeable teacher-forced validation states, but this did not transfer to closed-loop episode success. The failure identifies distribution shift from per-step routing as the issue: an early wrong depth choice moves the episode to states absent from the selector's teacher trajectory.

The same gate showed depth1/depth2 oracle union 35/80 (43.75%), with 8 depth2-only and 13 depth1-only solved tasks. R2.0h therefore moves routing to episode level and trains directly from full closed-loop solve labels.
