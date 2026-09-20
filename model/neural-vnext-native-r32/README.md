# Neural vNext Native R32 — factorized terminal action value

Status: **DEV REJECTED; CONFIRMATION AND FRESH UNOPENED**.

R32 changes the learning target rather than adding more representation.

R30 and R31 trained a three-class intervention classifier: neutral / rescue / harm. That formulation collapses two opposite terminal realities into the same neutral label:

- R11 fails and candidate fails;
- R11 solves and candidate solves.

R32 instead learns a binary terminal solve value for each first action:

**Q(s, a) = P(episode solves after taking action a once, then following accepted R11).**

The R11 action itself is labeled once per decision. Every valid alternative action is labeled separately. Rescue and harm are then derived from the candidate and R11 value estimates rather than learned as a single mutually exclusive class.

## Inference score

For each ensemble head:

- rescue = P(candidate solves) × (1 − P(R11 solves))
- harm = P(R11 solves) × (1 − P(candidate solves))
- advantage = P(candidate solves) − P(R11 solves)

An alternative is eligible only when every head has positive advantage, conservative rescue probability clears a locked threshold, and conservative harm probability stays below a locked ceiling.

## Locked architecture

- public goal features: **146**
- accepted R4 latent context: **528**
- per-action value feature width: **727**
- goal parameters: **107,799**
- value parameters: **153,219**
- total successor parameters: **261,018**
- physical learned parameters: **1,138,560**

## New single-use courts

- goal train: train:13824..14335
- temperature fit: train:14336..14463
- terminal value train: train:14464..14847
- four guard blocks: train:14848..15103
- primary dev: dev:1888..1919
- confirmation: dev:1920..1951
- reserved fresh: fresh:280..319 — **UNOPENED**

No development threshold retuning is permitted. Confirmation opens only if the locked primary candidate strictly improves total and implicit-goal solved counts while preserving visible-target family solved counts exactly.


## Locked development result

R32 trained on **5,112** paired counterfactual rows: **274 rescue**, **1,821 harm**, **2,505 both-solve**, and **512 both-fail**. The binary terminal-value objective itself learned strongly (final ensemble-head accuracy about **88.9–89.6%**, Brier about **0.078–0.081**), but the derived independent-probability rescue score did not generalize into a safe selector.

The preregistered guard failed closed. Conservative thresholds selected almost no actions; broader thresholds admitted harmful actions and poor cross-block rescue precision. Therefore R32 executed **0 overrides** on primary development.

On dev:1888..1919:
- accepted R11: **119/128**, implicit-goal **26/32**
- R32: **119/128**, implicit-goal **26/32**
- visible-target family solved counts: exact
- confirmation: **UNOPENED**
- fresh: **UNOPENED**

The next controlled target is a direct **four-way joint terminal outcome** model: both-fail / rescue / harm / both-solve. This preserves the distinction R31 lost without making R32's independence assumption.

Canonical negative evidence: evidence/DEV_REJECTED_001.json.
