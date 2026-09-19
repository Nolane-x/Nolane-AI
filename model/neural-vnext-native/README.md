# Neural vNext Native — self-contained recurrent rebuild

Status: **development candidate; fresh unopened**

This line exists because the accepted historical R2.3 evidence retained hashes and metrics but not the binary one-weight checkpoint or the 11,539-state expert+DAgger cache. Neural vNext Native restores a reproducible neural path that can be trained, frozen, and evaluated entirely from repository source.

## Core boundary

Inference receives only information present in the public FIGG-18 observation plus episode-local memory derived from public transitions:

- normalized public state;
- visible target when the benchmark exposes one;
- progress signal, remaining budget and step;
- public resource/gate values;
- public regime identity;
- previous public feedback;
- per-action public transition memory.

Private goal/rule fields are never encoded into model inputs.

The neural policy is action-order equivariant: a shared action encoder and shared scorer operate over action-memory tokens, while a multi-head attention summary and GRUCell maintain recurrent episode state. This is important because FIGG-18 shuffles action order per world.

## Training

The preregistered development program is in `PREDEV_LOCK.json`. Model initialization is seed-bound **before construction**. Development performs a bounded, preregistered curriculum tournament (`expert4`, `guarded_dagger`, `broad_dagger`) and selects only by dev evidence: solved episodes, then worst-family solved count, then fewer action steps, then lexical name.

Training uses only FIGG-18 `train` worlds. The teacher first requires public exploration of unseen non-submit action slots in the current public regime. After those slots have evidence, the FIGG-18 oracle supplies a training-only action target. DAgger candidates mix teacher and learned-policy behavior so supervision covers learner-induced states.

The `dev` split is used for iteration. The `fresh` split is explicitly forbidden to training and development code.

Run:

```bash
PYTHONPATH=model/neural-vnext-native:model/r1.8 \
python model/neural-vnext-native/scripts/train_native_dev.py \
  --checkpoint /tmp/native-vnext.pt \
  --manifest /tmp/native-vnext.manifest.json \
  --dev-result /tmp/native-vnext.dev.json
```

## Fresh court

Fresh indices `0..39` across all four FIGG-18 families are preregistered as a 160-episode untouched court.

They must not be instantiated until:

1. development is complete;
2. an exact checkpoint tensor digest and checkpoint SHA-256 are frozen in a separate pre-fresh lock;
3. training source/configuration are frozen;
4. the fresh evaluator verifies the exact frozen checkpoint before creating any fresh task.

Any tuning after fresh consumption invalidates promotion for that candidate.

## Claim boundary

This native line is not automatically a successor to R2.3. Historical R2.3 and a native candidate evaluated on a different fresh block are not treated as directly interchangeable measurements. Promotion language requires its own frozen fresh evidence.

## Development provenance

The first development-only run is retained at `evidence/DEV_HISTORY_001.json`. It reached 50/128 dev episodes (39.0625%) but is explicitly non-promotable because the model initialization seed had not yet been bound before construction. Fresh remained unopened. The deterministic curriculum tournament supersedes that run for candidate selection.


## Hidden-goal v2 development line

After dev-only trials exposed hidden-goal inference as the remaining bottleneck, the current development line keeps the strong parity-conditioned public transition memory and changes only the hidden-target path:

- visible-target episodes hard-bypass the goal transform and retain the legacy parity policy path;
- hidden-target episodes keep the full 3x5 categorical neural goal belief instead of compressing it to scalar coordinate expectations;
- exact hidden-goal labels are train-only and begin only after every non-submit action has public transition evidence in the current context;
- `implicit_goal_regimes` uses unique train indices `0..511`; the other three families remain at `0..127`;
- dev remains `0..31` and fresh remains unopened.

The prior dev trials are retained in `evidence/DEV_HISTORY_001.json` through `DEV_HISTORY_005.json`. They are tuning evidence only and have no promotion authority.
