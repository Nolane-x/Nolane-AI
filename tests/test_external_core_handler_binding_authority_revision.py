from __future__ import annotations

import pytest

from cogcoder.organization.runtime import OrganizationRuntime


def _handler_a(_workspace, arguments):
    return {"handler": "a", "arguments": dict(arguments)}


def _handler_b(_workspace, arguments):
    return {"handler": "b", "arguments": dict(arguments)}


def test_handler_binding_authority_revision_is_per_tool_and_idempotent() -> None:
    runtime = OrganizationRuntime.first_generation()
    executor = runtime.execution.executor
    tool_a = "requirements-graph"
    tool_b = "acceptance-criteria-engine"

    assert executor.handler_binding_authority_revision(tool_a) == 0
    assert executor.handler_binding_authority_revision(tool_b) == 0

    executor.register_handler(tool_a, _handler_a)
    assert executor.handler_binding_authority_revision(tool_a) == 1
    assert executor.handler_binding_authority_revision(tool_b) == 0

    # Reasserting the exact same concrete handler is idempotent authority.
    executor.register_handler(tool_a, _handler_a)
    assert executor.handler_binding_authority_revision(tool_a) == 1

    # Binding an unrelated tool must not invalidate tool A's authority generation.
    executor.register_handler(tool_b, _handler_b)
    assert executor.handler_binding_authority_revision(tool_a) == 1
    assert executor.handler_binding_authority_revision(tool_b) == 1


def test_handler_binding_authority_revision_is_not_advanced_by_rejected_replacement() -> None:
    runtime = OrganizationRuntime.first_generation()
    executor = runtime.execution.executor
    tool_id = "requirements-graph"

    executor.register_handler(tool_id, _handler_a)
    revision = executor.handler_binding_authority_revision(tool_id)
    assert revision == 1

    with pytest.raises(ValueError, match="handler already registered|already registered"):
        executor.register_handler(tool_id, _handler_b)

    assert executor.handler_binding_authority_revision(tool_id) == revision
