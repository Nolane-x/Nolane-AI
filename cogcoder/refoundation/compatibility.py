from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.types import canonical_digest

from .manifests import build_bootstrap_agent_manifests


@dataclass(frozen=True, slots=True)
class BootstrapParityReport:
    source_identity_count: int
    manifest_identity_count: int
    missing_agent_ids: tuple[str, ...]
    extra_agent_ids: tuple[str, ...]
    field_mismatches: tuple[str, ...]
    digest: str

    @property
    def clean(self) -> bool:
        return not self.missing_agent_ids and not self.extra_agent_ids and not self.field_mismatches

    def payload(self) -> dict[str, Any]:
        return {
            "source_identity_count": self.source_identity_count,
            "manifest_identity_count": self.manifest_identity_count,
            "missing_agent_ids": list(self.missing_agent_ids),
            "extra_agent_ids": list(self.extra_agent_ids),
            "field_mismatches": list(self.field_mismatches),
        }

    def __post_init__(self) -> None:
        if canonical_digest(self.payload()) != self.digest:
            raise ValueError("bootstrap parity report digest mismatch")


def build_bootstrap_parity_report() -> BootstrapParityReport:
    """Compare canonical manifests against the entire accepted identity state.

    Legacy blueprint data is now a parity oracle only. The canonical manifest
    builder does not import or call it; this report proves the independent
    source retained every serialized AgentIdentity field.
    """

    source = {row.agent_id: row for row in build_first_generation_blueprint()}
    manifests = {row.agent_id: row for row in build_bootstrap_agent_manifests()}
    missing = tuple(sorted(set(source) - set(manifests)))
    extra = tuple(sorted(set(manifests) - set(source)))
    mismatches: list[str] = []
    for agent_id in sorted(set(source) & set(manifests)):
        expected = source[agent_id].to_state()
        actual = manifests[agent_id].identity_state()
        for field in sorted(set(expected) | set(actual)):
            if expected.get(field) != actual.get(field):
                mismatches.append(f"{agent_id}:{field}")

    payload = {
        "source_identity_count": len(source),
        "manifest_identity_count": len(manifests),
        "missing_agent_ids": list(missing),
        "extra_agent_ids": list(extra),
        "field_mismatches": mismatches,
    }
    return BootstrapParityReport(
        source_identity_count=len(source),
        manifest_identity_count=len(manifests),
        missing_agent_ids=missing,
        extra_agent_ids=extra,
        field_mismatches=tuple(mismatches),
        digest=canonical_digest(payload),
    )
