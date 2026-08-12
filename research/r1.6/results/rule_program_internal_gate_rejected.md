# RuleProgramPrior — internal gate REJECTED

Date: 2026-08-12 (Asia/Bangkok)

Preregistered train-only run: fit95–104/family, val105–107/family, seed16170, 40 epochs. Parent is accepted EffectProgress CurrentBest; only 411,650 `rule_program_*` parameters were trainable. Fresh/dev were not opened.

## Frozen parent internal validation

- CE: `0.9179354`
- overall accuracy: `72.131%`
- causal: `67.857%`
- resource: `100.000%`
- rule: `20.000%`

## Training behavior

Training rule accuracy rose from about 28.6% to 48.6%, but internal-validation rule accuracy fell to 10%. Overall validation accuracy also fell to roughly 65.6% and CE increased after early training.

The preregistered internal gate required lower CE, non-lower overall accuracy, and **strictly higher rule accuracy**. No epoch satisfied all conditions; best admissible epoch remained 0.

No `RuleProgramPrior` checkpoint was saved and no dev/fresh slice was opened.

## Interpretation

The module can fit a narrow rule curriculum but does not generalize from only ten fit worlds per family. This experiment is treated as a negative result, not a capability regression of CurrentBest because the accepted parent remains unchanged.

Next experiment should test data breadth before changing architecture: substantially widen procedural compositional-rule coverage while keeping the same program-prior module and a held-out train-only rule validation set.