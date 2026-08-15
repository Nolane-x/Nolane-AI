# R2.12 Fresh Real-Repository Localization Design

Date: 2026-08-15
Status: DESIGN LOCK CANDIDATE

## Purpose

R2.12 tests whether the compact Nolane coding stack can localize faults in **real, previously authored repositories** instead of synthetic micro-repositories. It does not attempt unrestricted patch generation. The milestone isolates file-level issue localization as an upstream capability before downstream repair, matching the failure decomposition used by recent repository-repair evaluation work.

## External panel

The Phase-A panel is the public 20-task `ibragim-bad/SWE-rebench-V2-sample` dataset referenced by the official `SWE-rebench/SWE-rebench-V2` README. It is pinned to immutable Hugging Face revision `9a7cd16b2431fc9f0abaf4c359e21fd3fae12ae3`, config `default`, split `train`, and loaded with `datasets==5.0.0`. Each row supplies a real repository, an exact `base_commit`, a problem statement, and a gold patch. The panel contains exactly 20 tasks across eight language labels.

The predictor is allowed to receive only:

- `instance_id`
- `repo`
- `base_commit`
- `problem_statement`
- repository source at `base_commit`

The predictor must not receive `patch`, `test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`, generated PR description, interface annotations, or metadata derived from the gold patch.

## Leak firewall

Evaluation is split into two processes and two workflow steps.

1. **Predict phase** downloads a redacted manifest containing only the allowed fields, materializes each repository at the exact base commit, and writes ranked file predictions.
2. **Score phase** starts only after `predictions.json` has been finalized. It separately downloads the immutable full dataset revision, derives gold modified files from `patch`, and scores the already-written predictions.

No function in the prediction module accepts a gold patch or gold file set. Unit tests enforce the schema boundary.

## Localizer

R2.12 adds **zero neural parameters**. The accepted candidate is a deterministic hierarchical localizer designed for a tiny-agent runtime:

1. extract issue anchors from code spans, paths, identifiers, error-like tokens, and ordinary lexical terms;
2. enumerate tracked text/source/config files from the base commit while excluding generated/vendor/build caches and oversized/binary files;
3. compute a path-only lexical baseline;
4. compute content and symbol-definition evidence, with strong boosts for exact quoted identifiers/paths;
5. form a small repository dependency graph from local imports/includes/requires among high-scoring files;
6. propagate a bounded fraction of seed evidence across resolved local edges;
7. rank files deterministically without using language/task IDs or repository-specific rules.

The algorithm is deliberately non-neural for Phase A. If real-repository localization fails, R2.13 may introduce a small learned semantic ranker only after the failure mode is measured.

## Metrics

For each task, gold files are the paths changed by the dataset `patch` field. `test_patch` is not part of the gold localization target.

Report:

- materialized task count / 20
- Hit@1: at least one gold patch file ranked first
- Hit@5: at least one gold patch file in top five
- MRR of first gold file
- mean Recall@5 over all gold patch files
- path-only baseline for the same metrics
- per-language results
- prediction determinism hash
- leakage-contract status

## Frozen Phase-A acceptance

Thresholds are locked before the external panel is scored:

- materialized tasks = 20/20
- candidate Hit@5 >= 0.55
- candidate MRR >= 0.30
- candidate Hit@5 improvement over path baseline >= 10 percentage points
- candidate MRR improvement over path baseline >= 0.05
- mean Recall@5 must not be below the path baseline
- prediction determinism = 100% on a repeated ranking pass
- leak-contract tests = pass
- new neural parameters = 0

Failure of any required threshold rejects R2.12 Phase A. Thresholds are not changed after scoring.

## Claim boundary

A pass establishes only external file-localization evidence on the frozen 20-task real-repository panel. It does not establish arbitrary issue resolution, symbol/line localization, patch synthesis, broad coding competence, AGI, or frontier-model parity.

## Next decision

- **If accepted:** move to R2.13 real-repository symbol localization and then bounded repair on a subset whose required edits fit the R2.10 copy-edit algebra.
- **If rejected:** retain the negative result and diagnose whether the limiting factor is issue semantics, repository-scale retrieval, graph construction, or non-neural ranking; add neural capacity only if the measured failure justifies it.

## Acquisition correction before prediction

The first CI attempt (`31862050419`) pinned the builder repository's small `sample.json`, assuming it was identical to the documented 20-task Hugging Face sample. `prepare-public` rejected that assumption at the 20-row assertion. No prediction job and no gold scoring job ran. The acquisition source was therefore corrected and re-locked before any external model/ranker score existed; all acceptance thresholds and frozen ranking-source hashes remain unchanged.
