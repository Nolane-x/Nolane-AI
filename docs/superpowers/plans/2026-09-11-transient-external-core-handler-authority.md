# Transient External-Core Handler Authority Implementation Plan

**Goal:** Reject a TOOL decision when the concrete handler binding for the selected external core changes during inference, before the stale decision or any core side effect is persisted.

**Architecture:** Keep concrete handler-binding authority process-local in `ExternalCoreExecutor`, keyed by `tool_id`. Snapshot per-tool revisions before inference in the lineage control plane, but compare only the tool selected by the returned decision. This avoids invalidating a session when an unrelated external core is registered. Do not serialize the runtime fence.

**TDD sequence:**
1. Add a black-box regression that first-registers an authorized external-core handler through public `register_handler()` inside `backend.decide()` and returns a TOOL action for that core. Current code must dispatch it; desired behavior is `PermissionError` before decision persistence or handler execution.
2. Add permanent revision contracts: initial revision 0, first successful registration increments, exact same-handler re-registration is idempotent, unrelated tool registration does not affect the target, and rejected replacement does not advance authority.
3. Put both tests in the Neural R2.4 Result Projection gate and obtain hosted RED on Python 3.11/3.13 before production changes.
4. Implement the minimal per-tool revision API and pre-inference snapshot / post-inference selected-tool attestation.
5. Run exact-head Result Projection, External Core/version discipline, Decision Lineage, Refoundation, Memory and integrity gates. Change component metadata only if the repository version-discipline validator requires it.
6. Audit diff/reviews/base race, merge with expected-head lock, then verify push-time CI on the exact merge SHA.
