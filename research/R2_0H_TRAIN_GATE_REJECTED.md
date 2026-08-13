# Nolane R2.0h Episode Compute Router — Train Gate Rejected

Date: 2026-08-13

**REJECTED.** On locked train indices 1920..1939, fixed-depth-1 and the episode-level router both solved 26/80 (32.5%), so aggregate gain was 0 pp instead of the required +10 pp. The router improved `regime_switch` from 30% to 40% but regressed `conditional_regimes` from 50% to 40%; implicit remained 50%, and causal prerequisites remained 0% for depth1, depth2, and the router. DEV/FRESH remain closed.

R2.0h used only 32,338 parameters and selected depth once per episode, eliminating the per-step distribution-shift failure of R2.0g. Its failure is therefore informative: the remaining causal block cannot be solved by routing between the two frozen policies because neither policy solves those worlds. The next candidate moves to public active causal discovery/subgoal control rather than another compute selector.
