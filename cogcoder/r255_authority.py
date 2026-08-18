from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest_payload(
    *,
    objective: str,
    allowed_actions: Iterable[str],
    allowed_side_effect_classes: Iterable[str],
    issuer: str,
    parent_digest: str | None,
) -> str:
    payload = {
        "objective": str(objective),
        "allowed_actions": sorted({str(x) for x in allowed_actions}),
        "allowed_side_effect_classes": sorted({str(x) for x in allowed_side_effect_classes}),
        "issuer": str(issuer),
        "parent_digest": parent_digest,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AuthorityEnvelope:
    """Host-issued control-plane authority, minted before untrusted data is read.

    The envelope is intentionally capability-like rather than advisory. Retrieved
    documents/tool responses may influence proposals, but they cannot mint or widen
    this envelope because the issuer and digest are host-owned and every child scope
    must be a subset of its parent.
    """

    objective: str
    allowed_actions: frozenset[str]
    allowed_side_effect_classes: frozenset[str]
    issuer: str
    parent_digest: str | None
    digest: str

    @classmethod
    def issue(
        cls,
        *,
        objective: str,
        allowed_actions: Iterable[str],
        allowed_side_effect_classes: Iterable[str],
        issuer: str = "host:runtime",
        parent_digest: str | None = None,
    ) -> "AuthorityEnvelope":
        if not str(issuer).startswith("host:"):
            raise ValueError("authority envelopes must be host-issued")
        actions = frozenset(str(x) for x in allowed_actions)
        side_effects = frozenset(str(x) for x in allowed_side_effect_classes)
        digest = _digest_payload(
            objective=objective,
            allowed_actions=actions,
            allowed_side_effect_classes=side_effects,
            issuer=issuer,
            parent_digest=parent_digest,
        )
        return cls(str(objective), actions, side_effects, str(issuer), parent_digest, digest)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AuthorityEnvelope":
        """Deserialize without recomputing the supplied digest.

        Keeping the serialized digest is deliberate: `verify()` must detect tampering
        rather than silently blessing modified fields by minting a new digest.
        """

        return cls(
            objective=str(payload.get("objective", "")),
            allowed_actions=frozenset(str(x) for x in payload.get("allowed_actions", ())),
            allowed_side_effect_classes=frozenset(
                str(x) for x in payload.get("allowed_side_effect_classes", ())
            ),
            issuer=str(payload.get("issuer", "")),
            parent_digest=payload.get("parent_digest"),
            digest=str(payload.get("digest", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "allowed_actions": sorted(self.allowed_actions),
            "allowed_side_effect_classes": sorted(self.allowed_side_effect_classes),
            "issuer": self.issuer,
            "parent_digest": self.parent_digest,
            "digest": self.digest,
        }

    def verify(self) -> bool:
        if not self.issuer.startswith("host:"):
            return False
        expected = _digest_payload(
            objective=self.objective,
            allowed_actions=self.allowed_actions,
            allowed_side_effect_classes=self.allowed_side_effect_classes,
            issuer=self.issuer,
            parent_digest=self.parent_digest,
        )
        return hashlib.sha256(self.digest.encode()).digest() == hashlib.sha256(expected.encode()).digest()

    def narrow(
        self,
        *,
        allowed_actions: Iterable[str] | None = None,
        allowed_side_effect_classes: Iterable[str] | None = None,
        objective: str | None = None,
    ) -> "AuthorityEnvelope":
        if not self.verify():
            raise ValueError("cannot narrow an invalid authority envelope")
        actions = self.allowed_actions if allowed_actions is None else frozenset(str(x) for x in allowed_actions)
        side_effects = (
            self.allowed_side_effect_classes
            if allowed_side_effect_classes is None
            else frozenset(str(x) for x in allowed_side_effect_classes)
        )
        if not actions.issubset(self.allowed_actions):
            raise ValueError("child authority cannot widen allowed actions")
        if not side_effects.issubset(self.allowed_side_effect_classes):
            raise ValueError("child authority cannot widen side-effect classes")
        return AuthorityEnvelope.issue(
            objective=self.objective if objective is None else str(objective),
            allowed_actions=actions,
            allowed_side_effect_classes=side_effects,
            issuer=self.issuer,
            parent_digest=self.digest,
        )


@dataclass(frozen=True, slots=True)
class ActionProposal:
    action_id: str
    side_effect_class: str
    source: str = "cognition"
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class AuthorityDecision:
    authorized: bool
    reason: str
    authority_digest: str
    action_id: str
    side_effect_class: str


class AuthorityBoundary:
    """Fail-closed authorization boundary between cognition and host actions."""

    def authorize(self, envelope: AuthorityEnvelope, proposal: ActionProposal) -> AuthorityDecision:
        if not envelope.verify():
            return AuthorityDecision(
                False,
                "invalid_authority_envelope",
                envelope.digest,
                proposal.action_id,
                proposal.side_effect_class,
            )
        if proposal.action_id not in envelope.allowed_actions:
            return AuthorityDecision(
                False,
                "action_not_pre_authorized",
                envelope.digest,
                proposal.action_id,
                proposal.side_effect_class,
            )
        if proposal.side_effect_class not in envelope.allowed_side_effect_classes:
            return AuthorityDecision(
                False,
                "side_effect_not_pre_authorized",
                envelope.digest,
                proposal.action_id,
                proposal.side_effect_class,
            )
        return AuthorityDecision(
            True,
            "authorized",
            envelope.digest,
            proposal.action_id,
            proposal.side_effect_class,
        )
