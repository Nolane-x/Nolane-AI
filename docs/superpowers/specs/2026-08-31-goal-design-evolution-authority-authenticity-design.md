# Goal/Design Evolution Authority Authenticity Design

## Problem

Goal/Design integrity evolution receipts are currently content-addressed and bind an exact predecessor, successor, and deterministic delta, but `authority_ref` is only a caller-supplied string. A caller can therefore mint a structurally valid receipt naming `authority:goal-owner` without proving that any trusted authority actually authorized the transition.

The next authority layer must preserve the existing lineage and tamper-evidence guarantees while making permission externally verifiable and fail-closed.

## Security boundary

The runtime must not infer authority from names, provenance strings, predecessor hashes, receipt content, or persisted runtime state. Authority exists only when an injected `GoalIntegrityEvolutionAuthorityVerifier` can resolve the receipt's `authority_ref` to a verifier-issued authorization proof.

Trusted root issuers are configuration supplied outside serialized authority state. Loading serialized grants must never create a new trust anchor.

## Capability model

A `GoalIntegrityEvolutionGrant` is immutable and content-addressed. It binds:

- issuer identity;
- subject identity;
- allowed goal IDs;
- allowed actions;
- validity window;
- optional parent grant;
- delegation permission and bounded remaining delegation depth.

A root grant is accepted only when its issuer is in the verifier's externally configured trusted-root set. A delegated grant is accepted only when its parent exists and the child is an attenuation of the parent: issuer equals parent subject, goal/action scope is a subset, validity is contained by the parent, and delegation depth cannot expand.

## Authorization proof

The leaf grant is not itself sufficient to mutate a contract. The verifier issues a content-addressed `GoalIntegrityEvolutionAuthorizationProof` only after validating the complete grant chain at verifier-controlled clock time.

The proof binds:

- grant ID and authorized subject;
- goal ID;
- predecessor digest;
- successor digest;
- deterministic delta digest;
- action `goal_integrity_contract_evolution`;
- verifier-issued timestamp.

The evolution receipt's `authority_ref` points to this proof ID. Runtime verification therefore requires both the existing receipt identity checks and an independent verifier lookup proving that the exact transition was authorized.

## Revocation and time

Revocation is recorded with verifier-controlled time. A revoked grant cannot issue new proofs at or after its revocation time; revoking an ancestor disables future proof issuance through descendants. Proofs legitimately issued before revocation remain historically authentic, preventing later revocation from corrupting already committed history while still closing future authority.

Expired or not-yet-valid grants cannot issue proofs. Caller-supplied timestamps are not accepted for proof issuance, preventing backdating around revocation/expiry.

## Persistence and migration

Authority registry state is independently content-addressed and can be restored only with the trusted-root set supplied out of band. Restore revalidates grant identities, delegation attenuation, revocation records, proof identities, and exact grant-chain validity at each proof's issue time.

The current v0.2 integrity runtime and v0.1 evolution protocol are frozen into private compatibility modules before public v0.3/v0.2 layers are introduced. Public runtime state advances to schema v3.

- historical v1 runtime revisions remain `legacy_unattested`;
- v2 revisions whose receipts predate verifier-issued proofs migrate as `legacy_unverified_authority` rather than being falsely upgraded;
- new v3 revisions are `verified_capability_authority` and require verifier proof at install and restore.

Persisting a verifier proof ID never persists or fabricates the trust anchor itself.

## Runtime flow

For a changed non-root integrity contract:

1. Verify predecessor lineage exactly as before.
2. Verify the evolution receipt's content identity and exact transition/delta binding.
3. Resolve `authority_ref` through the injected verifier.
4. Verify the referenced authorization proof binds the same goal, predecessor, successor, and delta.
5. Only after all checks succeed, mutate contract state and record the verified receipt.

Any verifier absence, unknown proof, grant-chain failure, scope mismatch, temporal failure, revocation, or proof/transition mismatch fails before state mutation.

## Acceptance criteria

The wave is accepted only with RED -> GREEN evidence for all of the following:

- a self-asserted authority string cannot authorize a transition;
- an exact verifier-issued proof can authorize it;
- proof reuse for another transition fails;
- goal/action scope escalation fails;
- expired and not-yet-valid grants fail;
- revoked grants and descendants cannot issue new proofs;
- delegated grants cannot broaden parent scope or validity;
- tampered grant/proof/registry state fails restore;
- v2 persisted revisions migrate without fabricated verifier trust;
- v3 runtime restore re-verifies authorization proofs;
- existing Goal/Design and Refoundation gates remain green.
