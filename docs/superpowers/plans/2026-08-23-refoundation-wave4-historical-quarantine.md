# Wave 4 Historical Authority Quarantine — Implementation Plan

> **For execution:** follow TDD and verification-before-completion. Keep all historical evidence fail-closed; do not delete source/evidence in Wave 4A.

## Goal

Make repository authority and remaining migration debt mechanically auditable, isolate every historical PR workflow from Refoundation PRs, and physically archive only history proven safe to relocate.

## Task 1 — RED repository-quarantine contracts

Create `tests/test_refoundation_wave4_repository_quarantine.py` first. It must fail until all of the following exist:

- `CURRENT/REPOSITORY_AUTHORITY.md`;
- `archive/README.md` and `archive/INDEX.json`;
- `CURRENT/NATIVE_DEBT.json` and `CURRENT/NATIVE_DEBT.md`;
- `nolane.repository.audit` with deterministic generation/check behavior;
- complete historical-root coverage;
- complete non-native implementation-ledger coverage;
- complete Refoundation-head isolation for every historical PR workflow;
- updated `CURRENT/STATUS.md` declaring Wave 3 accepted and Wave 4 active.

Open a draft PR while RED and capture the offender list from hosted CI.

## Task 2 — Canonical repository audit

Create:

- `nolane/repository/__init__.py`
- `nolane/repository/audit.py`

The audit module must:

1. enumerate historical root candidates from the repository filesystem;
2. hash source bytes with SHA-256;
3. classify each candidate using explicit family rules;
4. produce archive target suggestions without moving files;
5. mark every entry `delete_allowed: false`;
6. generate native debt from `build_component_implementation_ledger()`;
7. render human-readable native-debt Markdown;
8. expose `--write` and `--check`;
9. be deterministic and idempotent;
10. fail if root candidates or implementation debt are omitted.

Repository-governance version starts at `0.0.0`.

## Task 3 — Canonical authority documents

Create `CURRENT/REPOSITORY_AUTHORITY.md` and `archive/README.md`. Update `CURRENT/STATUS.md` so it describes Wave 3 as merged/accepted and Wave 4 as the active repository-quarantine wave.

`CURRENT/REPOSITORY_AUTHORITY.md` must define the present-authority hierarchy and explain `quarantined_in_place` vs `moved` history.

## Task 4 — Materialize audit ledgers

Generate and commit:

- `archive/INDEX.json`
- `CURRENT/NATIVE_DEBT.json`
- `CURRENT/NATIVE_DEBT.md`

Add a permanent read-only step to `.github/workflows/refoundation-epoch0-wave1.yml`:

```bash
python -m nolane.repository.audit --check
```

The write path may be bootstrapped temporarily in Actions if necessary, but any write-enabled bootstrap workflow must be removed before acceptance.

## Task 5 — Exhaustive historical workflow isolation

Use the RED failure list to identify every non-Refoundation workflow that subscribes to `pull_request` and lacks Refoundation-head isolation.

For each offending workflow, preserve all existing test/evidence commands and triggers, but add job-level routing equivalent to:

```yaml
# REFOUNDATION_PR_ISOLATION
if: ${{ !(github.event_name == 'pull_request' && startsWith(github.head_ref, 'refoundation/')) }}
```

If a job already has an `if`, combine conditions without changing its original meaning for non-Refoundation events.

Do not disable push, schedule, workflow_dispatch, or normal PR execution.

## Task 6 — Reference audit and safe physical archive

After 4A is green, scan every root historical candidate for path/name references in active source, tests, workflows, scripts, and documentation that is still an executable reproduction contract.

Classify candidates:

- `safe_to_move`
- `quarantined_in_place`

Move only `safe_to_move` artifacts into stable `archive/root-history/...` targets. Preserve Git history via ordinary moves/copy-delete semantics and keep source SHA/digest in `archive/INDEX.json`.

Do not move checkpoint/current-weight pointers or anything with unresolved active references.

## Task 7 — Hosted verification

On exact Wave-4 head, require both Python 3.11 and 3.13 to pass:

- compile;
- AI dossier freshness;
- repository audit freshness;
- all `test_refoundation_*.py`;
- zero-loss evidence generation/upload;
- all organization/campaign/execution regressions;
- frozen Neural R2.3 metadata.

Also confirm historical PR workflows are `skipped` on the Wave-4 PR and only the dedicated Refoundation gate consumes runners for Refoundation-specific paths.

## Task 8 — Completion evidence

Update the Wave-4 PR body with:

- exact accepted head SHA;
- hosted run ID;
- Python 3.11/3.13 success;
- historical-root census count;
- workflow-isolation count;
- native-debt count by implementation status;
- moved vs quarantined-in-place history counts;
- explicit statement that no evidence was deleted.

Only then mark Wave 4 complete.