# Goal/Design Evolution Authority Authenticity Design

## Problem

Goal/Design integrity evolution receipts are currently content-addressed and bind an exact predecessor, successor, and deterministic delta, but `authority_ref` is only a caller-supplied string. A caller can therefore mint a structurally valid receipt naming `authority:goal-owner` without proving that any trusted authority actually authorized the transition.

The next authority layer must preserve the existing lineage and tamper-evidence guarantees while making permission independently verifiable and fail-closed.

## Security boundary

The runtime must not infer authority from names, provenance strings, predecessor hashes, receipt content, or persisted runtime state. Authority exists only when an injected `GoalIntegrityEvolutionAuthorityVerifier` can resolve the receipt's `authority_ref` to a verifier-issued authorization proof.

Normal verifier construction receives two trust inputs out of band: a bounded set of trusted root issuer identities and an authority authentication key. Neither input is learned from serialized authority state. The key authenticates grants, authorization proofs, and the complete authority-registry state; therefore recomputing a public content digest is not sufficient to forge a grant, erase revocation, inject a proof, or create a new trust anchor after restart.

State restoration has one additional authority input: an out-of-band `expected_state_digest` selected by a rollback-resistant checkpoint store. The serialized state cannot self-assert that it is the latest state. A valid keyed authenticator proves that a snapshot was issued by the authority, not that the snapshot is current. Consequently, freshness authority must remain outside the serialized blob just like the root configuration and authentication key.

This verifier is a security boundary/service abstraction. Code permitted to invoke root-grant issuance or publish the latest rollback checkpoint is trusted control-plane code; ordinary integrity-contract callers receive proof references but do not acquire the authority key or freshness checkpoint authority.

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

A root grant can be issued only for an externally configured trusted-root issuer. A delegated grant is accepted only when its authenticated parent exists, is live-valid and non-revoked at delegation time, and the child is an attenuation of the parent: issuer equals parent subject, goal/action scope is a subset, validity is contained by the parent, and delegation depth cannot expand. Serialized state is replay-validated against structural constraints after its keyed state authenticator and external freshness checkpoint are verified.

## Authorization proof

The leaf grant is not itself sufficient to mutate a contract. The verifier issues an authenticated, content-addressed `GoalIntegrityEvolutionAuthorizationProof` only after validating the complete live grant chain at verifier-controlled clock time.

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

Revocation is a monotonic authority-state fact. The first verifier-recorded revocation timestamp for a grant is immutable; repeated revocation is idempotent and cannot move that timestamp backward if the verifier clock later regresses. This preserves the truth of previously issued historical proofs.

For **historical verification**, a proof is checked against the grant chain at its verifier-issued timestamp. A proof legitimately issued before revocation therefore remains historically authentic and can be used to verify already committed state after restart.

For **live authority use**, any recorded revocation anywhere in the grant's ancestor chain permanently disables new proof issuance, further delegation, and new runtime mutation, independent of a later clock rollback. A pre-revocation proof cannot be stockpiled and exercised for a new mutation after revocation. Live verification also requires the verifier clock not to precede proof issuance and requires the grant chain to be inside its current validity window.

Expired or not-yet-valid grants cannot mint proofs or perform live delegation. Caller-supplied timestamps are not accepted for proof issuance, preventing backdating around revocation/expiry.

## Persistence, freshness, and migration

Authority registry state contains grants, immutable first-revocation timestamps, authorization proofs, a public deterministic state digest, and a keyed state authenticator. The authority key, trusted-root configuration, and latest-state checkpoint are never serialized.

Restore is deliberately three-layered before semantic replay:

1. recompute and verify the deterministic structural state digest;
2. verify the keyed state authenticator, proving the snapshot was issued by the authority;
3. compare that digest with the required out-of-band `expected_state_digest`, proving this is the externally selected current snapshot rather than an older authentic snapshot.

Only after those checks does restore revalidate grant authentication, delegation attenuation, revocations, proof authentication, and exact grant-chain validity at each proof's issue time.

This separation is required because HMAC authenticity does not imply freshness. Without the external checkpoint, an attacker able to replay storage could present an older, correctly signed pre-revocation snapshot and thereby erase a later revocation from the reconstructed authority state. `restore_state` therefore requires `expected_state_digest`; there is no implicit unsafe fallback that trusts serialized state to name itself as latest. A signed snapshot whose digest differs from the external checkpoint fails closed even when every byte and HMAC is otherwise valid.

The accepted v0.2 integrity runtime and v0.1 evolution protocol are frozen into private compatibility modules before public v0.3/v0.2 layers are introduced. Public runtime state advances to schema v3.

- historical v1 runtime revisions remain `legacy_unattested`;
- v2 revisions whose receipts predate verifier-issued proofs migrate as `legacy_unverified_authority` rather than being falsely upgraded;
- new v3 revisions are `verified_capability_authority` and require verifier proof at install and restore.

Persisting a verifier proof ID never persists or fabricates verifier trust, root configuration, authority authentication key, or latest-state checkpoint.

## Runtime flow

For a changed non-root integrity contract:

1. Verify predecessor lineage exactly as before.
2. Verify the evolution receipt's content identity and exact transition/delta binding.
3. Require an injected authority-authenticity verifier.
4. Resolve `authority_ref` through that verifier.
5. Verify the registered authorization proof's authenticator and exact goal/predecessor/successor/delta binding.
6. Verify historical grant-chain validity at proof issuance.
7. For a new mutation, additionally require current validity, no recorded revocation in the complete ancestor chain, and no verifier-clock rollback before proof issuance.
8. Only after all checks succeed, mutate contract state and record the verified receipt.

Runtime restore intentionally uses historical proof validity rather than requiring currently live authority: later revocation must close future authority without corrupting an already committed, historically authentic transition. Authority-registry restore is separately protected against storage rollback by its required external digest checkpoint.

Any verifier absence, unknown proof, invalid authenticator, state-checkpoint mismatch, grant-chain failure, scope mismatch, temporal failure, revocation, clock rollback, or proof/transition mismatch fails before live state mutation or restored authority publication.

## Acceptance criteria

The wave is accepted only with RED -> GREEN evidence for all of the following:

- a self-asserted authority string cannot authorize a transition;
- an exact verifier-issued proof can authorize it;
- proof reuse for another transition fails;
- goal/action scope escalation fails;
- expired and not-yet-valid grants fail;
- revoked grants and descendants cannot issue new proofs;
- a proof issued before revocation cannot authorize a new mutation after revocation;
- revoked authority cannot be revived by verifier-clock rollback;
- first-revocation time is immutable and repeated revoke cannot invalidate valid pre-revocation history;
- revoked parents cannot continue live delegation;
- delegated grants cannot broaden parent scope, validity, or delegation depth;
- tampered grant/proof/registry state fails restore even if its public digest is recomputed;
- a previously valid signed snapshot cannot roll authority state back behind a newer external checkpoint;
- restore requires an external expected state digest and does not let serialized state self-declare freshness;
- authority key material and rollback checkpoint authority are absent from serialized state;
- v2 persisted revisions migrate without fabricated verifier trust;
- v3 runtime restore re-verifies historical authorization proofs without requiring currently live authority;
- existing Goal/Design and Refoundation gates remain green.
