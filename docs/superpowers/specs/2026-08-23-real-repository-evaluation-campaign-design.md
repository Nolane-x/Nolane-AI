# Real-Repository Evaluation Campaign Core — Design

## Status
Approved direction following completion of Parts I–XV. This is a post-roadmap capability-growth subsystem, not Part XVI of the original architecture roadmap.

## Goal
Create a deterministic, evidence-producing campaign harness for fresh real-repository tasks. The campaign layer executes or records benchmark runs; Part XV remains the sole authority for evaluation comparisons, claim boundaries, scaling decisions, and reproducible release evidence.

## Non-goals
- No AGI/frontier claim unlocking.
- No direct neural promotion or parameter-ceiling mutation.
- No replacement of Part XV benchmark/evidence ledgers.
- No hidden network execution inside the organization runtime.
- No dependence on one public benchmark format.

## Architecture choice
Use a campaign overlay with six focused components:
1. `campaign_tasks.py` — immutable repository/task manifests and heldout split metadata.
2. `campaign_repository.py` — repository snapshot identity, source/revision provenance, contamination controls.
3. `campaign_runner.py` — run specifications and immutable execution receipts for SINGLE_AGENT, FLAT_SWARM, ORGANIZATION and Part-XV ablation modes.
4. `campaign_ingest.py` — validates run receipts/artifacts and converts them into Part-XV benchmark regimes + evaluation observations.
5. `campaign_reproduction.py` — independent reproduction requests/receipts and release-ready evidence bundles.
6. `campaign.py` — façade, campaign lifecycle, snapshot/restore and completeness checks.

The campaign layer produces evidence; `EvaluationScalingControlPlane` judges it.

## Campaign lifecycle
`DRAFT -> FROZEN -> RUNNING -> EVIDENCE_READY -> REPRODUCING -> COMPLETE`

Fail-closed terminal paths: `INVALID`, `QUARANTINED`, `ABORTED`.

A campaign may only transition to FROZEN when all task manifests, repository snapshots, budget envelopes, runner protocol version, evaluation modes and heldout/train partition are content-addressed. After FROZEN, those inputs are immutable.

## Repository snapshot model
Every repository task binds:
- canonical repository locator label;
- exact source revision SHA/digest;
- task patch/base revision digest;
- language/toolchain metadata digest;
- test command digest;
- contamination policy digest;
- optional license/source metadata;
- frozen timestamp/freshness epoch as logical metadata.

The campaign never treats branch names such as `main` as a frozen revision.

## Task manifests
Each task includes:
- task id and domain;
- repository snapshot id;
- natural-language objective digest/text;
- acceptance/test command digest;
- hidden/heldout flag;
- difficulty tier;
- allowed tool/core envelope;
- compute/tool/external-core/wall-clock/active-agent budgets;
- expected evaluator protocol;
- contamination tags/prohibited evidence refs.

Task ids cannot be rebound to different content.

## Heldout integrity
A campaign split ledger records train/dev/heldout membership before execution. Once frozen:
- a task cannot move partitions;
- heldout task content cannot appear in training/distillation input refs;
- any detected contamination quarantines affected observations;
- Part XV receives `fresh=False` or a blocked ingestion rather than laundering contaminated evidence.

## Runner receipts
Runner execution itself is outside claim authority. A run receipt binds:
- campaign/task/repository snapshot;
- exact producer revision;
- Part-XV evaluation mode;
- runner protocol/environment/toolchain digests;
- input artifact refs;
- output artifact refs;
- task result/pass state;
- false-accept/regression counters;
- compute/tool/core/wall-clock/energy/active-agent metrics;
- termination reason;
- immutable digest.

No caller may supply a free-form score disconnected from task outcomes. Campaign aggregation computes pass_count/task_count and score deterministically.

## Baseline fairness
For a declared regime, the same frozen task set, repository revisions, tool envelope and hard budgets are used for:
- SINGLE_AGENT;
- FLAT_SWARM;
- ORGANIZATION;
- selected ablations.

A baseline run with a different task set/revision/budget is preserved but marked incomparable by Part XV.

## Ingestion into Part XV
`CampaignIngestor` creates or reuses a `BenchmarkRegime` and records `EvaluationObservation` rows in `EvaluationEvidenceLedger`.

Rules:
- only EVIDENCE_READY campaigns ingest;
- all required tasks for the selected mode must have terminal run receipts;
- task count and score are derived from receipts;
- resource metrics are sums/maxima according to declared aggregation policy;
- evidence artifacts must already exist in `ArtifactStore`;
- external-independent provenance requires an evaluator id outside the 67 permanent identities;
- no ingestion mutates previous Part-XV observations.

## Reproduction
An external reproduction package binds:
- frozen campaign digest;
- source revision(s);
- task set digest;
- runner protocol digest;
- environment digest;
- exact command manifest digest;
- generated Part-XV observation ids;
- artifact bundle digest.

Independent reproduction is a separate receipt, never inferred from a successful internal rerun.

## Runtime integration
The current accepted Part-XV runtime is preserved as `runtime_part15.py`. New `runtime.py` adds only `evaluation_campaign` construction and snapshot state. A pre-campaign snapshot restores an empty campaign layer.

## Security and adversarial gates
RED contracts cover:
- branch-name-as-revision rejection;
- task id rebinding;
- post-freeze manifest mutation;
- heldout partition mutation;
- contamination laundering;
- result score injection;
- missing evidence artifacts;
- mode/budget mismatch;
- duplicate run identity with changed outputs;
- external evaluator spoofing using permanent agent ids;
- reproduction receipt tampering;
- old-snapshot compatibility.

## Acceptance
The campaign core is accepted only if:
1. frozen campaigns are fully content-addressed and immutable;
2. heldout contamination is detected/fail-closed;
3. runner receipts cannot inject arbitrary aggregate scores;
4. matched modes share frozen regime inputs;
5. Part-XV ingestion derives observations deterministically;
6. external-independent provenance cannot be spoofed by permanent identities;
7. reproduction evidence is independently bound;
8. snapshot/restore is exact and older snapshots yield an empty campaign layer;
9. Python 3.11 and 3.13 campaign tests pass together with Parts I–XV regressions;
10. no code path unlocks AGI/frontier claims or mutates neural/parameter production state.
