from __future__ import annotations

from typing import Sequence

from .r269_causal_basis_adapter import PortableExperience
from .r269_meta_learning_kernel import PublicTaskSignature
from .r269_scoped_promotion import ScopedPromotionRegistry
from .r269_transfer_runtime import (
    MetaLearningConfig,
    MetaLearningReceipt,
    PriorRegistry,
    run_meta_learning_episode,
)

_IMPORTED_VERIFIED_ADAPTER = 'causal_basis_v1'
_LEARNED_ADAPTER = 'verified_meta_episode_v1'


def _authorize_priors(
    priors: Sequence[PortableExperience],
    signature: PublicTaskSignature,
    promotion_registry: ScopedPromotionRegistry | None,
) -> tuple[PortableExperience, ...]:
    if not isinstance(signature, PublicTaskSignature):
        raise TypeError('signature must be PublicTaskSignature')
    if promotion_registry is not None and not isinstance(promotion_registry, ScopedPromotionRegistry):
        raise TypeError('promotion_registry must be ScopedPromotionRegistry')

    authorized: list[PortableExperience] = []
    active = None if promotion_registry is None else promotion_registry.active_for(signature.structural_class_digest)
    for portable in priors:
        if not isinstance(portable, PortableExperience):
            raise TypeError('priors must contain PortableExperience')
        if portable.adapter_type == _IMPORTED_VERIFIED_ADAPTER:
            authorized.append(portable)
            continue
        if portable.adapter_type != _LEARNED_ADAPTER:
            raise ValueError('unsupported portable adapter in governed runtime')
        if active is None:
            raise ValueError('verified meta prior requires active scoped promotion')
        if not active.promoted:
            raise ValueError('active scoped promotion must be an accepted promotion decision')
        if active.candidate_kind != 'portable_prior':
            raise ValueError('active scoped promotion is not a portable prior')
        if active.structural_class_digest != signature.structural_class_digest:
            raise ValueError('active promotion scope does not match target structural scope')
        if active.candidate_artifact_digest != portable.portable_digest:
            raise ValueError('active promotion artifact does not match learned prior')
        authorized.append(portable)
    return tuple(authorized)


def run_governed_meta_learning_episode(
    priors: Sequence[PortableExperience],
    signature: PublicTaskSignature,
    diagnostic_contexts,
    terminal_contexts,
    oracle,
    config: MetaLearningConfig,
    *,
    prior_registry: PriorRegistry | None = None,
    promotion_registry: ScopedPromotionRegistry | None = None,
) -> MetaLearningReceipt:
    """Run the release-authoritative R2.69 target path.

    Accepted R2.68 `causal_basis_v1` imports retain their verifier-backed source
    authority. Experiences learned by R2.69 itself (`verified_meta_episode_v1`)
    are not allowed to influence a later target until a scoped champion/
    challenger promotion is active for that exact public structural class.
    Rollback removes that authority immediately because authorization is
    resolved from the live promotion registry on every episode.
    """
    if not isinstance(config, MetaLearningConfig):
        raise TypeError('config must be MetaLearningConfig')
    authorized = _authorize_priors(priors, signature, promotion_registry)
    return run_meta_learning_episode(
        authorized,
        signature,
        diagnostic_contexts,
        terminal_contexts,
        oracle,
        config,
        registry=prior_registry,
    )


__all__ = ['run_governed_meta_learning_episode']
