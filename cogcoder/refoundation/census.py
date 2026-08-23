from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from cogcoder.organization.types import canonical_digest

from .migration import LegacyDisposition, LegacyPathRecord, ReviewDepth


class CensusKind(str, Enum):
    SOURCE = "source"
    HISTORICAL_SOURCE = "historical_source"
    TEST = "test"
    WORKFLOW = "workflow"
    RESEARCH = "research"
    RESULT = "result"
    MANIFEST = "manifest"
    MODEL = "model"
    DOCUMENTATION = "documentation"
    THIRD_PARTY = "third_party"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class SourceCensusRecord:
    path: str
    kind: CensusKind
    subsystem: str | None = None
    component_candidate: str | None = None
    disposition: LegacyDisposition = LegacyDisposition.KEEP
    review_depth: ReviewDepth = ReviewDepth.UNREVIEWED
    blob_sha: str | None = None
    canonical_destination: str | None = None
    parity_receipt: str | None = None
    migration_receipt: str | None = None
    history_provenance: str | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # Delegate path/SHA and fail-closed destructive semantics to the shared
        # legacy migration contract so the census cannot weaken migration law.
        self.as_legacy_path_record()

    def as_legacy_path_record(self) -> LegacyPathRecord:
        return LegacyPathRecord(
            path=self.path,
            disposition=self.disposition,
            review_depth=self.review_depth,
            blob_sha=self.blob_sha,
            canonical_destination=self.canonical_destination,
            parity_receipt=self.parity_receipt,
            migration_receipt=self.migration_receipt,
            history_provenance=self.history_provenance,
            notes=self.notes,
        )

    def to_state(self) -> dict[str, object]:
        return {
            "path": self.path,
            "kind": self.kind.value,
            "subsystem": self.subsystem,
            "component_candidate": self.component_candidate,
            **self.as_legacy_path_record().to_state(),
        }


@dataclass(frozen=True, slots=True)
class CensusCoverage:
    tracked_count: int
    censused_count: int
    missing_paths: tuple[str, ...]
    extra_paths: tuple[str, ...]

    @property
    def coverage_ratio(self) -> float:
        if self.tracked_count == 0:
            return 1.0 if self.censused_count == 0 else 0.0
        return self.censused_count / self.tracked_count

    @property
    def complete(self) -> bool:
        return not self.missing_paths and not self.extra_paths and self.tracked_count == self.censused_count


class RepositoryCensus:
    def __init__(self, records: Iterable[SourceCensusRecord] = ()) -> None:
        rows = tuple(records)
        self._records: dict[str, SourceCensusRecord] = {}
        for row in rows:
            if row.path in self._records:
                raise ValueError(f"duplicate census path: {row.path}")
            self._records[row.path] = row

    def records(self) -> tuple[SourceCensusRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))

    def get(self, path: str) -> SourceCensusRecord:
        try:
            return self._records[str(path)]
        except KeyError as exc:
            raise KeyError(f"uncensused repository path: {path}") from exc

    @property
    def digest(self) -> str:
        return canonical_digest([row.to_state() for row in self.records()])

    def coverage(self, tracked_paths: Iterable[str]) -> CensusCoverage:
        tracked = tuple(sorted({str(path) for path in tracked_paths}))
        tracked_set = set(tracked)
        census_set = set(self._records)
        missing = tuple(sorted(tracked_set - census_set))
        extra = tuple(sorted(census_set - tracked_set))
        return CensusCoverage(
            tracked_count=len(tracked),
            censused_count=len(tracked_set & census_set),
            missing_paths=missing,
            extra_paths=extra,
        )

    def require_complete(self, tracked_paths: Iterable[str]) -> CensusCoverage:
        report = self.coverage(tracked_paths)
        if not report.complete:
            raise PermissionError(
                "destructive refoundation phase is blocked until repository census coverage is exactly 100%; "
                f"missing={report.missing_paths}, extra={report.extra_paths}"
            )
        return report
