# Neural vNext Native R4 — accepted latent hidden-goal belief successor

Status: **ACCEPTED** under the preregistered parent-relative FIGG-18 court `fresh:120..159`.

R4 extends accepted R3 without mutating it. It adds a learned latent hidden-goal belief over three 5-way goal coordinates from public action-attributed progress history.

## Accepted authority

- selected candidate: `latent_goal_guarded`
- total parameters: **877,542**
- R4-owned parameters: **169,552**
- checkpoint SHA-256: `167e845e9aa2bfe8a6431478723c777ee8a2f8e77c452192d74cd31d1959a244`
- state-dict SHA-256: `97f114dd202b0e533c01db1adf69efe35b67db02a713d7b40dc619afd3cd2aa9`
- durable checkpoint: `accepted/r4.pt` via Git LFS, **3,539,102 bytes**

The private goal is used only as a train-split auxiliary supervision label. Rollout, development and fresh evaluation consume public information only.

## Development

On `dev:160..191`:

- frozen R3: **114/128**
- R4: **117/128**
- `implicit_goal_regimes`: **22/32 → 25/32**
- conditional, regime-switch and causal-prerequisite solved counts remain exact.

Two development workflows reproduced the same behavioral result but different checkpoint/state bytes. This negative result is retained in `evidence/DEV_REPRO_NEGATIVE_001.json`.

R4 therefore does **not** claim cross-run or cross-host bitwise source-training reproducibility.

## Untouched fresh court

`PRE_FRESH_LOCK.json` froze the exact canonical artifact, source blobs, identities and gate before `fresh:120..159` opened.

Observed:

- frozen R3: **146/160 = 91.25%**
- R4: **148/160 = 92.5%**
- total delta: **+2**

Families:

- `conditional_regimes`: 40 → **40**
- `regime_switch`: 38 → **38**
- `causal_prerequisites`: 39 → **39**
- `implicit_goal_regimes`: 29 → **31 (+2)**

Every solved-count gain occurred in the intended hidden-goal family while every visible-target family remained exact.

Fresh workflow run: `35451949227`; immutable fresh artifact: `10587106977`.

## Durable accepted materialization

The exact canonical development artifact was archived after fresh acceptance without retraining:

- source run: `35451337745`
- source artifact: `10586044507`
- path: `model/neural-vnext-native-r4/accepted/r4.pt`
- storage: Git LFS
- LFS SHA-256: `167e845e9aa2bfe8a6431478723c777ee8a2f8e77c452192d74cd31d1959a244`
- size: **3,539,102 bytes**
- archive commit: `c74347a96d0862f462154c7777ba7e50e9050653`

CI checks out the LFS object, verifies exact hashes and authority metadata, preserves the disclosed non-bitwise reproduction result, runs all R4 contracts, and loads the accepted checkpoint.

## Post-fresh rule

`fresh:120..159` is permanently consumed.

- no post-fresh tuning;
- no mutation under this accepted authority;
- no reuse of the same fresh block for another promotion attempt;
- future successors require a new frozen candidate and untouched fresh identities.
