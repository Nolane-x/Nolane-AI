from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


_SHA1_RE = re.compile(r"^[0-9a-fA-F]{40}$")


class LegacyDisposition(str, Enum):
    KEEP = "keep"
    COMPATIBILITY = "compatibility"
    HISTORY = "history"
    CANONICALIZED = "canonicalized"


class ReviewDepth(str, Enum):
    UNREVIEWED = "unreviewed"
    FAMILY_MAPPED = "family_mapped"
    CONTRACT_REVIEWED = "contract_reviewed"
    LINE_REVIEWED = "line_reviewed"


@dataclass(frozen=True, slots=True)
class LegacyPathRecord:
    """One zero-loss migration row for an existing repository path.

    The record is intentionally fail-closed.  Wave 1 never asks callers to
    prove that deletion is safe by absence of failures; it requires positive
    review, parity, migration and history-provenance receipts.
    """

    path: str
    disposition: LegacyDisposition = LegacyDisposition.KEEP
    review_depth: ReviewDepth = ReviewDepth.UNREVIEWED
    blob_sha: str | None = None
    canonical_destination: str | None = None
    parity_receipt: str | None = None
    migration_receipt: str | None = None
    history_provenance: str | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.path.strip() or self.path.startswith("/") or ".." in self.path.split("/"):
            raise ValueError("legacy path must be a normalized repository-relative path")
        if self.blob_sha is not None and _SHA1_RE.fullmatch(self.blob_sha) is None:
            raise ValueError("legacy blob SHA must be a full 40-hex Git blob SHA")
        for value, label in (
            (self.parity_receipt, "parity receipt"),
            (self.migration_receipt, "migration receipt"),
            (self.history_provenance, "history provenance"),
        ):
            if value is not None and not str(value).strip():
                raise ValueError(f"{label} cannot be blank")

    @property
    def destructive_action_allowed(self) -> bool:
        return bool(
            self.disposition in {LegacyDisposition.HISTORY, LegacyDisposition.CANONICALIZED}
            and self.review_depth is ReviewDepth.LINE_REVIEWED
            and self.blob_sha
            and self.parity_receipt
            and self.migration_receipt
            and self.history_provenance
        )

    def require_destructive_action(self) -> None:
        if not self.destructive_action_allowed:
            raise PermissionError(
                "destructive migration is blocked until line review, blob identity, "
                "parity evidence, migration receipt and history provenance are all present"
            )

    def to_state(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "disposition": self.disposition.value,
            "review_depth": self.review_depth.value,
            "blob_sha": self.blob_sha,
            "canonical_destination": self.canonical_destination,
            "parity_receipt": self.parity_receipt,
            "migration_receipt": self.migration_receipt,
            "history_provenance": self.history_provenance,
            "notes": list(self.notes),
            "destructive_action_allowed": self.destructive_action_allowed,
        }


WAVE1_PRESERVED_LEGACY_PATHS: tuple[LegacyPathRecord, ...] = (
    LegacyPathRecord(
        path="cogcoder/organization/runtime_core.py",
        disposition=LegacyDisposition.COMPATIBILITY,
        review_depth=ReviewDepth.LINE_REVIEWED,
        notes=("accepted runtime core remains live during manifest bootstrap",),
    ),
    LegacyPathRecord(
        path="cogcoder/organization/runtime_part13.py",
        disposition=LegacyDisposition.COMPATIBILITY,
        review_depth=ReviewDepth.LINE_REVIEWED,
        notes=("Part XIII coordination runtime layer remains loadable",),
    ),
    LegacyPathRecord(
        path="cogcoder/organization/runtime_part14.py",
        disposition=LegacyDisposition.COMPATIBILITY,
        review_depth=ReviewDepth.LINE_REVIEWED,
        notes=("Part XIV Foundry history/runtime layer remains loadable",),
    ),
    LegacyPathRecord(
        path="cogcoder/organization/runtime_part15.py",
        disposition=LegacyDisposition.COMPATIBILITY,
        review_depth=ReviewDepth.LINE_REVIEWED,
        notes=("Part XV evaluation/scaling boundary remains authoritative",),
    ),
    LegacyPathRecord(
        path="cogcoder/organization/runtime.py",
        disposition=LegacyDisposition.COMPATIBILITY,
        review_depth=ReviewDepth.LINE_REVIEWED,
        notes=("current campaign/execution runtime remains production-compatible",),
    ),
)
