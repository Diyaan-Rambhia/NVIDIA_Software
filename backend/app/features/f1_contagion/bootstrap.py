"""Moving-block bootstrap implementation for Feature 1 Contagion Detector.

Resamples baseline time series with replacement using moving overlapping blocks
to preserve short-term temporal dependence per PROJECT.md §5.6.
"""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from backend.app.config.env import get_repo_root
from backend.app.config.loader import ParameterError, load_config_file
from backend.app.config.models import ParameterEntry, ParametersConfig

_DEFAULT_CONFIG_PATH = get_repo_root() / "config" / "parameters.yaml"


@dataclass(frozen=True)
class BootstrapResult:
    """Immutable result container capturing bootstrap replicates and provenance seed."""

    replications: np.ndarray
    seed: int
    block_len: int
    n_boot: int
    alpha: float


def get_parameters_config(config_path: Path | None = None) -> ParametersConfig:
    """Load parameter specifications from parameters.yaml without hardcoded bounds."""
    target_path = config_path if config_path is not None else _DEFAULT_CONFIG_PATH
    return load_config_file(target_path, ParametersConfig)


def get_parameter_def(name: str, config: ParametersConfig | None = None) -> ParameterEntry:
    """Retrieve parameter definition from configuration."""
    cfg = config if config is not None else get_parameters_config()
    if name not in cfg.parameters:
        raise ParameterError(
            field=name,
            value=name,
            allowed_range="known parameter",
            reason=f"Parameter '{name}' not found in configuration",
        )
    return cfg.parameters[name]


def validate_parameter_bounds(
    name: str,
    value: int | float,
    config: ParametersConfig | None = None,
) -> None:
    """Validate numeric parameter value against its configuration bounds."""
    entry = get_parameter_def(name, config)
    if entry.min is not None and entry.max is not None:
        if not (entry.min <= value <= entry.max):
            raise ParameterError(
                field=name,
                value=value,
                allowed_range=(entry.min, entry.max),
                reason=(
                    f"Parameter '{name}' value {value} is outside configured bounds "
                    f"[{entry.min}, {entry.max}]"
                ),
            )


def moving_block_bootstrap(
    data: np.ndarray,
    target_len: int,
    seed: int,
    block_len: int | None = None,
    n_boot: int | None = None,
    alpha: float | None = None,
    config: ParametersConfig | None = None,
    statistic_fn: Callable[[np.ndarray], Any] | None = None,
) -> BootstrapResult:
    """Resample observations using moving overlapping blocks.

    Draws blocks of length block_len with replacement, concatenates them,
    and truncates the final block to match target_len exactly.
    """
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ParameterError(
            field="seed",
            value=seed,
            allowed_range="int",
            reason=f"Seed must be an integer, got {type(seed).__name__}",
        )

    if not isinstance(data, np.ndarray):
        data = np.asarray(data, dtype=float)

    if data.size == 0:
        raise ParameterError(
            field="data",
            value="empty array",
            allowed_range="non-empty array",
            reason="Input data array cannot be empty",
        )

    if not np.all(np.isfinite(data)):
        raise ParameterError(
            field="data",
            value="non-finite elements",
            allowed_range="finite numbers",
            reason="Input data contains NaN or infinite values",
        )

    if not isinstance(target_len, int) or isinstance(target_len, bool) or target_len <= 0:
        raise ParameterError(
            field="target_len",
            value=target_len,
            allowed_range="positive int",
            reason="Target length must be a strictly positive integer",
        )

    if block_len is None:
        block_len = int(get_parameter_def("block_len", config).default)
    validate_parameter_bounds("block_len", block_len, config)

    n_obs = data.shape[0]
    if n_obs < block_len:
        raise ParameterError(
            field="data",
            value=n_obs,
            allowed_range=f">= block_len ({block_len})",
            reason=(
                f"Available observations {n_obs} are fewer than required block length {block_len}"
            ),
        )

    if n_boot is None:
        n_boot = int(get_parameter_def("n_boot", config).default)
    validate_parameter_bounds("n_boot", n_boot, config)

    if alpha is None:
        alpha = float(get_parameter_def("alpha", config).default)
    validate_parameter_bounds("alpha", alpha, config)

    # Number of possible overlapping contiguous blocks
    num_blocks_available = n_obs - block_len + 1
    blocks_needed = math.ceil(target_len / block_len)

    rng = np.random.default_rng(seed)

    reps: list[Any] = []
    for _ in range(n_boot):
        # Sample starting indices for blocks
        start_indices = rng.integers(0, num_blocks_available, size=blocks_needed)
        sampled_blocks = [data[idx : idx + block_len] for idx in start_indices]
        concatenated = np.concatenate(sampled_blocks, axis=0)
        resampled_series = concatenated[:target_len]

        if statistic_fn is not None:
            reps.append(statistic_fn(resampled_series))
        else:
            reps.append(resampled_series)

    replications_arr = np.asarray(reps)
    return BootstrapResult(
        replications=replications_arr,
        seed=seed,
        block_len=block_len,
        n_boot=n_boot,
        alpha=alpha,
    )
