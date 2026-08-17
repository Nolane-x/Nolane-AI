# R2.51 Interprocedural Call-Flow Query Induction — Implementation Plan

1. Add RED tests for module call/return flow, query learning across call depth, and precise helper localization.
2. Build a module-wide fact graph over the same parsed AST used by candidate labels.
3. Add direct static call binding, return-to-call value flow, scoped symbols, and generic transitive `FLOW*`.
4. Add bounded interprocedural trace extraction with terminal `FLOW*` and abstract-state deduplication.
5. Learn interprocedural query-conditioned patch macros from changed/unchanged sites.
6. Localize learned macros once on the immutable pre-edit graph and reuse localization across candidate combinations.
7. Add multi-function compile/root execution and sparse executable CEGIS.
8. Add frozen six-episode held-out benchmark with unseen call depths, opaque names, decoy helpers, 10 competing macro families, and a causally observable three-edit target.
9. Run focused tests, full parent gates, frozen recompute, integrity workflows, and cross-Python checks.
10. Run Nolane World W5 adversarial audit, freeze evidence, create a complete repository release ZIP, verify SHA/unzip, and persist the release to Library.
