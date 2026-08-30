# Truth / Knowledge A10 — Relation Semantics Candidate

Status: **candidate; not yet accepted or merged.**

A1–A8 remain the accepted Truth / Knowledge baseline. A9 Temporal Validity is a separate concurrent workstream and is not claimed by A10.

A10 adds canonical relation-cardinality authority under `external.knowledge` without creating a sixth family-A component. `RelationSemanticsRegistry` owns append-only revisions for `EXCLUSIVE`, `MULTI_VALUED`, and `UNSPECIFIED` relation semantics. `external.knowledge` advances to component revision `0.0.2` because its own canonical API and accepted local semantics change.

Truth protocols preserve global v1 and dependency-scope v2 byte semantics. A10 adds relation-aware scope v3 with exact Knowledge, Evidence, Epistemic, relevant relation-semantics projection, Verification, and Assurance binding. V3 closure is fail-closed for unresolved multi-object relations whose cardinality is `UNSPECIFIED`; `EXCLUSIVE` relations produce contradiction; `MULTI_VALUED` relations permit coexisting object values.

Verification and Assurance dispatch by exact binding mode. A v3 history cannot silently downgrade to v2 after a relevant relation-policy revision makes old v3 receipts stale. Irrelevant relation-policy revisions do not stale a target scope.

Historical `nolane.memory.knowledge.EvidenceLedger.conflicts()` retains its original compatibility behavior. The additive `semantic_conflicts(RelationSemanticsRegistry)` API exposes relation-aware conflicts from the canonical Knowledge parent.

Acceptance requires an exact integrated head against current `main` to pass the focused Truth Knowledge gate and full Refoundation Epoch 0 on Python 3.11 and 3.13, repository authority review, and expected-head merge verification. Until those gates pass this document is evidence of candidate intent only, not canonical acceptance.
