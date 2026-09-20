from __future__ import annotations

import torch

from advantage_core import consensus_advantage_action


def test_consensus_advantage_requires_agreement() -> None:
    scores = torch.tensor([
        [0.0, 2.0, 1.0],
        [0.0, 1.0, 2.0],
        [0.0, 2.5, 1.5],
    ])
    action, info = consensus_advantage_action(
        scores,
        valid_actions=torch.tensor([True, True, True]),
        r11_action=0,
        threshold=0.1,
    )
    assert action == 0
    assert info["reason"] == "ensemble_disagreement"


def test_consensus_advantage_requires_margin() -> None:
    scores = torch.tensor([
        [1.0, 1.2, 0.0],
        [1.0, 1.3, 0.0],
        [1.0, 1.4, 0.0],
    ])
    action, info = consensus_advantage_action(
        scores,
        valid_actions=torch.tensor([True, True, True]),
        r11_action=0,
        threshold=0.25,
    )
    assert action == 0
    assert info["reason"] == "margin_below_threshold"


def test_consensus_advantage_accepts_shared_high_margin_alternative() -> None:
    scores = torch.tensor([
        [0.1, 1.1, -0.2],
        [0.2, 1.3, -0.4],
        [0.0, 1.0, -0.1],
    ])
    action, info = consensus_advantage_action(
        scores,
        valid_actions=torch.tensor([True, True, True]),
        r11_action=0,
        threshold=0.8,
    )
    assert action == 1
    assert info["override"] is True
    assert info["reason"] == "consensus_advantage"


def test_invalid_action_never_selected() -> None:
    scores = torch.tensor([
        [0.1, 10.0, 1.1],
        [0.2, 10.0, 1.3],
        [0.0, 10.0, 1.0],
    ])
    action, info = consensus_advantage_action(
        scores,
        valid_actions=torch.tensor([True, False, True]),
        r11_action=0,
        threshold=0.8,
    )
    assert action == 2
    assert info["override"] is True
