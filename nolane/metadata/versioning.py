from __future__ import annotations

import re
from dataclasses import dataclass


_VERSION_RE = re.compile(r"^0\.0\.(0|[1-9][0-9]*)$")


@dataclass(frozen=True, slots=True, order=True)
class ComponentVersion:
    """Refoundation Epoch-0 component-local revision.

    Component versions intentionally use only ``0.0.N`` during this epoch.
    They are software/external-cognition revisions and are deliberately
    orthogonal to neural versions, persisted state schemas, evaluation
    releases, historical R/Part labels, and Git commit SHAs.
    """

    major: int
    minor: int
    revision: int

    def __post_init__(self) -> None:
        if isinstance(self.major, bool) or isinstance(self.minor, bool) or isinstance(self.revision, bool):
            raise TypeError("component version fields must be integers")
        if (self.major, self.minor) != (0, 0):
            raise ValueError("Refoundation Epoch-0 component versions must use 0.0.N")
        if self.revision < 0:
            raise ValueError("component revision must be non-negative")

    @classmethod
    def parse(cls, value: str) -> "ComponentVersion":
        text = str(value).strip()
        match = _VERSION_RE.fullmatch(text)
        if match is None:
            raise ValueError("component version must have canonical form 0.0.N")
        return cls(0, 0, int(match.group(1)))

    def next_revision(self) -> "ComponentVersion":
        return type(self)(0, 0, self.revision + 1)

    def __str__(self) -> str:
        return f"0.0.{self.revision}"
