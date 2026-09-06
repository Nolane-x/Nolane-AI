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

### Frozen admission-v2 artifact lane

A5 receipts content-address `owner_component_version`, and `ProtocolAdmissionReceipt.from_state()` validates that owner version. Therefore changing the admission-v2 implementation constant from `0.0.4` to `0.0.5` would silently make existing A5 receipts non-restorable even though their protocol and serialized schema did not change.

A6 therefore deliberately freezes the artifact issuer lane:

- `nolane.external_core.integration_admission.COMPONENT_VERSION == "0.0.4"`
- `ADMISSION_PROTOCOL == "external-integration-admission-v2"`
- historical A5 receipt identities remain unchanged and exactly restorable.

This frozen artifact version is not the current canonical component revision. It is the version embedded in the unchanged admission-v2 artifact identity contract.

## Ownership and versioning

A6 remains owned exclusively by `external.integration`.

Accepted current local semantic revision:

- canonical `external.integration`: `0.0.4 -> 0.0.5`
- `nolane.external_core.integration.COMPONENT_VERSION`: `0.0.5`
- `nolane.external_core.compatibility.SEMANTIC_SURFACE_VERSION`: `0.0.5`
- `nolane.external_core.integration_admission_bundle.COMPONENT_VERSION`: `0.0.5`
- canonical component revision table: `external.integration == 5`
- frozen `integration_admission` artifact issuer: `0.0.4` under unchanged admission-v2 identity semantics.

No unrelated component version is advanced. There is no global External Core version.

A6 audit protocol becomes `external-integration-admission-audit-v2` and its report digest namespace becomes `admission-audit-v2-*`. Admission protocol remains `external-integration-admission-v2`; admission bundle protocol remains `external-integration-admission-bundle-v2`.

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

Permanent tests prove or must preserve:

- epoch-N bundle + live epoch N is clean;
- epoch-N bundle + no live epoch fails closed with `CURRENT_OBSERVATION_EPOCH_UNAVAILABLE`;
- epoch-N bundle + live epoch N+1 yields `OBSERVATION_EPOCH_CONTEXT_MISMATCH` even when registry and all six frontiers are unchanged;
- epoch-N bundle + live epoch N-1 also yields mismatch;
- `True`, `False`, float, string, bytes, enum-like objects, and negative integers are invalid live epochs and never coerce;
- fresh in-process canonical audit at epoch N remains clean without duplicating the epoch argument;
- explicit fresh-builder live epoch mismatch is reported;
- temporal mismatch can coexist deterministically with registry/frontier mismatch;
- A5 forged/self-issued receipt defenses remain intact;
- admission-v2 receipts continue to embed owner `external.integration` version `0.0.4` and round-trip exactly;
- historical A5 admission bundle restore remains unchanged.

## TDD evidence

A6 was driven through explicit RED -> GREEN cycles before version closure:

1. Missing live epoch proof — RED head `25e4c730187c035a678ca147370cec764721da0b`: 267 passed / exactly 1 failed; persisted epoch-11 bundle audited clean without any live epoch proof.
2. Epoch drift replay — RED head `c4b4056d23f7e83129bee7fd78c5b2a0831b0ad4`: 269 passed / exactly 2 failed; live epochs 10 and 12 were accepted clean while exact 11 passed.
3. Type laundering — RED head `c9602506e559a02ab52f426d9521690bc9cc7fdb`: 271 passed / exactly 6 failed; `True`, `False`, `-1`, `1.0`, `"11"`, and `b"11"` were misclassified as ordinary drift rather than invalid temporal evidence.
4. GREEN behavior head `9d04aa612db6474e4dc5f3f4de833b9573373076`: 277 External Core contracts passed on Python 3.11 and 3.13; the only remaining gate finding was the intentional `SEMANTIC_CHANGE_WITHOUT_REVISION` for `external.integration`, which triggers the A6 patch revision closure.

## Closure requirements

- exact-head Python 3.11 + 3.13 External Core contracts pass;
- component-local version discipline reports zero findings after revision 5 projection;
- canonical component projection passes;
- canonical A2/A3 coherence audit and A6 admission audit are clean;
- prior G/Assurance regressions pass;
- broader Refoundation/Truth/Knowledge/Memory/E-Acting gates pass on the exact synthetic merge-ref before merge;
- frozen historical release witnesses remain frozen and are not rewritten for cosmetic green CI.

## Success criteria

A6 is complete when a persisted canonical admission bundle cannot remain live-audit-clean merely because all non-temporal digests are unchanged: the exact observation epoch must be re-observed and match. The change must preserve all historical admission serialization, keep currentness descriptive rather than authoritative, and introduce no authority outside `external.integration`.