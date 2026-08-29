"""Canonical temporary work-unit API over the explicit compatibility membrane."""

from nolane.compatibility.refoundation import (
    TemporaryWorkUnitBudget,
    TemporaryWorkUnitManifest,
    TemporaryWorkUnitRequest,
    TemporaryWorkUnitService,
)

COMPONENT_ID = "organization.temporary_work_units"
COMPONENT_VERSION = "0.0.0"

__all__ = (
    "TemporaryWorkUnitBudget",
    "TemporaryWorkUnitManifest",
    "TemporaryWorkUnitRequest",
    "TemporaryWorkUnitService",
)
