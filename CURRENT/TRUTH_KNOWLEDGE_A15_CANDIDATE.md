# Truth / Knowledge A15 — Context-Qualified Truth Candidate

Status: **implementation candidate; not accepted and not canonical until exact integrated-head gates pass and the production change is merged.**

A1–A14 remain the accepted family-A baseline. A15 extends that baseline additively through dedicated v9 sidecars and does not create a sixth family-A authority.

## Authority boundary

Family A remains exactly:

1. `external.evidence`
2. `external.knowledge`
3. `external.epistemic`
4. `external.verification`
5. `external.assurance`

A15 sidecars declare only their existing `PARENT_COMPONENT_ID`; none declares `COMPONENT_ID`.

## V9 binding mode

```text
context-dependence-defeasible-justification-provenance-lineage-temporal-v9
```

Context is an applicability dimension only. It is never a source-independence dimension and cannot mint verification credit.

## Evidence / Knowledge context

`TruthContext` is explicit, deterministic and content-addressed. Required qualifiers are canonical sorted key/value pairs. Caller-supplied extra qualifiers are allowed, while every required qualifier must be present with the exact value.

`ClaimContextBindingRegistry` and `EvidenceContextBindingRegistry` are append-only sidecars bound to immutable base content digests. First revision is exactly 1 without predecessor; later revisions advance exactly once and bind the exact predecessor digest. Unbound claims and Evidence remain global for compatibility.

## Epistemic v9

`ContextEpistemicJudge` preserves the A14 dependence/provenance/defeasible/temporal audit scope and re-evaluates applicability under explicit `TruthContext`.

A context-mismatched target is `UNKNOWN`, not silently dropped. Context-mismatched required parents or Evidence break only the affected derivation path. A dead context-invalid alternative cannot veto a separate live supported path. Disjoint contextual competitors do not become live contradictions merely because they share subject/relation identity.

`ContextTruthScope` binds the exact TruthContext, relevant claim/evidence context projections, v8 audit dependence state, assessments, justification/undercutter states, contradictions, debt, mismatch IDs and canonical digest.

## Verification v9

`ContextTruthVerificationReceipt` exact-binds:

- claim and verifier identity;
- channel and pass/fail result;
- exact v9 scope digest;
- exact TruthContext digest;
- exact TemporalContext digest and `as_of`;
- verification Evidence IDs;
- verifier provenance projection;
- verifier source-dependence projection;
- verification-Evidence context projection.

`ContextTruthVerificationLedger` rejects v8 masquerading, retains negative receipts, checks live Evidence applicability in the exact TruthContext, and preserves the A14 common-basis/controller collapse algorithm unchanged. Context never appears in an independence key.

Relevant verification-Evidence context revision stales the receipt. Unrelated context revisions do not.

## Assurance v9

`ContextTruthClosureCertificate` binds exact v9 epistemic scope, exact v9 verification projection, exact TruthContext/TemporalContext, accepted verification receipts, epistemic debt, closure decision/reasons and canonical digest.

`ContextTruthAssuranceGate` re-derives live authority rather than trusting certificate content. It preserves A14 thresholds:

- LOW/STANDARD: 1 independent verifier + 1 channel;
- HIGH: 2 independent verifiers + 2 channels;
- CRITICAL: 3 independent verifiers + 3 channels.

Closure fails on target context mismatch, unsupported/conflicted live truth, contributing-lineage defects, critical epistemic debt, incomplete provenance/dependence, invalid context/provenance/dependence verification, negative verification, or insufficient diversity.

## Compatibility law

With empty `TruthContext` plus empty claim/evidence context registries, A15 must reproduce the accepted A14 epistemic semantics. V8 protocol objects remain historical exact modes and cannot masquerade as v9.

## Adversarial design transfer from Nolane World 0.12.0

A15 uses Nolane World only as an external reasoning/adversarial harness, never as Nolane AI authority. The relevant transferred invariants are:

- context reset must preserve explicit anchors and re-check environmental drift;
- proxy success must not substitute for the property being proved;
- source/common-basis dependence must not be washed away by a new label;
- verifier outputs must bind their exact evidence/context state;
- context changes must not mint independence.

These invariants are encoded as repository tests rather than trusted as design prose.

## Current evidence chain

- Verification RED: `8d17f9ae920a7bd0e0b4611a0553c7d0bdee15ed`; GitHub Actions run `33397195863` failed exactly because `verification_context_truth` did not exist while prior family-A compile stayed green.
- Verification implementation: `ecc29d18abf068764cc39cbc70855dc7ebb3350f`.
- Verification authority regression: `1651c40f6598deaf1977ae009d69a956342f349f`.
- Assurance RED: `3b36db1ec6a5378c47386b939aeafab4c3cf09ac`.
- Assurance implementation: `986723cb801b1b52fd70285be73a6aa9012e7418`.
- Five-authority hardening: `2732bffdab7f5e17dfdffcf7fc37da900abc1f73`.
- Empty-context v8 compatibility hardening: `298ca8171be94d2a47b54400dce8c9f55e60e389`.
- CI surface extended through A15/v9: `266641661214f575c6b254f4f1cbc00c7e04b067`, Truth Knowledge A Layer run `33398660889` pending at candidate-record time.

No SHA in this document is an acceptance claim. Acceptance requires fresh exact-head Truth gates, integration on the latest `main`, full Refoundation/release gates, race guard, intended-only diff and merge of the exact tested integrated head.
