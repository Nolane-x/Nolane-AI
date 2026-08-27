# Refoundation Epoch 0 Wave 5B — Native Evidence Primitive

## Scope

Wave 5B migrates exactly one semantic component: `external.evidence`.

Canonical ownership becomes `nolane.external_core.evidence.EvidenceRecord`. Existing imports through `cogcoder.organization.types.EvidenceRecord` and `cogcoder.organization.EvidenceRecord` remain compatibility surfaces and must resolve to the same class object.

## Why this tranche

`external.evidence` is currently `legacy_internal` because `EvidenceRecord` is embedded in `cogcoder.organization.types`. That module also contains identity, event, memory and context schemas, so moving the whole file would create unnecessary blast radius. `EvidenceRecord` itself is independent: it only needs dataclass validation and state serialization.

## Non-goals

Do not migrate `core.canonical_digest`, `schemas.identity`, memory, knowledge, skills, self-model, context, retrieval, execution or evaluation in this tranche. Do not invent a new evidence ledger. Do not delete historical source paths or frozen evidence.

## Zero-loss invariants

- Preserve all `EvidenceRecord` fields, defaults, validation, `to_state`, and `from_state` behavior.
- Legacy imports preserve exact class identity.
- Canonical class authority moves to `nolane.external_core.evidence`.
- Canonical evidence code does not import the historical owner.
- Advance only `external.evidence` from `0.0.0` to `0.0.1` in Wave 5B.
- Mark it `canonical_native` with canonical write authority.
- Reduce non-native debt exactly 44 → 43 and `legacy_internal` exactly 5 → 4; other debt counts stay unchanged.
- Keep repository-history quarantine unchanged unless separately proven safe.
- Preserve all prior Refoundation, 67-AI, regression and frozen Neural R2.3 gates.

## Implementation

Create `nolane/external_core/evidence.py` with the accepted `EvidenceRecord` implementation and component metadata. Replace only the local `EvidenceRecord` definition in `cogcoder/organization/types.py` with a canonical import. Update component revision and implementation-status authority metadata. Materialize native-debt projections deterministically.

## Acceptance

Accept only when an exact head passes the complete Refoundation workflow on Python 3.11 and 3.13: compile, AI dossier freshness, repository audit, all Refoundation contracts, zero-loss evidence, organization/campaign/execution regressions, and frozen Neural R2.3 metadata.
