"""Semantic runtime composition authority."""

from nolane.metadata.runtime_composition import (
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
