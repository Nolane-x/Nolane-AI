# External Core Component-Local Version Discipline & Integration Evolution — Design

Status: approved by repository owner
Base: `main@1cf8108f9df6e0ef62318f514632aa09dfbf42fa`
Scope: External Core component-local version enforcement plus `external.integration` semantic evolution

## 1. Governing authority

This design does not invent a new versioning policy. It makes the existing repository rule executable.

Canonical version authority already states:

- every semantic component owns an independent revision slot;
- Epoch-0 bootstrap is `0.0.0`;
- only components whose implementation authority or accepted local semantics move advance their local revision;
- the canonical component version form is `0.0.N`;
- component revisions are orthogonal to neural versions, state schemas, evaluation releases, historical R/Part labels, Git SHAs, and External Core structural protocol labels;
- there is no aggregate External Core platform version.

`nolane/metadata/component_versions.py`, `nolane/metadata/versioning.py`, `nolane/metadata/_component_specs.py`, and their canonical manifest projection remain the source of truth. `CURRENT/` remains higher repository authority than implementation code.

The problem addressed here is enforcement: existing tests assert the accepted revision snapshot, but an AI agent can still change component semantics without a corresponding local revision bump, bump an unrelated component, or jump revisions and only discover the inconsistency later.

## 2. Version Discipline Gate

Add a read-only deterministic repository checker under `nolane.metadata`. It is tooling, not a semantic component, so it receives no component version and creates no new authority.

The checker compares a base tree and head tree. It must not trust commit messages, PR prose, agent declarations, or manually supplied claims about which component changed.

### 2.1 Component ownership discovery

For Python modules under canonical `nolane` namespaces, ownership is derived from source, not a second handwritten ownership table:

1. Parse modules with `ast`.
2. Discover canonical roots from literal `COMPONENT_ID = "..."` declarations whose IDs exist in `COMPONENT_SPECS`.
3. Build a canonical internal import graph from `nolane.*` imports.
4. A changed canonical module directly declaring a component belongs to that component.
5. A changed helper module belongs to every component root that transitively imports it.
6. Shared helper changes therefore conservatively affect every reachable component owner.
7. Structural modules that are not reachable from any canonical component root do not force a semantic component bump.
8. Test, docs, workflow, generated projection, archive, historical compatibility bridge, and frozen release files are not semantic component source changes.

The ownership derivation is deterministic for the exact base/head trees.

### 2.2 Revision comparison

For each existing component affected by a semantic source change:

- head revision MUST equal base revision + 1.

For each existing component whose revision changed:

- it MUST be affected by a semantic source change;
- it MUST increase by exactly one;
- downgrade and multi-step jump fail closed.

For a newly introduced component:

- it MUST have a canonical `COMPONENT_SPECS` entry;
- its revision slot MUST begin at `0` (`0.0.0`);
- a corresponding canonical component source root MUST exist.

Removing a canonical component or revision slot is blocking unless handled by a separately designed retirement protocol; this change adds no automatic retirement path.

### 2.3 Categorical findings

The checker emits stable categorical codes, including:

- `SEMANTIC_CHANGE_WITHOUT_REVISION`
- `REVISION_WITHOUT_SEMANTIC_CHANGE`
- `REVISION_JUMP`
- `REVISION_DOWNGRADE`
- `NEW_COMPONENT_NOT_BOOTSTRAP`
- `MISSING_COMPONENT_REVISION_SLOT`
- `REMOVED_COMPONENT`
- `UNKNOWN_COMPONENT_REVISION`
- `OWNERSHIP_DISCOVERY_ERROR`

No scalar confidence is used.

### 2.4 CLI / CI

Provide a CLI capable of:

- `--base <git-ref>` and `--head <git-ref>`;
- `--check` nonzero exit on blocking findings;
- `--json` deterministic machine-readable report.

On pull requests the External Core workflow runs the gate against the PR base SHA and checked-out head. For local use, callers can pass refs explicitly.

Historical accepted revision debt is not rewritten. The gate evaluates only the semantic delta from base to head.

The checker has no repair mode and never edits version files automatically.

## 3. `external.integration` v0.0.2

Evolution/currentness qualification belongs to the existing `external.integration` component because `COMPONENT_SPECS` defines that component as the owner of compatibility and semantic integration authority.

Only this semantic component advances in this work:

- `external.integration`: `0.0.1` -> `0.0.2`
- `external.integration.compatibility` semantic surface: `0.0.1` -> `0.0.2`

No other component revision changes merely because it participates in a transition.

## 4. Evolution primitives

Implement focused immutable/content-addressed structures in `nolane/external_core/integration_evolution.py`. They are part of `external.integration`, not a new platform/family.

### 4.1 `ComponentEvolutionDelta`

Binds exact old/new `ExternalComponentManifest` states and classifies deterministic field-level changes:

- component version
- protocol versions
- consumed contracts
- produced contracts
- authority capabilities
- forbidden authorities
- mutable resources
- evidence inputs
- evidence outputs
- restore protocol
- compatibility range

Old/new component identity must match. Direct constructor forgery must be rejected by integrity revalidation at semantic consumers.

### 4.2 `EvolutionCompatibilityDisposition`

Categorical only:

- `COMPATIBLE`
- `REVALIDATION_REQUIRED`
- `INCOMPATIBLE`
- `UNKNOWN`

Compatibility qualification rules are fail closed. Examples:

- no semantic manifest change: `COMPATIBLE`;
- version-only movement within unchanged declared contracts/authority/resources: `REVALIDATION_REQUIRED` because currentness evidence is version-bound;
- removed produced/consumed contracts, newly forbidden authority conflicting with previous capability, mutable-resource ownership change, or compatibility-range exclusion: `INCOMPATIBLE`;
- incomplete required current evidence: `UNKNOWN`.

A compatibility qualification is structural/integration evidence only. It is not Truth, Verification, Assurance, authorization, promotion, execution success, release readiness, or deployment approval.

### 4.3 `IntegrationImpactClosure`

Computes deterministic transitive impact from changed component IDs across the supplied exact current structural state:

- authority graph edges;
- producer/consumer contract edges;
- typed handoffs whose producer or consumer is impacted;
- work-trace nodes belonging to impacted components or binding impacted handoffs.

The closure retains explicit reason edges so callers can audit why a component/handoff/trace is impacted. It does not invoke or mutate those objects.

### 4.4 `IntegrationRevalidationReceipt`

Binds:

- exact evolution delta IDs/digests;
- exact impact-closure digest;
- exact old/new live snapshot IDs/digests;
- externally supplied verifier component identity;
- externally supplied evidence refs/digests;
- categorical result.

The receipt MUST NOT self-certify. The verifier component must be distinct from every changed component. A nonempty evidence set is required for a positive revalidation result. The receipt cannot mint Assurance or authorization.

### 4.5 `IntegrationTransitionAssessment`

Combines exact deltas, impact closure, old/new live snapshots, and revalidation receipts to produce one categorical transition state:

- `CURRENT` only when all changed deltas are structurally compatible/current under exact supplied evidence and every required impacted lineage is covered;
- `REVALIDATION_REQUIRED` when structurally admissible but required proof is absent/incomplete;
- `INCOMPATIBLE` when a blocking compatibility condition exists;
- `UNKNOWN` when current evidence/state needed for assessment is unavailable;
- `QUARANTINED` for integrity/tamper/noncanonical input.

This assessment never changes another component's state.

## 5. Strict boundary hardening

New v0.0.2 integration/evolution APIs use strict admission: identity, version, digest, protocol and evidence-ref fields require actual nonempty strings. Boolean-as-integer, stringification of arbitrary objects, noncanonical mappings, duplicate semantic identities and direct-constructor digest forgery are rejected.

Historical v1/A2/A3 objects are not globally rewritten in this change. Existing historical restore compatibility remains intact.

## 6. Public API boundary

Public package exports may expose immutable/read-only integration-evolution structures and assessment functions. They must not expose:

- invoke
- execute
- authorize
- promote
- assure
- repair
- deploy
- auto-migrate
- auto-bump-version

The canonical version discipline checker also exposes no write path.

## 7. CI acceptance

The External Core workflow is renamed generically to `External Core` rather than continuing phase labels as current product version names. Historical A2/A3 documentation remains provenance.

Acceptance requires Python 3.11 and 3.13 to pass:

- version discipline contracts;
- all existing External Core A2/A3/G contracts;
- integration evolution contracts;
- canonical External Core audit with zero findings;
- prior G/Assurance regressions;
- canonical component-version tests;
- relevant Refoundation regression workflow on the exact PR merge tree.

No historical frozen release lock is rewritten to manufacture green CI.

## 8. Adversarial acceptance matrix

Tests must prove rejection of at least:

1. component source changed with unchanged revision;
2. unrelated revision bump;
3. revision jump by more than one;
4. revision downgrade;
5. new component starting above `0.0.0`;
6. shared helper change without all affected component bumps;
7. forged `ComponentEvolutionDelta` digest;
8. same component ID rebound to another old/new manifest identity;
9. changed component self-issuing a positive revalidation receipt;
10. positive revalidation with empty evidence;
11. impact closure omitting a reachable authority/contract edge;
12. impact closure omitting a handoff/trace descendant;
13. old/new live snapshot substitution;
14. duplicate evidence identity with divergent digest;
15. non-string identity smuggling;
16. boolean/integer type smuggling;
17. direct dataclass construction followed by semantic consumer use.

## 9. Non-goals

This change does not introduce a global External Core version, A4/A5 phase version, family H, central governor, runtime orchestrator, automatic migration engine, automatic version repair, or authority escalation.

It also does not change the canonical `0.0.N` version policy. A future move to another version grammar would require its own authority change to `nolane.metadata.versioning` and is outside this work.