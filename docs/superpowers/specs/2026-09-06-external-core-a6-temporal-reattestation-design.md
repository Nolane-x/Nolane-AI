# External Core A6 — Temporal Re-attestation

## Status

Approved continuation from A5 under the user's standing instruction to proceed without per-step approval pauses.

## Governing law

> A structural-currentness snapshot is current only for the exact observation epoch it proves; time/epoch identity may not be recorded without being re-attested.

A6 is a narrow post-A5 hardening of `external.integration`. It is not a new External Core family, not family H, not a governor, orchestrator, invoker, Verification or Assurance authority, and not an authorization, execution, promotion, release, deployment, repair, migration, or auto-refresh mechanism.

## Problem

A5 made `CanonicalAdmissionContext` content-addressed over the canonical registry, canonical authority graph, six live frontier digests, and an explicit non-negative `observed_epoch`. The epoch is therefore part of snapshot identity.

However, the A5 live audit re-attests the registry, authority graph, and six live frontiers while never re-attesting `observed_epoch` when a persisted `CanonicalAdmissionBundle` is supplied. Re-admission also uses the bundle's historical context, so a bundle admitted at epoch N can remain audit-clean at epoch N+1 when every other digest is unchanged.

That is a temporal replay gap: the system records temporal currentness evidence but does not require live temporal proof before calling the persisted bundle clean.

## Compatibility posture

A6 preserves A5 admission-state compatibility and changes only live-audit qualification semantics.

- Existing `external-integration-admission-v2` context, receipt, wrapper, and bundle serialized states remain restorable byte-semantically unchanged.
- Existing A2/A3/A4 state remains unchanged.
- No historical A5 bundle is rewritten or auto-migrated.
- A6 adds a stricter current/live audit protocol and explicit live epoch input.
- Building and auditing a fresh bundle in the same call remains deterministic and clean when the supplied observation epoch is exact.

## Ownership and versioning

A6 remains owned exclusively by `external.integration`.

Accepted local semantic revision:

- `external.integration`: `0.0.4 -> 0.0.5`

The canonical `nolane.external_core.integration` surface, `integration_admission`, and `integration_admission_bundle` secondary surfaces must project the same component identity/version. No unrelated component version is advanced.

A6 audit protocol becomes `external-integration-admission-audit-v2`. Admission protocol remains `external-integration-admission-v2`; the underlying admission artifacts are not reformatted.

## Live observation epoch contract

The audit distinguishes the persisted admission epoch from the live observation epoch.

For an explicitly supplied persisted bundle:

1. the bundle's `context.observed_epoch` is historical snapshot evidence;
2. the caller must provide an explicit live observation epoch;
3. the live epoch must be an exact non-negative `int` (`bool` is rejected);
4. missing live epoch proof produces categorical finding `CURRENT_OBSERVATION_EPOCH_UNAVAILABLE`;
5. invalid live epoch input produces `CURRENT_OBSERVATION_EPOCH_INVALID`;
6. an exact integer different from the bound epoch produces `OBSERVATION_EPOCH_CONTEXT_MISMATCH`;
7. only exact equality allows the temporal dimension of the audit to be clean.

For `bundle=None`, the canonical audit builder constructs the bundle from the supplied `observed_epoch` and reuses that exact epoch as the live observation proof. The no-argument canonical audit continues to use epoch 0, preserving its existing CLI/default behavior.

A6 intentionally does **not** accept `current_epoch >= admitted_epoch`. A later epoch is not proof that the old snapshot was re-observed at the new epoch; exact live re-attestation is required.

## API design

`run_canonical_admission_audit` gains a separate keyword-only live epoch input for persisted-bundle auditing while retaining `observed_epoch` as the canonical-builder epoch.

Preferred shape:

```python
run_canonical_admission_audit(
    *,
    bundle: CanonicalAdmissionBundle | None = None,
    observed_epoch: int = 0,
    current_observed_epoch: int | None = None,
    ...existing live frontier inputs...,
)
```

Semantics:

- `bundle is None`: `current_observed_epoch` may be omitted; the effective live epoch is `observed_epoch`.
- `bundle is not None`: `current_observed_epoch` is independent live proof and must be explicitly supplied.
- Supplying `current_observed_epoch` while building a fresh bundle is legal only when it exactly equals `observed_epoch`; mismatch yields the same categorical temporal mismatch rather than silently auditing two epochs.

The CLI's existing `--observed-epoch` remains sufficient because CLI audit builds a fresh canonical bundle in-process. No new repair, mutation, refresh, or migration flag is introduced.

## Audit order

A6 keeps the audit read-only and deterministic.

1. validate bundle integrity;
2. build current canonical registry/profile;
3. validate/re-attest live observation epoch;
4. re-attest registry and authority graph;
5. re-attest all six live frontiers;
6. replay semantic admission for manifests/graph and, when live proof is available, handoffs/traces;
7. sort categorical findings deterministically into the content-addressed audit report.

Temporal findings do not suppress independent structural findings; the report can expose epoch drift and registry/frontier drift together.

## Adversarial matrix

Permanent tests must prove at least:

- epoch-N bundle + live epoch N is clean;
- epoch-N bundle + no live epoch fails closed with `CURRENT_OBSERVATION_EPOCH_UNAVAILABLE`;
- epoch-N bundle + live epoch N+1 yields `OBSERVATION_EPOCH_CONTEXT_MISMATCH` even when registry and all six frontiers are unchanged;
- epoch-N bundle + live epoch N-1 also yields mismatch;
- `True`, `False`, float, string, bytes, enum-like objects, and negative integers are invalid live epochs and never coerce;
- fresh in-process canonical audit at epoch N remains clean without duplicating the epoch argument;
- explicit fresh-builder live epoch mismatch is reported;
- temporal mismatch can coexist deterministically with registry/frontier mismatch;
- A5 forged/self-issued receipt defenses remain intact;
- historical A5 admission bundle restore remains unchanged.

## TDD and closure

Implementation is RED -> GREEN:

1. first commit tests proving persisted epoch replay is currently accepted and that missing/invalid live epoch proof is not fail-closed;
2. run External Core CI on that exact RED head and record the intended failures;
3. minimally implement explicit live epoch re-attestation and audit-v2/version projection;
4. run exact-head Python 3.11 + 3.13 External Core contracts, component-local version discipline, component projection, A2/A3 audit, A6 audit, and prior G/Assurance regressions;
5. run broader Refoundation/Truth/Knowledge/Memory/E-Acting gates on the exact synthetic merge-ref before any merge decision;
6. frozen historical release witnesses remain frozen and are not rewritten for cosmetic green CI.

## Success criteria

A6 is complete when a persisted canonical admission bundle cannot remain live-audit-clean merely because all non-temporal digests are unchanged: the exact observation epoch must be re-observed and match. The change must preserve all historical admission serialization, keep currentness descriptive rather than authoritative, and introduce no authority outside `external.integration`.