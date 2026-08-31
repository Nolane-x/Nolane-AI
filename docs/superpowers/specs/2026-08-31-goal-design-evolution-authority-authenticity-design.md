# Goal/Design Evolution Authority Authenticity Design

## Problem

Goal/Design integrity evolution receipts are currently content-addressed and bind an exact predecessor, successor, and deterministic delta, but `authority_ref` is only a caller-supplied string. A caller can therefore mint a structurally valid receipt naming `authority:goal-owner` without proving that any trusted authority actually authorized the transition.

The next authority layer must preserve the existing lineage and tamper-evidence guarantees while making permission independently verifiable and fail-closed.

## Security boundary

The runtime must not infer authority from names, provenance strings, predecessor hashes, receipt content, or persisted runtime state. Authority exists only when an injected `GoalIntegrityEvolutionAuthorityVerifier` can resolve the receipt's `authority_ref` to a verifier-issued authorization proof.

The verifier receives two trust inputs out of band: a bounded set of trusted root issuer identities and an authority authentication key. Neither input is learned from serialized authority state. The key authenticates grants, authorization proofs, and the complete authority-registry state; therefore recomputing a public content digest is not sufficient to forge a grant, erase revocation, inject a proof, or create a new trust anchor after restart.

This verifier is a security boundary/service abstraction. Code permitted to invoke root-grant issuance is trusted control-plane code; ordinary integrity-contract callers receive proof references but do not acquire the authority key.

## Capability model

A `GoalIntegrityEvolutionGrant` is immutable, content-addressed, and authority-authenticated. It binds:

- issuer identity;
- subject identity;
- allowed goal IDs;
- allowed actions;
- validity window;
- optional parent grant;
- delegation permission and bounded remaining delegation depth;
- an authentication tag generated from the out-of-band authority key.

A root grant can be issued only for an externally configured trusted-root issuer. A delegated grant is accepted only when its authenticated parent exists and the child is an attenuation of the parent: issuer equals parent subject, goal/action scope is a subset, validity is contained by the parent, and delegation depth cannot expand. Serialized state is replay-validated against these constraints after its keyed state authenticator is verified.

## Authorization proof

The leaf grant is not itself sufficient to mutate a contract. The verifier issues an authenticated, content-addressed `GoalIntegrityEvolutionAuthorizationProof` only after validating the complete grant chain at verifier-controlled clock time.

The proof binds:

- grant ID and authorized subject;
- goal ID;
- predecessor digest;
- successor digest;
- deterministic delta digest;
- action `goal_integrity_contract_evolution`;
- verifier-issued timestamp;
- a verifier authentication tag.

The evolution receipt's `authority_ref` points to this proof ID. Runtime verification therefore requires both the existing receipt identity checks and an independent verifier lookup proving that the exact transition was authorized. A proof-shaped dataclass supplied by a caller has no authority unless its ID exists in the verifier registry and its authentication tag validates.

## Revocation and time

Revocation is recorded with verifier-controlled time. A revoked grant cannot issue new proofs at or after its revocation time; revoking an ancestor disables future proof issuance through descendants. Proofs legitimately issued before revocation remain historically authentic, preventing later revocation from corrupting already committed history while still closing future authority.

Expired or not-yet-valid grants cannot issue proofs. Caller-supplied timestamps are not accepted for proof issuance, preventing backdating around revocation/expiry.

## Persistence and migration

Authority registry state contains grants, revocation timestamps, authorization proofs, a public deterministic state digest, and a keyed state authenticator. The authority key and trusted-root configuration are never serialized. Restore first verifies the public digest and keyed state authenticator, then revalidates grant authentication, delegation attenuation, revocations, proof authentication, and exact grant-chain validity at each proof's issue time.

The accepted v0.2 integrity runtime and v0.1 evolution protocol are frozen into private compatibility modules before public v0.3/v0.2 layers are introduced. Public runtime state advances to schema v3.

- historical v1 runtime revisions remain `legacy_unattested`;
- v2 revisions whose receipts predate verifier-issued proofs migrate as `legacy_unverified_authority` rather than being falsely upgraded;
- new v3 revisions are `verified_capability_authority` and require verifier proof at install and restore.

Persisting a verifier proof ID never persists or fabricates verifier trust, root configuration, or the authority authentication key itself.

## Runtime flow

For a changed non-root integrity contract:

1. Verify predecessor lineage exactly as before.
2. Verify the evolution receipt's content identity and exact transition/delta binding.
3. Require an injected authority-authenticity verifier.
4. Resolve `authority_ref` through that verifier.
5. Verify the registered authorization proof's authenticator and exact goal/predecessor/successor/delta binding.
6. Revalidate the authenticated grant chain at the proof's verifier-issued time.
7. Only after all checks succeed, mutate contract state and record the verified receipt.

Any verifier absence, unknown proof, invalid authenticator, grant-chain failure, scope mismatch, temporal failure, revocation, or proof/transition mismatch fails before state mutation.

## Acceptance criteria

The wave is accepted only with RED -> GREEN evidence for all of the following:

- a self-asserted authority string cannot authorize a transition;
- an exact verifier-issued proof can authorize it;
- proof reuse for another transition fails;
- goal/action scope escalation fails;
- expired and not-yet-valid grants fail;
- revoked grants and descendants cannot issue new proofs;
- delegated grants cannot broaden parent scope, validity, or delegation depth;
- tampered grant/proof/registry state fails restore even if its public digest is recomputed;
- authority key material is absent from serialized state;
- v2 persisted revisions migrate without fabricated verifier trust;
- v3 runtime restore re-verifies authorization proofs;
- existing Goal/Design and Refoundation gates remain green.
