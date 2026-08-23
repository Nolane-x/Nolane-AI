# Organization

The permanent organization is fixed at 67 AI Identities for the current architecture generation:

- 1 Nolane Central
- 15 Regional Chiefs
- 20 senior specialists
- 31 specialists

Total specialists: 51. Total permanent identities: 67.

The 15 regions are Requirements/Product, Planning/Program, Architecture/System, Core Coding, Frontend/UI, UX/Product Design, Debugging/Failure, Verification/Testing, Security/Adversarial, Data/Storage/Migration, Infrastructure/Release, Performance/Reliability, Research/External, Integration/Change Control, and Memory/Context/Knowledge.

Every region owns one regional overlay source under `regions/<region-id>/`. Every permanent identity owns one independent profile under `ai/<agent-id>/`. Shared source is stored once under `shared/`; it is never copied into 67 profiles.

Update scopes are explicit: GLOBAL affects 67/67; REGIONAL affects exactly one region; ROLE is a coordinated set of explicit private-profile changes; INDIVIDUAL affects exactly one profile.
