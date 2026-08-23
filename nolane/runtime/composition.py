"""Semantic runtime composition authority.

This is the public, Part-free architecture view of the Nolane runtime. The
implementation bridge remains internal to Refoundation during Epoch 0.
"""

from cogcoder.refoundation.runtime_composition import (
    SemanticRuntimeComposition,
    SemanticRuntimeNode,
    build_semantic_runtime_composition,
)


def build_runtime_composition() -> SemanticRuntimeComposition:
    return build_semantic_runtime_composition()


__all__ = (
    "SemanticRuntimeComposition",
    "SemanticRuntimeNode",
    "build_runtime_composition",
)
