# Nolane R2.0f Goal-Directed Future Critic — Train Gate Rejected

Date: 2026-08-13

**Decision: REJECTED.** The frozen R2.0e shallow policy solved 26/80 (32.5%) on the locked 1480..1499 block. Adding the 55,954-parameter goal-directed future critic at depth 2 solved 27/80 (33.75%), a +1.25 pp gain, below the preregistered +10 pp requirement. No family regressed: conditional 45->45, regime 45->45, implicit 30->35, causal 10->10. DEV/FRESH remain closed.

The critic did solve the specific R2.0e failure of family regression, but not enough tasks to admit the candidate. A stronger signal emerged from the frozen R2.0e depth ablation: depth1 solved 26, depth2 solved 31, and their oracle union was 40/80 (50%). Fourteen tasks were depth2-only and nine were depth1-only. Therefore the next candidate targets compute routing rather than more world-model or policy capacity.

Bound critic SHA: `6187bc5cb2e7ce1f251b464b9516990571cb0ee9e2bcbbad7954c57ef0d34816`; candidate total: 78,835,207 parameters. This is not an AGI or >100B-model claim.
