"""Compatibility bridge for canonical task DAG primitives."""

from nolane.organization.tasks import TaskGraph, TaskRecord

MIGRATED_TO = "nolane.organization.tasks"

__all__ = ("TaskGraph", "TaskRecord", "MIGRATED_TO")
