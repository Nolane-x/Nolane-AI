# R2.59 Dual Intervention Portfolio Plan

- [x] Freeze integration goal: preserve main R2.58 positional intervention engine and Track-A exposure/CEGIS engine as independent hypothesis classes.
- [x] Define a common receipt and shared I/O-only challenge/accounting boundary.
- [x] Write focused tests first for canonicalized exposure, real positional fallback, robust consensus, field-renaming invariance, and disabled-engine fail-closed behavior.
- [ ] Confirm the tests are RED because the portfolio module does not exist.
- [ ] Implement `cogcoder/r259_intervention_portfolio.py` using main R2.58 `PositionalSchema`/`discover_causal_intervention` plus `r259_exposure_probe`.
- [ ] Require GREEN focused tests and preserve both parent R2.58 test families.
- [ ] Add a frozen portfolio benchmark with causal ablations: exposure-only, positional-only, robust consensus, rename replay, and strict oracle/synthesis accounting.
- [ ] Add pinned external I/O-only transfer and cross-Python hosted gate.
- [ ] Run Nolane World 0.8.0 audit/gate, preserve non-convergence if W5 remains false, then release only within bounded claim.
