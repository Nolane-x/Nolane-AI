# R2.3 admission lock v2

Created before opening DEV or FRESH after a TRAIN-only publication refactor.

Neural effective parameters: 78,779,253. New R2.3 neural parameters: 0.

Protocol: seen probability 0.35; composition-seen probability 0.25; three demonstrations per skill; induction depth at most 3; candidate budget 100000.

TRAIN 6000..6199: replay baseline 33.625%; R2.3 94.625%; gain +61.0 pp; retention 94.5%; revision 99.0%; composition 90.0%; integrity failures 0.

Reserved DEV: 7000..7199, unopened at this commit.
Reserved FRESH: 8000..8199, unopened at this commit.

Admission requires R2.3 >=85%, gain >=20 pp, retention >=90%, revision >=90%, composition >=80%, integrity failures =0.

Locked SHA-256:
- cogcoder/continual_skills.py 88c76452d3786d7725bd6532e9a9b17e6657f93fe5269aa5abc5a746893c2ec2
- cogcoder/curriculum_cases.py 800b198eb7e4bd79a1a755e7b9e76198771b9b224eca70d7c4b721577f208a48
- cogcoder/curriculum_eval.py 83b6bcd86095508df4a0a4ec70370e8077602de7763f51f0fca0dc26771173ff
- cogcoder/skill_curriculum.py 9b6b3d67ad5608b8e077ed4fd3a05b057c5b374560a71f2b04fb040e2ba12112
- cogcoder/skill_memory.py 183ab171bf532a6239b2761efcd8bdc7a10cd5b12f9d450b511f5955b5e3ac4d
- cogcoder/skill_synthesis.py 1b6e1651a72a0966831bb123282569800d02548f4a0eacd02163e18174391fd8
- scripts/evaluate_r23_continual.py dc81ba5711f41ae3b89f28a3b84c6367d5295e82b4b3f85f413cb7500eb4d2b2

No source or protocol changes are permitted after DEV is opened for this candidate.
