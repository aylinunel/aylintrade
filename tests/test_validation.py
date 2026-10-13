from __future__ import annotations

import pytest

from aylintrade.validation import expanding_walk_forward


def test_walk_forward_folds_are_chronological_and_embargoed() -> None:
    folds = expanding_walk_forward(720, initial_train=360, validation=120, holdout=120, embargo=5)
    assert len(folds) == 1
    fold = folds[0]
    assert fold.train_start == 0
    assert fold.train_end + fold.embargo == fold.validation_start
    assert fold.validation_end + fold.embargo == fold.holdout_start
    assert fold.holdout_end <= 720


def test_walk_forward_rejects_invalid_windows() -> None:
    with pytest.raises(ValueError):
        expanding_walk_forward(100, initial_train=0, validation=10, holdout=10, embargo=1)
