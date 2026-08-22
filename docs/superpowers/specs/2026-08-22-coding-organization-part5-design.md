# Coding Organization Part V — Design Specification

## Status

Implements Issue #133 on accepted Parts I–IV. The seven coding-region identities already exist in the first-generation 67-agent blueprint: Coding Chief, Core Algorithm Coder, Backend Coder, Systems Coder, Refactoring Coder, API Coder, and Build & Dependency Coder. Part V does not create seven prompt personas; it gives these durable identities a governed coding work model, distinct routing profiles, code-ownership claims, patch provenance, evidence completion rules and restart-safe state.

No claim is made that the current <100M neural cores are unrestricted AGI or frontier coding models. This Part establishes the organizational/runtime substrate on which their real coding capability can later be trained and evaluated.

## 1. Goals

1. Preserve all seven coders as general learning agents with personal memory, skills, self-models and neural version lineages inherited from Part I.
2. Make specialization operational rather than descriptive by routing work using declared domain capabilities and external-core/tool bindings.
3. Prevent destructive concurrent edits through explicit file/symbol work claims.
4. Make a patch a structured evidence-bearing object, not merely a diff string.
5. Require compiler/test/verification evidence before coding work is considered completion-ready.
6. Propagate plan/architecture gaps through the existing owners instead of letting coders silently rewrite authoritative plans/architecture.
7. Keep Coding Chief a direct worker.

## 2. Coding profiles and routing

`CodingProfileRegistry` derives a profile for each permanent `core-coding` identity. A profile contains:
- agent id;
- specialization domains;
- preferred external cores;
- preferred file/language/task signals;
- current self-model competence observations where available;
- current workload/task binding;
- accepted neural/specialization version.

The router is deterministic and evidence-neutral: it scores declared task traits against profile domains and current availability. It does not manufacture capability claims. Ties are resolved by stable agent id unless Coding Chief/Central explicitly overrides through an audited assignment event.

Baseline domains:
- Coding Chief: cross-system implementation, architecture-aware coding, integration coordination;
- Core Algorithm: algorithms, data structures, numerical/formal core logic;
- Backend: services, APIs, persistence-facing application logic;
- Systems: low-level/runtime/concurrency/performance-sensitive implementation;
- Refactoring: cross-file restructuring and behavior-preserving migration;
- API Coder: public/internal interfaces, schemas and compatibility implementation;
- Build & Dependency: build systems, packaging, dependency/toolchain changes.

Every specialist retains the universal cognitive capability floor; specialization is preference/expertise, not a hard prohibition on local planning/research/debugging.

## 3. Coding work request

A `CodingWorkRequest` contains:
- work id;
- task id;
- plan node id;
- requirement refs;
- architecture revision expected;
- requested domains;
- repository/file/symbol scope hints;
- acceptance criteria/evidence expectations;
- priority;
- requester;
- evidence refs.

Routing creates an immutable `CodingAssignmentReceipt` explaining selected agent, candidate scores, architecture/plan versions and override (if any).

## 4. Code work claims

`CodeClaimLedger` is separate from TaskGraph leases. TaskGraph owns *who owns the task*; CodeClaimLedger owns *who may mutate a specific repository scope while executing it*.

Claim scopes:
- file paths;
- symbol ids;
- optional directory/subtree prefixes;
- claim mode `EXCLUSIVE_WRITE` or `SHARED_READ`.

First-generation rule: overlapping `EXCLUSIVE_WRITE` claims from different active agents fail closed. Claims are bounded by task id and status (`ACTIVE`, `RELEASED`, `SUPERSEDED`, `ABORTED`).

Overlap is canonicalized using normalized POSIX-style paths and exact symbol ids. No claim implies ownership of the architecture or plan artifact; it only prevents concurrent source mutation collisions.

## 5. Patch candidates

A `CodingPatchCandidate` records:
- patch id;
- producer agent;
- task/work id;
- base architecture version;
- base plan version;
- claimed scopes;
- touched file/symbol refs;
- artifact id for diff/patch bytes;
- compile evidence refs;
- test evidence refs;
- static/type evidence refs;
- known risks;
- plan-gap event refs;
- architecture-concern event refs;
- status (`DRAFT`, `EVIDENCE_READY`, `VERIFIED`, `REJECTED`, `SUPERSEDED`).

The coding region cannot mark a patch `VERIFIED` itself. It can mark `EVIDENCE_READY`; Part-I VerificationAuthority / later Part VIII independent verification authorizes `VERIFIED` state with an external verifier evidence record.

## 6. Completion gates

A patch is completion-ready only when:
- its task lease belongs to the producer (or direct-working Coding Chief);
- source claims cover all declared touched files/symbols;
- architecture version is current or a declared accepted architecture/integration compatibility path exists;
- plan version is current or a plan-gap amendment updates the work capsule;
- compile evidence is present when compilation applies;
- test evidence is present;
- verifier evidence passes with zero false accepts/regressions for the declared gate;
- no active Integration/Security/Verification block applies.

The control plane emits a readiness receipt; it does not merge code directly.

## 7. Plan and architecture feedback

Coders use existing Part III/IV flows:
- missing work/dependency → `PLAN_GAP_DETECTED` to Planning Chief;
- structural/boundary issue → `ARCHITECTURE_CONCERN` to Architecture Chief.

Coding Chief can advise or escalate but cannot silently mutate those owners' artifacts.

## 8. Tool and external-core policy

Coding identities must expose coding-region bindings (`lsp`, `ast`, `symbol-graph`, `compiler`, `patch-engine`, `worktree-manager`, `test-selection`) through their identity/external-core registry. Part V records invocation receipts (tool/core id, task, input artifact refs, output artifact refs, success/failure, evidence refs) rather than pretending tool availability proves skill.

Central may own broad generic tools but does not silently gain specialist-private cores contrary to Part II lease policy.

## 9. Learning and evolution

Part V reuses Part-I personal skill and neural evolution mechanisms. Coding outcomes can create personal skill candidates tagged to domains such as `backend-api`, `refactor`, `systems-concurrency`. Promotion personal→regional→global remains evidence-gated. A failed patch may contribute episodic/negative evidence but cannot become an active skill rule without verification.

No Part-V code mutates production neural weights live.

## 10. Direct Coding Chief work

Acceptance must include a Coding Chief task leased directly to `coding.chief`, with an artifact/patch and evidence receipt completed without delegating. This protects the architectural principle that Chiefs are strong workers, not dispatch-only managers.

## 11. Snapshot/context

Runtime gains `runtime.coding: CodingControlPlane` and persists:
- profiles;
- work requests/assignments;
- active/released claims;
- patch candidates;
- tool invocation receipts;
- counters and provenance.

Context Compiler exposes current coding work/claim/patch summary to a coding agent through relevant events and authoritative artifact versions while preserving private memory isolation.

## 12. Fail-closed rules

- unknown/non-coding assignee for coding profile routing -> reject unless explicit audited cross-region assignment path is later added;
- overlapping exclusive claims -> reject atomically;
- patch touching unclaimed scope -> not completion-ready;
- stale architecture/plan -> not completion-ready;
- missing compile/test evidence -> not completion-ready;
- self-produced verification evidence -> cannot independently authorize verification;
- failed/false-accept/regression verification -> reject readiness;
- claim/patch/counter snapshot inconsistency -> reject restore;
- no automatic merge from coding readiness.

## 13. Acceptance tests

- exactly seven permanent core-coding identities and Coding Chief direct-work capability;
- profile specialization is non-identical while all retain universal cognitive floor and learning capability;
- deterministic specialist routing;
- concurrent overlapping write claims fail atomically;
- disjoint claims coexist;
- patch must be covered by claims;
- stale plan/architecture blocks readiness;
- compile/test/external verifier evidence required;
- coder can emit plan/architecture gaps without authority mutation;
- Coding Chief direct work succeeds through normal task/artifact path;
- skill candidate remains personal until promotion;
- exact snapshot/restore;
- all Parts I–IV regressions remain green on Python 3.11/3.13.
