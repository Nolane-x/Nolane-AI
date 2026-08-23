# Refoundation Epoch 0 Wave 3 — AI-First Canonical Authority Design

## Status
Approved architectural continuation of Waves 1–2c. This design implements the previously agreed AI-first repository model without broadening the current research scope into a user-facing Agent product.

## Problem
Waves 1–2c established canonical namespaces and migrated foundational Organization/task/Central implementation authority, but the repository still has three structural defects:

1. permanent AI identity authority is still authored in `cogcoder/refoundation/organization_spec.py` rather than in one independently evolvable source per AI;
2. shared, regional, and private Neural/External composition is implicit, so a reader must mentally reconstruct an AI from scattered structures;
3. historical R-series/root artifacts coexist with current architecture without a single architectural-law directory that explicitly wins conflicts.

Wave 3 fixes the authority model first. It does not destructively delete historical files.

## Canonical law
`CURRENT/` is the architecture-law surface. If a historical document conflicts with `CURRENT/`, `CURRENT/` wins for present architecture.

Required law documents:
- `CURRENT/README.md`
- `CURRENT/SYSTEM_DEFINITION.md`
- `CURRENT/TERMINOLOGY.md`
- `CURRENT/ORGANIZATION.md`
- `CURRENT/NEURAL_CORE.md`
- `CURRENT/EXTERNAL_CORE.md`
- `CURRENT/RESEARCH_SCOPE.md`
- `CURRENT/STATUS.md`

Terminology rules:
- **Nolane AI**: the whole research system.
- **AI Identity**: one of exactly 67 permanent cognitive members.
- **Neural Core**: trainable/internal neural intelligence.
- **External Core**: umbrella for non-neural capabilities.
- **Tool**: a subtype/capability inside External Core, never a peer to External Core.
- **AI Agent**: reserved for a future product-level autonomous system; it is not the current name for the 67 research identities.

## Source-of-truth hierarchy
Wave 3 introduces three canonical source scopes:

```text
shared/                         # global source
regions/<region-id>/            # regional overlay source
ai/<agent-id>/                  # individual source + generated resolved view
```

### Global source
`shared/neural-core/manifest.json` owns the shared 56M parameter core version and universal cognitive capability floor.

`shared/external-core/manifest.json` owns the general external capability/tool floor.

### Regional source
Each of 15 `regions/<region-id>/manifest.json` files owns:
- region identity and chief;
- regional Neural overlay version;
- regional External Core bindings;
- member IDs.

Epoch 0 regional Neural overlays are logical specialization layers with zero separately-accounted physical parameters. This preserves the accepted first-generation accounting: 56M shared + local delta. A later research release may allocate physical regional parameters only through an explicit parameter-accounting migration.

### Individual source
Each of 67 `ai/<agent-id>/profile.json` files owns:
- identity/name/role/rank/region/chief relation;
- local physical parameter budget;
- private Neural version/specialization metadata;
- private External Core bindings and private tool permissions;
- memory namespace, skill namespace, authority scope;
- direct-work and learning flags.

No shared or regional source is copied into an AI profile.

## Resolution model
Canonical resolution is:

```text
AI_i = identity_i
     + shared neural
     + regional neural (when applicable)
     + private neural_i
     + shared external
     + regional external
     + private external_i
     + memory_i
     + skills_i
```

`nolane.ai` owns loading, validation, and resolution. `cogcoder.refoundation.organization_spec` becomes a compatibility/parity bridge into this canonical authority rather than remaining an implementation owner.

The resolver produces a lossless accepted identity projection so the existing 67-member runtime continues to see the exact same `AgentIdentity` state.

## Generated views
Every AI folder contains generated:
- `RESOLVED.json` — machine-readable exact composition;
- `RESOLVED.md` — human-readable current AI dossier.

Generated files are never manually authoritative. Tests recompute them from canonical source and fail on drift.

A resolved view must show:
- identity;
- shared/regional/private Neural layers;
- shared/regional/private External layers;
- effective external bindings and tool permissions;
- memory/skill namespaces;
- parameter accounting;
- component version tuple.

## Update scopes
Four scopes are explicit:

- Level 0 GLOBAL: shared source change, all 67 resolve differently.
- Level 1 REGIONAL: one region overlay change, only that region changes.
- Level 2 ROLE: represented by coordinated private-profile changes to a named specialization subset; no hidden global mutation.
- Level 3 INDIVIDUAL: one AI profile change, only that AI changes.

The resolver API must make Global, Regional, and Individual impact directly testable. Role-scope automation is deliberately deferred until a role policy is actually needed.

## Compatibility and zero-loss constraints
Wave 3 MUST preserve:
- exactly 67 permanent identities;
- rank counts: 1 Central, 15 Chiefs, 20 senior specialists, 31 specialists;
- every identity below 100M physical parameters;
- accepted parameter accounting: shared 56M plus local 40M/34M/20M/8M by rank;
- exact effective `AgentIdentity` serialization used by the accepted organization runtime;
- existing tool permissions and External Core bindings;
- Wave-1 accepted runtime state fingerprint;
- all Wave 1/2/2b/2c regressions;
- frozen Neural R2.3 metadata contracts.

## Central and private capability honesty
Nolane Central's already-accepted Central-only tool permissions and three Central External Core bindings are represented as private Central source because they are not global capabilities.

For Regional Chiefs and specialists, Wave 3 does not fabricate private External Core capabilities that did not exist in accepted evidence. Their `private_external_core_bindings` and `private_tool_permissions` may therefore be empty while the private source and independent version slots exist. Future research can evolve them AI-by-AI.

## Dependency direction
After Wave 3:

```text
shared/ + regions/ + ai/ source data
             ↓
         nolane.ai
             ↓
cogcoder.refoundation compatibility/parity
             ↓
legacy consumers still awaiting later native extraction
```

Forbidden direction:
`nolane.ai -> cogcoder.refoundation.organization_spec`.

## Historical material
Wave 3 does not delete or bulk-move R-series/history files because that would mix an authority migration with destructive repository history movement. `CURRENT/` makes their non-authoritative status explicit now.

A later archive wave may move historical documentation only after inventory receipts prove no active workflow/runtime depends on each path.

## Verification
Required tests:
1. all eight `CURRENT/` law documents exist and state current precedence;
2. exactly 67 source profiles and 15 region manifests load;
3. rank/cardinality/parameter constraints hold;
4. resolved identity projection equals the pre-Wave-3 accepted identity state for all 67;
5. compatibility `cogcoder.refoundation.organization_spec` exports remain usable but source ownership points to `nolane.ai`;
6. all 67 `RESOLVED.json` and `RESOLVED.md` views exist and match recomputation;
7. a Global override affects all 67 resolved versions;
8. a Regional override affects exactly the members of that region;
9. an Individual private override affects exactly one identity;
10. all prior Refoundation/full organization/campaign/execution/frozen-neural gates remain green on Python 3.11 and 3.13.

## Non-goals
- No user-facing Agent application, UI, desktop/web product, or deployment product layer.
- No AGI/frontier-equivalence claim.
- No invented trained weights.
- No parameter-count increase.
- No destructive deletion of historical source/evidence in Wave 3.
