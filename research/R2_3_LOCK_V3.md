# R2.3 canonical admission lock v3

This is the canonical pre-DEV lock for the GitHub-published R2.3 candidate. It was committed before opening DEV 7000..7199 or FRESH 8000..8199.

Neural effective parameters: 78,779,253. New R2.3 neural parameters: 0.

Protocol: seen probability 0.35; composition-seen probability 0.25; three demonstrations per skill; induction depth at most 3; candidate budget 100000.

TRAIN 6000..6199: replay baseline 33.625%; R2.3 94.625%; gain +61.0 pp; retention 94.5%; revision 99.0%; composition 90.0%; integrity failures 0.

Admission requires R2.3 >=85%, gain >=20 pp, retention >=90%, revision >=90%, composition >=80%, integrity failures =0.

Canonical Git blob SHA on main:
- cogcoder/continual_skills.py 4e8ef528f91b6e03114499e8700d912014082120
- cogcoder/curriculum_cases.py fe69bf92dfab4927c3b9da6861121384b665c156
- cogcoder/curriculum_eval.py cb17f7486becb3a88050fd8b697d649442f86714
- cogcoder/skill_curriculum.py 735f7d5f418df6c7f70ef97ebe12a0befec18118
- cogcoder/skill_memory.py 87512a61c74c7c4e66785593a79fc13bdbf15dbd
- cogcoder/skill_synthesis.py 941785bfa59aa753d44713f7c0f92f9c98829c3b
- scripts/evaluate_r23_continual.py acaaa0ae74b9f84feef37fcc337dccb016e957da

After DEV is opened, no candidate source or protocol changes are permitted. FRESH may be opened once only after DEV passes and a pre-FRESH marker is committed.
