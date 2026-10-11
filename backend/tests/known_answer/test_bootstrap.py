"""Known-answer and property tests for moving-block bootstrap.

Tests determinism with identical seeds, variation across distinct seeds,
provenance seed preservation, and strict error handling on invalid inputs.
"""

import numpy as np
import pytest

from backend.app.config.loader import ParameterError
from backend.app.features.f1_contagion.bootstrap import (
    BootstrapResult,
    moving_block_bootstrap,
)


def test_bootstrap_determinism_same_seed() -> None:
    """Verify that identical seeds produce bitwise-identical bootstrap distributions."""
    rng = np.random.default_rng(101)
    data = rng.normal(0.0, 0.02, size=(50, 2))
    target_len = 20
    seed = 42

    res1 = moving_block_bootstrap(data, target_len=target_len, seed=seed, block_len=10, n_boot=200)
    res2 = moving_block_bootstrap(data, target_len=target_len, seed=seed, block_len=10, n_boot=200)

    assert isinstance(res1, BootstrapResult)
    assert res1.seed == seed
    assert res2.seed == seed
    assert np.array_equal(res1.replications, res2.replications)


def test_bootstrap_different_seeds_produce_different_output() -> None:
    """Verify that different seeds produce distinct resampled series."""
    rng = np.random.default_rng(202)
    data = rng.normal(0.0, 0.02, size=(60, 2))
    target_len = 20

    res1 = moving_block_bootstrap(data, target_len=target_len, seed=123, block_len=10, n_boot=200)
    res2 = moving_block_bootstrap(data, target_len=target_len, seed=456, block_len=10, n_boot=200)

    assert res1.seed == 123
    assert res2.seed == 456
    assert not np.array_equal(res1.replications, res2.replications)


def test_bootstrap_seed_present_in_result() -> None:
    """Verify that the result object preserves seed, block_len, n_boot, and alpha."""
    data = np.arange(100.0).reshape(50, 2)
    res = moving_block_bootstrap(
        data, target_len=15, seed=999, block_len=10, n_boot=200, alpha=0.05
    )

    assert res.seed == 999
    assert res.block_len == 10
    assert res.n_boot == 200
    assert res.alpha == 0.05
    assert res.replications.shape == (200, 15, 2)


def test_bootstrap_truncation_final_block() -> None:
    """Verify truncation when target_len is not a multiple of block_len."""
    data = np.arange(50.0)
    target_len = 25  # block_len=10 -> needs 3 blocks (30 items), truncated to 25
    res = moving_block_bootstrap(data, target_len=target_len, seed=7, block_len=10, n_boot=200)

    assert res.replications.shape == (200, 25)


def test_bootstrap_with_statistic_function() -> None:
    """Verify evaluation of statistic function across resampled replications."""
    data = np.arange(40.0)
    res = moving_block_bootstrap(
        data,
        target_len=20,
        seed=55,
        block_len=10,
        n_boot=200,
        statistic_fn=lambda arr: float(np.mean(arr)),
    )

    assert res.replications.shape == (200,)
    assert all(isinstance(val, (float, np.floating)) for val in res.replications)


def test_bootstrap_empty_data_raises() -> None:
    """Empty data array must raise ParameterError."""
    with pytest.raises(ParameterError, match="cannot be empty"):
        moving_block_bootstrap(np.array([]), target_len=10, seed=1)


def test_bootstrap_non_finite_data_raises() -> None:
    """Data containing NaN or infinite values must raise ParameterError."""
    bad_data = np.array([1.0, 2.0, float("nan"), 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    with pytest.raises(ParameterError, match="NaN or infinite"):
        moving_block_bootstrap(bad_data, target_len=5, seed=1, block_len=2)


def test_bootstrap_fewer_obs_than_block_len_raises() -> None:
    """Having fewer observations than block_len must raise ParameterError."""
    short_data = np.array([1.0, 2.0, 3.0])
    with pytest.raises(ParameterError, match="fewer than required block length"):
        moving_block_bootstrap(short_data, target_len=5, seed=1, block_len=10)


def test_bootstrap_invalid_seed_raises() -> None:
    """Non-integer or boolean seed must raise ParameterError."""
    data = np.arange(30.0)
    with pytest.raises(ParameterError, match="Seed must be an integer"):
        moving_block_bootstrap(data, target_len=10, seed=True)  # type: ignore[arg-type]

    with pytest.raises(ParameterError, match="Seed must be an integer"):
        moving_block_bootstrap(data, target_len=10, seed=1.5)  # type: ignore[arg-type]


def test_bootstrap_invalid_target_len_raises() -> None:
    """Non-positive target length must raise ParameterError."""
    data = np.arange(30.0)
    with pytest.raises(ParameterError, match="strictly positive"):
        moving_block_bootstrap(data, target_len=0, seed=1)


def test_bootstrap_bounds_enforcement() -> None:
    """Parameters outside config bounds must raise ParameterError."""
    data = np.arange(100.0)

    # block_len out of bounds (min 2, max 60)
    with pytest.raises(ParameterError, match="outside configured bounds"):
        moving_block_bootstrap(data, target_len=10, seed=1, block_len=1)

    with pytest.raises(ParameterError, match="outside configured bounds"):
        moving_block_bootstrap(data, target_len=10, seed=1, block_len=70)

    # n_boot out of bounds (min 200, max 5000)
    with pytest.raises(ParameterError, match="outside configured bounds"):
        moving_block_bootstrap(data, target_len=10, seed=1, block_len=10, n_boot=100)
