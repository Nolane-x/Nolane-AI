import torch

from cogcoder.r27_codeworld_controller import (
    ACTION_KINDS,
    CodeWorldController,
    CodeWorldControllerConfig,
    controller_parameter_count,
)


def test_controller_is_compact_and_scores_variable_action_sets():
    cfg = CodeWorldControllerConfig()
    model = CodeWorldController(cfg)
    count = controller_parameter_count(model)
    assert 200_000 <= count < 1_000_000

    batch, actions, history = 3, 7, 5
    out = model(
        state_features=torch.randn(batch, cfg.state_dim),
        action_features=torch.randn(batch, actions, cfg.action_feature_dim),
        history_features=torch.randn(batch, history, cfg.history_feature_dim),
        language_ids=torch.tensor([0, 3, 7]),
        task_type_ids=torch.tensor([0, 2, 5]),
        action_mask=torch.tensor(
            [[1, 1, 1, 1, 1, 1, 1], [1, 1, 0, 1, 1, 0, 1], [1, 0, 0, 1, 1, 1, 1]],
            dtype=torch.bool,
        ),
    )
    assert out.action_logits.shape == (batch, actions)
    assert out.stop_logit.shape == (batch,)
    assert out.success_logit.shape == (batch,)
    assert torch.isneginf(out.action_logits[1, 2])
    assert torch.isneginf(out.action_logits[1, 5])
    assert len(ACTION_KINDS) == 12


def test_controller_rejects_malformed_shapes():
    cfg = CodeWorldControllerConfig()
    model = CodeWorldController(cfg)
    with torch.no_grad():
        try:
            model(
                state_features=torch.randn(2, cfg.state_dim + 1),
                action_features=torch.randn(2, 4, cfg.action_feature_dim),
                history_features=torch.randn(2, 3, cfg.history_feature_dim),
                language_ids=torch.tensor([0, 1]),
                task_type_ids=torch.tensor([0, 1]),
                action_mask=torch.ones(2, 4, dtype=torch.bool),
            )
        except ValueError as exc:
            assert "state_features" in str(exc)
        else:
            raise AssertionError("expected malformed state_features to be rejected")
