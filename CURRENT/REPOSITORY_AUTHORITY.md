# Repository Authority and Historical Quarantine

## Present authority

The current Nolane AI repository is governed by this precedence order:

1. `CURRENT/` — present architecture law and scope.
2. `shared/`, `regions/`, `ai/` — AI-first canonical configuration/source authority.
3. `nolane/` canonical implementation namespaces and their declared component manifests/ledgers.
4. Accepted evidence/checkpoint authorities for the scientific claims they explicitly govern.
5. Compatibility bridges and historical implementation paths.
6. R-series/Part-era delivery, release, recovery, readiness, and evidence documentation as historical provenance.

A lower layer can provide evidence about the past, but it cannot silently redefine a higher layer's present architecture.

## Historical quarantine

Historical material is preserved under a fail-closed policy. Every ambiguous historical root artifact is represented in `archive/INDEX.json` with its original path, SHA-256 digest, classification, proposed stable archive target, movement state, and deletion prohibition.

Two movement states exist in Wave 4:

- `quarantined_in_place`: the file remains at its historical path because dependencies/reproduction references have not yet been cleared;
- `moved`: the file has been relocated to its stable archive target after a reference audit and migration receipt.

Neither state authorizes deletion. Wave 4 records `delete_allowed=false` for all history.

## Misleading legacy CURRENT names

Root-level `CURRENT_STATUS.md` and `CURRENT_ONE_WEIGHT_*` names predate the A1 Refoundation authority model. Their names are preserved as historical/checkpoint provenance while quarantined, but they do not outrank `CURRENT/STATUS.md`, `CURRENT/NEURAL_CORE.md`, or accepted checkpoint evidence contracts.

## Repository audit

`nolane.repository.audit` is the canonical Wave-4 audit/materialization mechanism:

```bash
python -m nolane.repository.audit --write
python -m nolane.repository.audit --check
```

It produces:

- `archive/INDEX.json` — exhaustive ambiguous-root historical census;
- `CURRENT/NATIVE_DEBT.json` — exhaustive non-native implementation census;
- `CURRENT/NATIVE_DEBT.md` — human-readable debt projection.

Generated audit projections are not hand-edit authority.

## Native implementation debt

A component in `CURRENT/NATIVE_DEBT.json` is not necessarily defective. It means the implementation ledger still classifies it as compatibility facade, legacy internal, historical-only, or frozen asset rather than fully `canonical_native`.

Future extraction waves remove entries only by changing the canonical implementation ledger after behavior/parity/hosted verification. This makes remaining work explicit instead of burying it in old Part/R documents.

## Workflow authority

Refoundation PRs use `.github/workflows/refoundation-epoch0-wave1.yml` as their repository-refoundation regression gate. Historical workflows retain their normal push/schedule/manual/ordinary-PR behavior, but must not consume runners for `refoundation/*` PR heads.

This is routing isolation only; historical evidence gates are not deleted or weakened for their intended contexts.
