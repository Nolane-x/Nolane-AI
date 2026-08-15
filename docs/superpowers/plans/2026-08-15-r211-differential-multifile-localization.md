# R2.11 Differential Multi-File Localization Implementation Plan

**Goal:** Add +0-param hierarchical multi-file localization from coverage spectrum + differential behavior, then verify end-to-end with R2.10 + R2.9.

1. Write RED tests for path/node-id exclusion and identity permutation.
2. Implement reachable-symbol graph traversal and anonymous localization scores.
3. Build multi-file JavaScript executable protocol with randomized identities and off-path distractors.
4. Add a healthy shadow implementation with identical coverage spectrum to force a real ambiguity.
5. Ablate R2.10 edit-gain on DEV; disable it if it harms localization.
6. Add differential peer-behavior consensus as public execution evidence.
7. Validate on multiple DEV seeds; freeze heldout thresholds/source hashes before measurement.
8. Measure file/symbol localization independently from repair.
9. Handoff top symbol to unchanged R2.10 proposal and R2.9 verifier under budget 2.
10. Require identity permutation invariance, zero false accepts, +0 params, GitHub CI reproduction, full ZIP and Library persistence.
