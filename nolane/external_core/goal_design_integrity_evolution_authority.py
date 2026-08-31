"""Authenticated capability authority for Goal/Design integrity evolution.

The integrity runtime must never treat a provenance label as permission. This
module supplies a provider-neutral verifier boundary whose grants, transition
proofs, revocations and persisted registry state are authenticated with an
out-of-band authority key that is never serialized.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
from typing import Any, Callable, Iterable, Mapping

from .goal_design import stable_digest
from ._goal_design_integrity_evolution_v01 import assess_goal_integrity_evolution
from .goal_design_integrity import GoalIntegrityContract

__version__ = "0.1.1"

AUTHORITY_STATE_SCHEMA_VERSION = 1
GOAL_INTEGRITY_EVOLUTION_ACTION = "goal_integrity_contract_evolution"
_MAX_REF = 512
_MAX_SCOPE = 128


def _ref(name: str, value: Any) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    if len(normalized) > _MAX_REF:
        raise ValueError(f"{name} exceeds bounded field limit")
    return normalized


def _scope(name: str, values: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(sorted({_ref(name, value) for value in values}))
    if not normalized:
        raise ValueError(f"{name} requires at least one value")
    if len(normalized) > _MAX_SCOPE:
        raise ValueError(f"{name} exceeds bounded scope")
    return normalized


def _epoch(name: str, value: Any) -> int:
    normalized = int(value)
    if normalized < 0:
        raise ValueError(f"{name} cannot be negative")
    return normalized


def _key_bytes(value: bytes | bytearray | memoryview) -> bytes:
    key = bytes(value)
    if len(key) < 16:
        raise ValueError("Goal/Design evolution authority key must be at least 128 bits")
    return key


def _mac(key: bytes, domain: str, identity: str) -> str:
    message = f"nolane-goal-design:{domain}:{identity}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class GoalIntegrityEvolutionGrant:
    """Authenticated, attenuating capability grant issued by the verifier."""

    grant_id: str
    auth_tag: str
    issuer_ref: str
    subject_ref: str
    goal_ids: tuple[str, ...]
    actions: tuple[str, ...]
    valid_from_epoch_s: int
    valid_until_epoch_s: int
    parent_grant_id: str | None = None
    can_delegate: bool = False
    delegation_depth_remaining: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "grant_id", _ref("grant_id", self.grant_id))
        object.__setattr__(self, "auth_tag", _ref("auth_tag", self.auth_tag))
        object.__setattr__(self, "issuer_ref", _ref("issuer_ref", self.issuer_ref))
        object.__setattr__(self, "subject_ref", _ref("subject_ref", self.subject_ref))
        object.__setattr__(self, "goal_ids", _scope("goal_id", self.goal_ids))
        object.__setattr__(self, "actions", _scope("action", self.actions))
        start = _epoch("valid_from_epoch_s", self.valid_from_epoch_s)
        end = _epoch("valid_until_epoch_s", self.valid_until_epoch_s)
        if end < start:
            raise ValueError("grant validity window is inverted")
        object.__setattr__(self, "valid_from_epoch_s", start)
        object.__setattr__(self, "valid_until_epoch_s", end)
        parent = None if self.parent_grant_id is None else _ref("parent_grant_id", self.parent_grant_id)
        object.__setattr__(self, "parent_grant_id", parent)
        depth = int(self.delegation_depth_remaining)
        if depth < 0 or depth > 32:
            raise ValueError("delegation_depth_remaining must be between 0 and 32")
        if not bool(self.can_delegate) and depth != 0:
            raise ValueError("non-delegating grant cannot retain delegation depth")
        if bool(self.can_delegate) and depth == 0:
            raise ValueError("delegating grant requires positive remaining depth")
        object.__setattr__(self, "can_delegate", bool(self.can_delegate))
        object.__setattr__(self, "delegation_depth_remaining", depth)


@dataclass(frozen=True)
class GoalIntegrityEvolutionAuthorizationProof:
    """Verifier-issued permission for one exact integrity transition."""

    proof_id: str
    auth_tag: str
    grant_id: str
    subject_ref: str
    goal_id: str
    predecessor_digest: str
    successor_digest: str
    delta_digest: str
    action: str
    issued_at_epoch_s: int

    def __post_init__(self) -> None:
        for field in (
            "proof_id",
            "auth_tag",
            "grant_id",
            "subject_ref",
            "goal_id",
            "predecessor_digest",
            "successor_digest",
            "delta_digest",
            "action",
        ):
            object.__setattr__(self, field, _ref(field, getattr(self, field)))
        object.__setattr__(self, "issued_at_epoch_s", _epoch("issued_at_epoch_s", self.issued_at_epoch_s))


def _grant_payload(grant: GoalIntegrityEvolutionGrant) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "issuer_ref": grant.issuer_ref,
        "subject_ref": grant.subject_ref,
        "goal_ids": grant.goal_ids,
        "actions": grant.actions,
        "valid_from_epoch_s": grant.valid_from_epoch_s,
        "valid_until_epoch_s": grant.valid_until_epoch_s,
        "parent_grant_id": grant.parent_grant_id,
        "can_delegate": grant.can_delegate,
        "delegation_depth_remaining": grant.delegation_depth_remaining,
    }


def expected_goal_integrity_evolution_grant_id(grant: GoalIntegrityEvolutionGrant) -> str:
    return stable_digest({"goal_integrity_evolution_grant": _grant_payload(grant)})


def _proof_payload(proof: GoalIntegrityEvolutionAuthorizationProof) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "grant_id": proof.grant_id,
        "subject_ref": proof.subject_ref,
        "goal_id": proof.goal_id,
        "predecessor_digest": proof.predecessor_digest,
        "successor_digest": proof.successor_digest,
        "delta_digest": proof.delta_digest,
        "action": proof.action,
        "issued_at_epoch_s": proof.issued_at_epoch_s,
    }


def expected_goal_integrity_evolution_proof_id(
    proof: GoalIntegrityEvolutionAuthorizationProof,
) -> str:
    return stable_digest({"goal_integrity_evolution_authorization_proof": _proof_payload(proof)})


def _grant_to_state(grant: GoalIntegrityEvolutionGrant) -> dict[str, Any]:
    return {"grant_id": grant.grant_id, "auth_tag": grant.auth_tag, **_grant_payload(grant)}


def _grant_from_state(state: Mapping[str, Any]) -> GoalIntegrityEvolutionGrant:
    return GoalIntegrityEvolutionGrant(
        grant_id=str(state["grant_id"]),
        auth_tag=str(state["auth_tag"]),
        issuer_ref=str(state["issuer_ref"]),
        subject_ref=str(state["subject_ref"]),
        goal_ids=tuple(str(value) for value in state.get("goal_ids", ())),
        actions=tuple(str(value) for value in state.get("actions", ())),
        valid_from_epoch_s=int(state["valid_from_epoch_s"]),
        valid_until_epoch_s=int(state["valid_until_epoch_s"]),
        parent_grant_id=(None if state.get("parent_grant_id") is None else str(state["parent_grant_id"])),
        can_delegate=bool(state.get("can_delegate", False)),
        delegation_depth_remaining=int(state.get("delegation_depth_remaining", 0)),
    )


def _proof_to_state(proof: GoalIntegrityEvolutionAuthorizationProof) -> dict[str, Any]:
    return {"proof_id": proof.proof_id, "auth_tag": proof.auth_tag, **_proof_payload(proof)}


def _proof_from_state(state: Mapping[str, Any]) -> GoalIntegrityEvolutionAuthorizationProof:
    return GoalIntegrityEvolutionAuthorizationProof(
        proof_id=str(state["proof_id"]),
        auth_tag=str(state["auth_tag"]),
        grant_id=str(state["grant_id"]),
        subject_ref=str(state["subject_ref"]),
        goal_id=str(state["goal_id"]),
        predecessor_digest=str(state["predecessor_digest"]),
        successor_digest=str(state["successor_digest"]),
        delta_digest=str(state["delta_digest"]),
        action=str(state["action"]),
        issued_at_epoch_s=int(state["issued_at_epoch_s"]),
    )


class GoalIntegrityEvolutionAuthorityVerifier:
    """Fail-closed authority service for contract-evolution capabilities."""

    def __init__(
        self,
        *,
        trusted_root_issuers: Iterable[str],
        authority_key: bytes | bytearray | memoryview,
        clock: Callable[[], int],
    ) -> None:
        roots = tuple(sorted({_ref("trusted_root_issuer", value) for value in trusted_root_issuers}))
        if not roots:
            raise ValueError("at least one trusted Goal/Design evolution root issuer is required")
        if not callable(clock):
            raise TypeError("clock must be callable")
        self._trusted_root_issuers = frozenset(roots)
        self._authority_key = _key_bytes(authority_key)
        self._clock = clock
        self._grants: dict[str, GoalIntegrityEvolutionGrant] = {}
        self._revoked_at: dict[str, int] = {}
        self._proofs: dict[str, GoalIntegrityEvolutionAuthorizationProof] = {}

    def _now(self) -> int:
        return _epoch("authority clock", self._clock())

    def _sign_grant(self, provisional: GoalIntegrityEvolutionGrant) -> GoalIntegrityEvolutionGrant:
        grant_id = expected_goal_integrity_evolution_grant_id(provisional)
        return GoalIntegrityEvolutionGrant(
            **{
                **provisional.__dict__,
                "grant_id": grant_id,
                "auth_tag": _mac(self._authority_key, "grant", grant_id),
            }
        )

    def _verify_grant_authenticity(self, grant: GoalIntegrityEvolutionGrant) -> None:
        expected_id = expected_goal_integrity_evolution_grant_id(grant)
        if grant.grant_id != expected_id:
            raise ValueError("Goal/Design evolution grant identity digest mismatch")
        expected_tag = _mac(self._authority_key, "grant", expected_id)
        if not hmac.compare_digest(grant.auth_tag, expected_tag):
            raise ValueError("Goal/Design evolution grant authenticator mismatch")

    def _validate_grant_structure(
        self,
        grant: GoalIntegrityEvolutionGrant,
        *,
        trail: frozenset[str] = frozenset(),
    ) -> None:
        self._verify_grant_authenticity(grant)
        if grant.grant_id in trail:
            raise ValueError("Goal/Design evolution delegation cycle detected")
        if grant.parent_grant_id is None:
            if grant.issuer_ref not in self._trusted_root_issuers:
                raise ValueError("Goal/Design evolution root grant issuer is not trusted")
            return
        parent = self._grants.get(grant.parent_grant_id)
        if parent is None:
            raise ValueError("Goal/Design evolution delegated grant has unknown parent")
        self._validate_grant_structure(parent, trail=trail | {grant.grant_id})
        if not parent.can_delegate or parent.delegation_depth_remaining <= 0:
            raise ValueError("Goal/Design evolution parent grant cannot delegate")
        if grant.issuer_ref != parent.subject_ref:
            raise ValueError("Goal/Design evolution delegated grant issuer is not parent subject")
        if not set(grant.goal_ids).issubset(parent.goal_ids):
            raise ValueError("Goal/Design evolution delegated goal scope broadens parent")
        if not set(grant.actions).issubset(parent.actions):
            raise ValueError("Goal/Design evolution delegated action scope broadens parent")
        if grant.valid_from_epoch_s < parent.valid_from_epoch_s or grant.valid_until_epoch_s > parent.valid_until_epoch_s:
            raise ValueError("Goal/Design evolution delegated validity broadens parent")
        if grant.delegation_depth_remaining > parent.delegation_depth_remaining - 1:
            raise ValueError("Goal/Design evolution delegated depth broadens parent")

    def issue_root_grant(
        self,
        *,
        issuer_ref: str,
        subject_ref: str,
        goal_ids: Iterable[str],
        actions: Iterable[str] = (GOAL_INTEGRITY_EVOLUTION_ACTION,),
        valid_from_epoch_s: int,
        valid_until_epoch_s: int,
        can_delegate: bool = False,
        delegation_depth_remaining: int = 0,
    ) -> GoalIntegrityEvolutionGrant:
        issuer = _ref("issuer_ref", issuer_ref)
        if issuer not in self._trusted_root_issuers:
            raise ValueError("Goal/Design evolution root issuer is not trusted")
        provisional = GoalIntegrityEvolutionGrant(
            grant_id="pending",
            auth_tag="pending",
            issuer_ref=issuer,
            subject_ref=subject_ref,
            goal_ids=tuple(goal_ids),
            actions=tuple(actions),
            valid_from_epoch_s=valid_from_epoch_s,
            valid_until_epoch_s=valid_until_epoch_s,
            parent_grant_id=None,
            can_delegate=can_delegate,
            delegation_depth_remaining=delegation_depth_remaining,
        )
        grant = self._sign_grant(provisional)
        existing = self._grants.get(grant.grant_id)
        if existing is not None and existing != grant:
            raise ValueError("Goal/Design evolution grant identity collision")
        self._grants[grant.grant_id] = grant
        return grant

    def delegate_grant(
        self,
        parent_grant_id: str,
        *,
        subject_ref: str,
        goal_ids: Iterable[str],
        actions: Iterable[str],
        valid_from_epoch_s: int,
        valid_until_epoch_s: int,
        can_delegate: bool = False,
        delegation_depth_remaining: int = 0,
    ) -> GoalIntegrityEvolutionGrant:
        parent_id = _ref("parent_grant_id", parent_grant_id)
        try:
            parent = self._grants[parent_id]
        except KeyError as exc:
            raise ValueError("unknown Goal/Design evolution parent grant") from exc
        provisional = GoalIntegrityEvolutionGrant(
            grant_id="pending",
            auth_tag="pending",
            issuer_ref=parent.subject_ref,
            subject_ref=subject_ref,
            goal_ids=tuple(goal_ids),
            actions=tuple(actions),
            valid_from_epoch_s=valid_from_epoch_s,
            valid_until_epoch_s=valid_until_epoch_s,
            parent_grant_id=parent_id,
            can_delegate=can_delegate,
            delegation_depth_remaining=delegation_depth_remaining,
        )
        grant = self._sign_grant(provisional)
        self._grants[grant.grant_id] = grant
        try:
            self._validate_grant_structure(grant)
        except Exception:
            self._grants.pop(grant.grant_id, None)
            raise
        return grant

    def revoke_grant(self, grant_id: str) -> int:
        identity = _ref("grant_id", grant_id)
        if identity not in self._grants:
            raise ValueError("cannot revoke unknown Goal/Design evolution grant")
        now = self._now()
        existing = self._revoked_at.get(identity)
        if existing is None or now < existing:
            self._revoked_at[identity] = now
        return self._revoked_at[identity]

    def _validate_chain_at(
        self,
        grant_id: str,
        epoch_s: int,
        *,
        trail: frozenset[str] = frozenset(),
    ) -> GoalIntegrityEvolutionGrant:
        identity = _ref("grant_id", grant_id)
        if identity in trail:
            raise ValueError("Goal/Design evolution delegation cycle detected")
        try:
            grant = self._grants[identity]
        except KeyError as exc:
            raise ValueError("unknown Goal/Design evolution grant") from exc
        self._validate_grant_structure(grant)
        moment = _epoch("authorization time", epoch_s)
        if moment < grant.valid_from_epoch_s or moment > grant.valid_until_epoch_s:
            raise ValueError("Goal/Design evolution grant is outside its validity window")
        revoked = self._revoked_at.get(identity)
        if revoked is not None and revoked <= moment:
            raise ValueError("Goal/Design evolution grant is revoked")
        if grant.parent_grant_id is not None:
            self._validate_chain_at(
                grant.parent_grant_id,
                moment,
                trail=trail | {identity},
            )
        return grant

    def _assert_live_chain_not_revoked(
        self,
        grant_id: str,
        *,
        trail: frozenset[str] = frozenset(),
    ) -> None:
        """Treat any recorded revocation as permanent for new live mutations."""

        identity = _ref("grant_id", grant_id)
        if identity in trail:
            raise ValueError("Goal/Design evolution delegation cycle detected")
        try:
            grant = self._grants[identity]
        except KeyError as exc:
            raise ValueError("unknown Goal/Design evolution grant") from exc
        if identity in self._revoked_at:
            raise ValueError("Goal/Design evolution grant is revoked for live use")
        if grant.parent_grant_id is not None:
            self._assert_live_chain_not_revoked(
                grant.parent_grant_id,
                trail=trail | {identity},
            )

    def _sign_proof(
        self,
        provisional: GoalIntegrityEvolutionAuthorizationProof,
    ) -> GoalIntegrityEvolutionAuthorizationProof:
        proof_id = expected_goal_integrity_evolution_proof_id(provisional)
        return GoalIntegrityEvolutionAuthorizationProof(
            **{
                **provisional.__dict__,
                "proof_id": proof_id,
                "auth_tag": _mac(self._authority_key, "proof", proof_id),
            }
        )

    def _verify_proof_authenticity(self, proof: GoalIntegrityEvolutionAuthorizationProof) -> None:
        expected_id = expected_goal_integrity_evolution_proof_id(proof)
        if proof.proof_id != expected_id:
            raise ValueError("Goal/Design evolution authorization proof identity mismatch")
        expected_tag = _mac(self._authority_key, "proof", expected_id)
        if not hmac.compare_digest(proof.auth_tag, expected_tag):
            raise ValueError("Goal/Design evolution authorization proof authenticator mismatch")

    def issue_authorization(
        self,
        grant_id: str,
        *,
        goal_id: str,
        predecessor_digest: str,
        successor_digest: str,
        delta_digest: str,
        action: str = GOAL_INTEGRITY_EVOLUTION_ACTION,
    ) -> GoalIntegrityEvolutionAuthorizationProof:
        now = self._now()
        grant = self._validate_chain_at(grant_id, now)
        goal = _ref("goal_id", goal_id)
        normalized_action = _ref("action", action)
        if goal not in grant.goal_ids:
            raise ValueError("Goal/Design evolution grant does not cover goal")
        if normalized_action not in grant.actions:
            raise ValueError("Goal/Design evolution grant does not cover action")
        provisional = GoalIntegrityEvolutionAuthorizationProof(
            proof_id="pending",
            auth_tag="pending",
            grant_id=grant.grant_id,
            subject_ref=grant.subject_ref,
            goal_id=goal,
            predecessor_digest=predecessor_digest,
            successor_digest=successor_digest,
            delta_digest=delta_digest,
            action=normalized_action,
            issued_at_epoch_s=now,
        )
        proof = self._sign_proof(provisional)
        existing = self._proofs.get(proof.proof_id)
        if existing is not None and existing != proof:
            raise ValueError("Goal/Design evolution authorization proof identity collision")
        self._proofs[proof.proof_id] = proof
        return proof

    def authorize_contract_transition(
        self,
        grant_id: str,
        *,
        predecessor: GoalIntegrityContract,
        successor: GoalIntegrityContract,
    ) -> GoalIntegrityEvolutionAuthorizationProof:
        delta = assess_goal_integrity_evolution(predecessor, successor)
        return self.issue_authorization(
            grant_id,
            goal_id=predecessor.goal_id,
            predecessor_digest=predecessor.digest,
            successor_digest=successor.digest,
            delta_digest=delta.digest,
        )

    def verify_authorization_proof(
        self,
        proof_id: str,
        *,
        goal_id: str,
        predecessor_digest: str,
        successor_digest: str,
        delta_digest: str,
        action: str = GOAL_INTEGRITY_EVOLUTION_ACTION,
    ) -> GoalIntegrityEvolutionAuthorizationProof:
        """Verify historical authenticity at the proof's verifier-issued time."""

        identity = _ref("proof_id", proof_id)
        try:
            proof = self._proofs[identity]
        except KeyError as exc:
            raise ValueError("unknown Goal/Design evolution authorization proof") from exc
        self._verify_proof_authenticity(proof)
        expected = {
            "goal_id": _ref("goal_id", goal_id),
            "predecessor_digest": _ref("predecessor_digest", predecessor_digest),
            "successor_digest": _ref("successor_digest", successor_digest),
            "delta_digest": _ref("delta_digest", delta_digest),
            "action": _ref("action", action),
        }
        for field, value in expected.items():
            if getattr(proof, field) != value:
                raise ValueError(f"Goal/Design evolution authorization proof {field} mismatch")
        grant = self._validate_chain_at(proof.grant_id, proof.issued_at_epoch_s)
        if proof.subject_ref != grant.subject_ref:
            raise ValueError("Goal/Design evolution authorization proof subject mismatch")
        if proof.goal_id not in grant.goal_ids or proof.action not in grant.actions:
            raise ValueError("Goal/Design evolution authorization proof exceeds grant scope")
        return proof

    def verify_live_authorization_proof(
        self,
        proof_id: str,
        *,
        goal_id: str,
        predecessor_digest: str,
        successor_digest: str,
        delta_digest: str,
        action: str = GOAL_INTEGRITY_EVOLUTION_ACTION,
    ) -> GoalIntegrityEvolutionAuthorizationProof:
        """Verify a proof for a new mutation under current, non-revived authority."""

        proof = self.verify_authorization_proof(
            proof_id,
            goal_id=goal_id,
            predecessor_digest=predecessor_digest,
            successor_digest=successor_digest,
            delta_digest=delta_digest,
            action=action,
        )
        now = self._now()
        if now < proof.issued_at_epoch_s:
            raise ValueError("Goal/Design evolution authority clock precedes proof issuance")
        self._assert_live_chain_not_revoked(proof.grant_id)
        self._validate_chain_at(proof.grant_id, now)
        return proof

    def verify_contract_transition(
        self,
        proof_id: str,
        *,
        predecessor: GoalIntegrityContract,
        successor: GoalIntegrityContract,
    ) -> GoalIntegrityEvolutionAuthorizationProof:
        delta = assess_goal_integrity_evolution(predecessor, successor)
        return self.verify_authorization_proof(
            proof_id,
            goal_id=predecessor.goal_id,
            predecessor_digest=predecessor.digest,
            successor_digest=successor.digest,
            delta_digest=delta.digest,
        )

    def grant(self, grant_id: str) -> GoalIntegrityEvolutionGrant:
        try:
            return self._grants[_ref("grant_id", grant_id)]
        except KeyError as exc:
            raise KeyError(f"unknown Goal/Design evolution grant {grant_id}") from exc

    def proof(self, proof_id: str) -> GoalIntegrityEvolutionAuthorizationProof:
        try:
            return self._proofs[_ref("proof_id", proof_id)]
        except KeyError as exc:
            raise KeyError(f"unknown Goal/Design evolution authorization proof {proof_id}") from exc

    @staticmethod
    def _state_digest(payload: Mapping[str, Any]) -> str:
        return stable_digest({"goal_integrity_evolution_authority_state_v1": dict(payload)})

    def state(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": AUTHORITY_STATE_SCHEMA_VERSION,
            "grants": [_grant_to_state(self._grants[key]) for key in sorted(self._grants)],
            "revocations": [
                {"grant_id": key, "revoked_at_epoch_s": self._revoked_at[key]}
                for key in sorted(self._revoked_at)
            ],
            "proofs": [_proof_to_state(self._proofs[key]) for key in sorted(self._proofs)],
        }
        digest = self._state_digest(payload)
        return {
            **payload,
            "state_digest": digest,
            "state_auth_tag": _mac(self._authority_key, "state", digest),
        }

    @classmethod
    def restore_state(
        cls,
        state: Mapping[str, Any],
        *,
        trusted_root_issuers: Iterable[str],
        authority_key: bytes | bytearray | memoryview,
        clock: Callable[[], int],
    ) -> "GoalIntegrityEvolutionAuthorityVerifier":
        verifier = cls(
            trusted_root_issuers=trusted_root_issuers,
            authority_key=authority_key,
            clock=clock,
        )
        schema = int(state.get("schema_version", 0))
        if schema != AUTHORITY_STATE_SCHEMA_VERSION:
            raise ValueError("unsupported Goal/Design evolution authority state schema")
        payload: dict[str, Any] = {
            "schema_version": schema,
            "grants": state.get("grants", ()),
            "revocations": state.get("revocations", ()),
            "proofs": state.get("proofs", ()),
        }
        digest = verifier._state_digest(payload)
        if str(state.get("state_digest", "")) != digest:
            raise ValueError("Goal/Design evolution authority state digest mismatch")
        expected_tag = _mac(verifier._authority_key, "state", digest)
        if not hmac.compare_digest(str(state.get("state_auth_tag", "")), expected_tag):
            raise ValueError("Goal/Design evolution authority state authenticator mismatch")

        for row in payload["grants"]:
            grant = _grant_from_state(row)
            if grant.grant_id in verifier._grants:
                raise ValueError("duplicate Goal/Design evolution grant in state")
            verifier._verify_grant_authenticity(grant)
            verifier._grants[grant.grant_id] = grant
        for grant in verifier._grants.values():
            verifier._validate_grant_structure(grant)

        for row in payload["revocations"]:
            grant_id = _ref("grant_id", row["grant_id"])
            if grant_id not in verifier._grants:
                raise ValueError("Goal/Design evolution revocation references unknown grant")
            if grant_id in verifier._revoked_at:
                raise ValueError("duplicate Goal/Design evolution revocation in state")
            verifier._revoked_at[grant_id] = _epoch("revoked_at_epoch_s", row["revoked_at_epoch_s"])

        for row in payload["proofs"]:
            proof = _proof_from_state(row)
            if proof.proof_id in verifier._proofs:
                raise ValueError("duplicate Goal/Design evolution proof in state")
            verifier._verify_proof_authenticity(proof)
            verifier._proofs[proof.proof_id] = proof
        for proof in verifier._proofs.values():
            verifier.verify_authorization_proof(
                proof.proof_id,
                goal_id=proof.goal_id,
                predecessor_digest=proof.predecessor_digest,
                successor_digest=proof.successor_digest,
                delta_digest=proof.delta_digest,
                action=proof.action,
            )
        return verifier


__all__ = [
    "AUTHORITY_STATE_SCHEMA_VERSION",
    "GOAL_INTEGRITY_EVOLUTION_ACTION",
    "GoalIntegrityEvolutionAuthorizationProof",
    "GoalIntegrityEvolutionAuthorityVerifier",
    "GoalIntegrityEvolutionGrant",
    "expected_goal_integrity_evolution_grant_id",
    "expected_goal_integrity_evolution_proof_id",
]
