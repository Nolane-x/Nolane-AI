# R1.6 Dual-Role two-slice gate completed

Date: 2026-08-12

The Dual-Role Causal Binder was evaluated against the accepted PSRPlanner control on two disjoint held-out dev slices: 54–59 and 60–65 per family.

A machine gate, not manual interpretation, selected `checkpoints/Nolane-R1.6-NS2-CurrentBest.pt` using this preregistered rule:

> accept Dual-Role only if it solves strictly more closed-loop tasks than PSRPlanner on **both** held-out slices; otherwise keep PSRPlanner.

The exact machine-readable decision is stored locally as `results/r1_6_dual_role_gate_decision.json` and is included in the authoritative R1.6 live recovery artifact. The current GitHub connector is not used to transcribe binary/model artifacts by hand after the earlier byte-integrity audit.

Research after this point must use `CurrentBest.pt` as the parent selector rather than choosing a checkpoint from a single favorable slice.
