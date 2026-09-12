# Neural R2.5 ABA-Safe Coding Request Authority Design

## Status and base

This design closes issue #379 on top of `main@96b7d6984e7ecbc25408d5728530c16f54f78883`.

It follows the Nolane World W5 research discipline—rival hypotheses, falsifier, decisive experiment, and claim-level provenance. No claim is made that a local Nolane World runtime was executed in this environment.

## Problem

#372 made self-model authority ABA-safe with a monotonic temporal revision. #373 then made the request's full `ContextCapsule.authoritative_artifacts` live-revalidated after inference, #376 exposed that full frontier in the context receipt, and #378 added the exact applicable skill frontier.

A remaining asymmetry exists for digest-valued context authorities that are semantically reversible.

For a `core-coding` identity, `ContextCompiler._request_authority_snapshot()` includes:

```text
('coding-state', runtime.coding.digest)
```

`CodingControlPlane.digest` is the canonical digest of `CodingControlPlane.to_state()`. The current coding state stores one current `CodingAssignmentReceipt` per `work_id`. An authorized override replaces that receipt. The public control-plane API therefore permits this exact semantic sequence for one work item:

```text
A --override--> B --override--> A
```

when both A assignments use the same authorized override actor. The final current assignment can be byte-for-byte equal to the initial assignment. The event ledger records the intermediate routing operations, but the event ledger is intentionally not part of `CodingControlPlane.to_state()`. Consequently the coding digest can return to its original value.

A request compiled from the initial A state can therefore see the same final `coding-state` after inference even though its authority was revoked and restored while inference was in flight. Final-value equality is insufficient for this reversible authority.

## Rival hypotheses

### H1 — final-value authority is sufficient

Allow a decision if the final coding digest equals the request-time coding digest, even when an intermediate authorized routing mutation occurred.

This is falsified if a real A→B→A override performed inside `backend.decide()` lets the stale decision persist today.

### H2 — put the temporal witness inside canonical coding state

Add a monotonic `assignment_authority_revision` to `CodingControlPlane`. Increment it exactly when the semantic assignment for a work item changes. Persist/restore it and include it in `to_state()` once non-zero, so the existing `coding-state` digest becomes ABA-safe without adding a second execution authority channel.

This is the preferred design if RED confirms the gap.

### H3 — add an execution-only coding revision fence

Capture a separate coding revision in a new execution `ContextVar` and revalidate it after inference.

This is rejected unless H2 fails. It would duplicate authority outside `ContextCapsule.authoritative_artifacts` and make the context receipt's explicit authority surface incomplete again.

## Decisive experiment

Use a real `OrganizationRuntime.first_generation()` execution with `coding.chief` and a leased task so its request capsule contains `coding-state`.

Before stepping, establish one `CodingWorkRequest` assigned to coder A through:

```python
runtime.coding.request_work(
    request,
    override_agent_id='coding.chief',
    override_actor_id='nolane.central',
)
```

Inside `backend.decide(request)`:

1. override the same work to coder B (`coding.backend.01`);
2. prove `runtime.coding.digest` differs from the initial digest;
3. override the same work back to coder A with the same actor;
4. on the unpatched base, prove the final digest equals the initial digest;
5. return a valid WAIT decision from the stale request.

The desired authority contract is fail-closed rejection before decision/session/task/workspace persistence. Current main is expected to accept the stale decision, establishing RED.

## Surviving architecture

`CodingControlPlane` gains:

```python
assignment_authority_revision: int
```

The revision is non-negative and monotonic.

`request_work()` compares the current assignment with the newly resolved receipt. It increments the revision exactly once when the semantic assignment changes:

- first assignment: increment;
- A→B override: increment;
- B→A override: increment;
- explicit A→A override producing the exact same receipt: no increment;
- ordinary idempotent re-request that returns the existing assignment: no increment.

The revision is projected into `CodingControlPlane.to_state()` when non-zero. Therefore it is automatically part of `CodingControlPlane.digest`, which is already consumed as the canonical `coding-state` request-authority artifact. No `ContextCapsule`, `ContextCompilationReceipt`, `InferenceRequest`, decision, or execution-session field is added.

`CodingControlPlane.from_state()` restores the revision with a legacy default of zero and rejects negative values. `UICodingControlPlane.from_state()` must pass the restored base revision through when reconstructing the concrete runtime control plane.

## Why the revision belongs in coding state

The authority being protected is routing ownership of coding work, so the temporal witness belongs to the owner of that state. Putting the witness into the canonical coding semantic state has four advantages:

1. the existing context receipt explicitly commits it through `coding-state`;
2. the existing post-inference full-context fence revalidates it automatically;
3. persistence/replay can reconstruct the exact temporal frontier;
4. no parallel execution-only authority protocol is introduced.

The event ledger is not used as the witness because that would couple coding request freshness to unrelated events and overbind context.

## Persistence and compatibility

Legacy snapshots may contain assignments but no `assignment_authority_revision`. They restore with revision zero. This preserves historical readability. The first future semantic assignment change increments from zero and introduces the temporal witness.

New snapshots with a positive revision must round-trip exactly through `OrganizationRuntime.to_state()/from_state()` and through the concrete `UICodingControlPlane` reconstruction path.

The revision is included in `to_state()` only when non-zero. Empty or untouched legacy coding state therefore retains its historical canonical shape.

## Invariants

1. **ABA rejection:** a request compiled at assignment A cannot persist a decision after A→B→A during inference.
2. **Monotonicity:** every semantic assignment change advances the revision exactly once.
3. **Idempotence:** a request that leaves the exact assignment unchanged does not advance the revision.
4. **Canonical reuse:** the existing `coding-state` artifact, receipt, verifier, request digest, and execution fence remain the single authority path.
5. **No event overbinding:** unrelated event-ledger activity does not advance coding assignment authority.
6. **Legacy restore:** snapshots without the revision remain readable with revision zero.
7. **Exact restore:** modern snapshots preserve the positive revision exactly.
8. **No schema spread:** no new inference, decision, session, capsule, or context-receipt field.
9. **No frozen neural change:** Neural R2.3 weights/protocols remain untouched.

## Tests

The permanent regression suite must prove:

- real execution A→B→A inside `backend.decide()` is rejected before persistence;
- the intermediate B digest differs;
- after the fix, the final A digest differs from the request-time A digest solely because the revision advanced;
- revision sequence is `0 -> 1 -> 1 -> 2 -> 3` for first A, idempotent A, B, A;
- modern runtime snapshot round-trip preserves the revision;
- a legacy coding state with the field absent restores at revision zero;
- all existing context/execution/coding/refoundation tests remain green.

## Version discipline

Do not guess component revisions. After behavior is GREEN, run the repository's executable `nolane.metadata.version_discipline_cli` against the exact branch base and advance only the owners it reports, including their canonical projection sentinels. Public execution/integration protocol versions must remain unchanged unless the executable discipline or a direct protocol test proves otherwise.

## Integration gate

The change is mergeable only after:

1. hosted test-only RED is observed on the intended adversarial test;
2. minimal production GREEN passes the focused coding/context/execution suites;
3. executable version discipline is clean;
4. exact-head direct Neural/Memory/External Core/Refoundation gates are GREEN;
5. final diff has no temporary CI helper;
6. base has not drifted or drift is reconciled and reverified;
7. guarded merge uses the exact accepted head SHA;
8. every push workflow actually triggered on the merge SHA completes successfully.