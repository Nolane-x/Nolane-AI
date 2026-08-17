# R2.50 → R2.51 Evolution

R2.50 removed R2.49's hand-authored high-level context vocabulary by inducing relational query structure from low-level program facts. Its strongest remaining counterexample was representational scope: a bug in a helper function could be invisible to a single-function graph even when tests observed the caller failure.

R2.51 closes that counterexample for a bounded static Python setting. It adds module-wide call/argument/return value flow, learns localization queries across helper/caller boundaries, transfers from training call depths 1-2 to heldout depths 4-5, and applies multiple edits transactionally after immutable pre-edit localization.

The next falsifiable boundary is cross-file/import-aware repair: caller and helper in separate modules, opaque module names, decoy imports, atomic multi-file edits, isolated package execution, and rollback on any failed gate. Dynamic dispatch, recursion, noisy tests and repository-scale search remain subsequent frontiers.
