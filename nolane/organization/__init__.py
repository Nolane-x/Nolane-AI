"""Canonical organization-layer namespace.

Use :func:`build_first_generation_runtime` for the manifest-driven fixed
67-identity bootstrap. Legacy class symbols remain available through the
compatibility facade modules during Epoch 0.
"""

from .runtime import OrganizationRuntime, build_first_generation_runtime

__all__ = ("OrganizationRuntime", "build_first_generation_runtime")
