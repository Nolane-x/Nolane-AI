# Refoundation Epoch 0 Wave 5N — Native Planning Implementation Plan

## Goal

Cut over `external.planning` to canonical native ownership and remove dual mutable plan-version authority without losing historical compatibility.

## Baseline

- Base: accepted Wave 5M exact head `64a78eaf189bbbf61fd74125b1c93738da4a839a`.
- Native debt: 32.
- `nolane.external_core.planning` is still a 0.0.0 facade over `cogcoder.organization.planning`.
- `TaskGraph.plan_version` currently starts at 1 and mutates independently.
- `MasterPlanGraph.version` starts at 0 and mutates independently.

## Execution sequence

### 1. Freeze semantic boundary

Record the design in the Wave 5N spec. Do not expand scope into Architecture, leases, execution, coding, or Requirements redesign.

### 2. TDD RED

Add `tests/test_refoundation_wave5n_native_planning.py` before production changes. The suite must prove:

- canonical Planning does not yet own its public classes;
- historical Planning is not yet an exact bridge;
- TaskGraph starts from the wrong independent clock and exposes writable revision state;
- Planning mutations do not project their revision into TaskGraph;
- canonical persistence marker/mismatch rules are absent;
- component/version/facade/debt metadata still describe Planning as non-native.

Open a Draft PR and capture hosted RED evidence. RED is expected only for Wave 5N contracts; unrelated regressions are blockers.

### 3. Canonical Planning implementation

Move the complete accepted Planning implementation into `nolane/external_core/planning.py` and import accepted canonical dependencies wherever their ownership is already native. Add component metadata `external.planning` / `0.0.1` / migrated historical path.

Replace `cogcoder/organization/planning.py` with an explicit re-export bridge whose public classes are exact canonical identities.

### 4. Remove the second plan clock

Advance `organization.tasks` to 0.0.2.

- replace public writable `plan_version` storage with a read-only property backed by private projection state;
- fresh projection begins at 0;
- add a Planning-only binding/projection boundary;
- reject backward revision projection;
- keep the historical amendment entrypoint, but delegate to Planning authority and fail closed when unbound;
- serialize the `external.planning` authority marker.

Planning must project its graph version and node IDs after every successful revision, rollback, gap application, and compatibility amendment.

### 5. Restore invariants

Composition/restoration must reconcile TaskGraph and Planning graph exactly once:

- marked canonical state must match exactly;
- matching legacy state is adopted;
- only the historical empty bootstrap mismatch 1/0 is normalized to 0;
- all other mismatches fail closed.

### 6. Authority bookkeeping

- `external.planning`: revision 1, canonical-native, canonical write authority, version 0.0.1;
- `organization.tasks`: revision 2, version 0.0.2;
- remove `external.planning` from active facades;
- update forward-compatible acceptance sets without weakening prior-wave invariants.

### 7. Generated truth

Run the repository audit writer using the same temporary-carrier pattern already accepted in Epoch 0 if connector-only execution requires it. Commit generated projections, remove the carrier, and require `python -m nolane.repository.audit --check` to pass byte-exact on the final source head.

Expected debt: 31, with only `external.planning` removed in this wave.

### 8. Fresh exact-head acceptance

Require hosted success on Python 3.11 and 3.13 for:

- compile;
- 67/67 dossier freshness;
- repository audit freshness;
- all `tests/test_refoundation_*.py`;
- zero-loss evidence;
- organization/campaign/execution regressions;
- frozen Neural R2.3 metadata;
- migration-carrier cleanup guard.

Only then update PR metadata with the exact source SHA, workflow run, and evidence artifact digests and mark Ready for Review. Do not auto-merge.