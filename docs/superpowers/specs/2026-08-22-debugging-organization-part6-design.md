# Debugging Organization Part VI — Design Specification

## Status

Implements Issue #134 on accepted Parts I–V. The six persistent debugging-region identities already exist in the first-generation blueprint: Debug Chief, Bug Reproducer, Runtime Trace Investigator, Static Root-Cause Investigator, Concurrency & State Debugger, and Regression & Bisect Agent. Part VI turns those durable identities into a governed failure-intelligence system rather than prompt-only personas.

No unrestricted AGI/frontier coding claim is made. This part establishes evidence-bearing debugging organization/runtime behavior and bounded acceptance contracts.

## 1. Goals

1. Make failure cases durable first-class objects with immutable provenance.
2. Separate reproduction, evidence capture, hypotheses, root-cause acceptance, coding handoff and verified resolution.
3. Make specialization operational through deterministic domain routing and evidence/core requirements.
4. Preserve rejected hypotheses as negative knowledge while preventing them from masquerading as current truth.
5. Link reproduction -> root cause -> Coding Part-V patch -> independent readiness evidence end-to-end.
6. Keep Debug Chief a direct investigator and technical worker.
7. Persist exact debugging state and expose only relevant debugging state to debugging agents' context capsules.

## 2. Debug profiles and routing

`DebugProfileRegistry` derives exactly six profiles from region `debugging-failure`.

Domains:
- Debug Chief: cross-failure coordination and difficult mixed failures;
- Bug Reproducer: deterministic reproduction and minimization;
- Runtime Trace Investigator: stacks, traces, coverage and temporal state;
- Static Root-Cause Investigator: source/control/data-flow reasoning;
- Concurrency & State Debugger: races, deadlocks, ordering/state corruption;
- Regression & Bisect Agent: historical causality, regression windows and bisect evidence.

Every debugger retains the universal cognitive floor, personal memory/skills/self-model and accepted neural lineage from Part I. Routing is deterministic; role names do not prove capability.

## 3. Failure cases

A `FailureCase` contains:
- case id and task id;
- title/symptom;
- failure class;
- affected component/file/symbol refs;
- initial evidence refs;
- reporter;
- status;
- accepted root-cause hypothesis id when one exists.

Lifecycle:
`OPEN -> REPRODUCED -> ROOT_CAUSE_ACCEPTED -> PATCH_IN_PROGRESS -> VERIFIED -> RESOLVED`.

A case may also become `QUARANTINED` or `CLOSED_UNRESOLVED`; transitions are explicit and history-bearing.

## 4. Reproduction evidence

A `ReproductionReceipt` records:
- reproducer identity;
- deterministic/not deterministic;
- minimized/not minimized;
- environment digest;
- failure fingerprint;
- reproducer artifact refs;
- evidence refs.

A case cannot move to `REPRODUCED` without a deterministic reproduction receipt. Non-deterministic attempts remain preserved as evidence but do not satisfy that gate.

## 5. Evidence timeline

`DebugEvidenceArtifact` records typed evidence:
- runtime trace;
- stack trace;
- coverage;
- state diff;
- static/data/control-flow;
- concurrency trace;
- bisect/regression evidence;
- crash/core-dump;
- log correlation;
- profiler evidence.

Each artifact binds producer, case, logical sequence, input/output artifact refs and evidence refs. The timeline is append-only.

## 6. Competing hypotheses

`DebugHypothesis` records statement, proposer, supporting/refuting evidence refs, confidence and status:
- `ACTIVE`;
- `REJECTED`;
- `ACCEPTED`.

Rejecting a hypothesis preserves it and its refutation evidence. Only one accepted root cause may be current for a case. A rejected hypothesis can never be promoted to accepted without a new hypothesis object.

Root-cause acceptance requires:
- deterministic reproduction;
- at least one supporting evidence artifact;
- explicit Debug-Chief authorization;
- for concurrency/state failures: at least one `CONCURRENCY_TRACE` artifact;
- for regression failures: at least one `BISECT` artifact.

## 7. Coding handoff and resolution

Part VI reuses Part V rather than implementing a second patch system.

`DebugPatchHandoff` binds:
- case id;
- accepted hypothesis id;
- coding work id/task id;
- selected coder assignment digest;
- affected source refs;
- debugging evidence refs.

The handoff calls the existing `CodingControlPlane.request_work` and moves the case to `PATCH_IN_PROGRESS`. Debug authority cannot bypass CodeClaimLedger, patch provenance or Coding readiness rules.

`DebugResolutionReceipt` is accepted only when:
- handoff exists for case/hypothesis;
- referenced Part-V patch belongs to the handoff work/task;
- referenced Part-V `CodingReadinessReceipt.ready == True`;
- the current accepted root cause is unchanged;
- no contradictory active debugging evidence is unresolved.

Then the case becomes `RESOLVED`. Debugging never merges code itself.

## 8. Direct Debug-Chief work

Acceptance includes a difficult case/task leased to `debug.chief`. The Chief personally records reproduction/evidence, proposes and accepts a root cause, produces an investigation artifact and completes the task via ordinary `chief_direct_work`. This prevents manager-only degeneration.

## 9. Learning and bug memory

Failure cases, rejected hypotheses and evidence remain durable negative/positive experience. `DebugControlPlane.propose_personal_skill_from_resolution` may create a Part-I personal skill candidate for the resolver, but it remains `CANDIDATE` until normal evidence-gated promotion. Failed hypotheses cannot directly become skills.

## 10. Snapshot and context

Runtime gains `runtime.debugging: DebugControlPlane` and persists profiles, cases, reproductions, evidence timeline, hypotheses, handoffs, resolutions and counters.

For agents in `debugging-failure`, Context Compiler adds `('debugging-state', runtime.debugging.digest)` plus event delta since checkpoint. Other regions do not receive the full debugging-state digest by default.

## 11. Fail-closed rules

- unknown/non-debug profile -> reject debug routing;
- duplicate case id rebinding -> reject;
- reproduction without evidence/fingerprint/environment -> reject;
- non-deterministic reproduction does not satisfy reproduced gate;
- rejected hypothesis cannot become accepted in place;
- root cause without deterministic reproduction/supporting evidence -> reject;
- concurrency root cause without concurrency evidence -> reject;
- regression root cause without bisect evidence -> reject;
- coding handoff without accepted current root cause -> reject;
- resolution without Part-V ready patch -> reject;
- snapshot counters/references/digests inconsistent -> reject;
- no automatic source mutation or merge from debugging authority.

## 12. Acceptance tests

- exactly six persistent debugging profiles with non-identical domains/cores;
- deterministic routing for reproduction/trace/static/concurrency/regression/cross-failure work;
- deterministic reproduction gate and append-only evidence timeline;
- competing hypotheses retain rejected history and one current accepted root cause;
- dedicated concurrency/root-cause evidence gate;
- dedicated regression/bisect evidence gate;
- accepted root cause -> Part-V coding handoff -> ready patch -> resolution provenance;
- direct Debug-Chief investigation and personal skill candidate;
- exact snapshot/restore and debugging-state context reference;
- all Parts I–V regressions remain green on Python 3.11/3.13.
