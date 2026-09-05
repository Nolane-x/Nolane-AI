# External Core A3 — Canonical Registry & Live Coherence Implementation Plan

> Implement with strict RED → GREEN → REFACTOR cycles. Production code must not precede the failing test that requires it.

## Goal

Bind the A2 External Core Coherence Fabric to canonical component identity/version and deterministic live frontiers without creating a new authority owner.

## Task 1 — Registry RED

Create `tests/test_external_core_a3_registry.py` with failing requirements for:
- immutable content-addressed manifest adapters,
- adapter/manifest identity and version equality,
- deterministic registry digest independent of input order,
- duplicate component/adapter rejection,
- exact registry restore and tamper rejection,
- categorical coverage findings,
- descriptive-only capability catalog binding.

Verify hosted CI fails because A3 registry production symbols do not exist.

## Task 2 — Registry GREEN

Create `nolane/external_core/registry.py` with:
- `ManifestAdapter`,
- `CanonicalComponentRegistry`,
- `RegistryCoverageFinding` / `RegistryCoverageReport`,
- `CapabilityCatalogBindingReceipt`,
- canonical JSON/digest helpers reused from A2 where safe.

Keep all APIs immutable/read-only. Verify A3 registry tests green and A2 regressions unchanged.

## Task 3 — Live frontier RED

Create `tests/test_external_core_a3_live_coherence.py` requiring:
- deterministic handoff/work-trace/source-state frontier digests,
- exact `LiveExternalCoreSnapshot` round trip,
- categorical restore assessment,
- registry/version drift → `REQUIRES_REVALIDATION`,
- malformed/tampered snapshot → rejection/quarantine,
- missing current proof → `UNKNOWN`,
- exact current state → `CURRENT`,
- registry-backed live audit.

Verify the new tests fail for missing live-coherence production symbols.

## Task 4 — Live frontier GREEN

Create `nolane/external_core/live_fabric.py` and extend `coherence_audit.py` with registry-backed audit and restore assessment. Preserve A2 APIs.

## Task 5 — Canonical adapter population RED

Create `tests/test_external_core_a3_adversarial.py` requiring:
- canonical builder reads component class identity/version dynamically,
- no duplicate semantic component,
- forged identity/version rejected,
- authority laundering rejected by existing authority graph rules,
- capability receipt cannot claim grant semantics,
- registry rollback/mixed-version/frontier substitution fail closed,
- discovery exposes no mutation/invocation methods.

## Task 6 — Canonical integration GREEN

Refactor `nolane/external_core/audit.py` so the canonical profile is derived from `build_canonical_registry()` and live frontier state. Preserve `build_canonical_fabric_profile()` for compatibility.

Extend `capability_discovery.py` with registry-backed read-only discovery while retaining A2 APIs. Export only structural A3 APIs from `nolane/external_core/__init__.py`.

## Task 7 — CURRENT + CI

Document A3 in `CURRENT/EXTERNAL_CORE.md`, including the governing law and explicit non-authority boundary.

Upgrade `.github/workflows/external-core-a2.yml` into an A2+A3 gate while preserving its file path/history:
- trigger on the A3 branch and A3 test paths,
- compile canonical namespaces,
- run G + A2 + A3 tests,
- run canonical audit CLI,
- run prior G/Assurance regressions,
- matrix Python 3.11/3.13.

## Task 8 — Verification and review

At exact head:
- A2+A3 CI: Python 3.11 success,
- A2+A3 CI: Python 3.13 success,
- Refoundation workflow: Python 3.11 success,
- Refoundation workflow: Python 3.13 success,
- inspect PR diff and high-risk authority seams,
- apply fixes through fresh RED→GREEN cycles if any defect is found,
- update PR evidence and mark ready for review.

Do not merge without an explicit merge request from the user.
