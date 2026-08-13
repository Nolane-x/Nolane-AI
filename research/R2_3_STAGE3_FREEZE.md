# R2.3 stage-3 freeze

The validation stage passed and the candidate is frozen before the final held-out evaluation.

Reserved final held-out indices: 8000..8199. They were not evaluated when this marker was committed.

Protocol: seen probability 0.35; composition-seen probability 0.25; three demonstrations per skill; maximum induction depth 3; candidate budget 100000.

Thresholds: candidate >=85%, gain >=20 pp, retention >=90%, revision >=90%, composition >=80%, integrity failures =0.

Git blob identities:
- cogcoder/continual_skills.py 4e8ef528f91b6e03114499e8700d912014082120
- cogcoder/curriculum_cases.py fe69bf92dfab4927c3b9da6861121384b665c156
- cogcoder/curriculum_eval.py cb17f7486becb3a88050fd8b697d649442f86714
- cogcoder/skill_curriculum.py 735f7d5f418df6c7f70ef97ebe12a0befec18118
- cogcoder/skill_memory.py 87512a61c74c7c4e66785593a79fc13bdbf15dbd
- cogcoder/skill_synthesis.py 941785bfa59aa753d44713f7c0f92f9c98829c3b
- scripts/evaluate_r23_continual.py acaaa0ae74b9f84feef37fcc337dccb016e957da

Validation run 31705841354: candidate 94.25%, replay 33.25%, gain +61.0 pp, retention 95.0%, revision 95.5%, composition 91.0%, integrity failures 0. No candidate source or protocol changes followed that result.
