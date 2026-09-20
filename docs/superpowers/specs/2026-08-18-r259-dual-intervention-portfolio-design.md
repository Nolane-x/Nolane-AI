# R2.59 Dual Intervention Portfolio Design

## Goal
Combine the two independently verified R2.58 intervention-discovery mechanisms instead of choosing one: main's positional/canonical anchor search and Track A's learned-vocabulary identity-exposure + bounded CEGIS search.

## Architecture
R2.59 first canonicalizes the external schema by declared input position. It then runs one or both bounded discovery engines behind a shared cached I/O-only oracle ledger. Every candidate is normalized to an external full-target expression and must pass one common full-target challenge layer before selection.

### Engine A — canonicalized exposure discovery
Reuse Track A's R2.58 exposure-schema miner as `r259_exposure_probe`. Run it entirely on `PositionalSchema.canonical_fields` from main R2.58, so lexical external field identities cannot affect search. The oracle adapter maps canonical contexts back to the external ordered schema. This preserves the low-query learned-vocabulary path and its CEGIS repair while inheriting main R2.58's positional invariance boundary.

### Engine B — positional anchor discovery
Reuse main R2.58 `discover_causal_intervention` unchanged. Probe-training contexts come from the supplied downstream training examples and probe-validation contexts from the supplied independent challenge contexts. The existing engine supplies full synthesis accounting and a different intervention hypothesis class.

### Portfolio policy
- `fallback`: try canonicalized exposure first; if it fails common full-target challenge, run positional anchor discovery.
- `robust`: run both engines. If both independently pass and their externalized expressions agree on every challenge context, return `consensus`. If only one passes the common challenge, return a single-engine verified result with explicit reason; never silently treat one engine's failure as agreement.
- A shared oracle cache counts unique external contexts across both engines and the common challenge.
- A hard shared oracle budget fails closed. Per-engine search budgets remain explicit and finite.

## Receipts and accounting
`PortfolioReceipt` records selected method, common challenge exactness, exposure/positional pass states, agreement, shared oracle calls, per-engine synthesis candidates, total synthesis candidates, selected expression, and zero trainable-parameter delta.

## Evidence boundary
R2.59 must causally show: canonicalized exposure retains Track A's external transfer; positional fallback remains usable; robust mode can obtain cross-mechanism agreement on at least one pinned external case; external-field renaming/permutation does not alter the positional role decision. This remains finite pure-function intervention discovery, not open-ended experiment invention, effectful tool invention, arbitrary program synthesis, broad coding autonomy, or AGI.
