"""FinInsight configuration loader, parameter resolver, and window validator."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from backend.app.config.env import ConfigError, get_repo_root
from backend.app.config.models import (
    AllConfig,
    EpisodesConfig,
    LexiconConfig,
    ParametersConfig,
    PlansConfig,
    ThresholdsConfig,
    UniverseConfig,
)


class ParameterError(ValueError):
    """Raised when a parameter override violates bounds, mutability, or schema rules."""

    def __init__(
        self,
        field: str,
        value: Any,
        allowed_range: tuple[float | int | None, float | int | None] | str,
        reason: str,
    ) -> None:
        self.field = field
        self.value = value
        self.allowed_range = allowed_range
        self.reason = reason
        super().__init__(
            f"Parameter error for '{field}': value={value!r}, allowed={allowed_range}. "
            f"Reason: {reason}"
        )


def _load_yaml_file(file_path: Path) -> dict[str, Any]:
    """Load a YAML file, rejecting missing, non-existent, or empty files."""
    if not file_path.is_file():
        raise ConfigError(f"Configuration file not found: {file_path.name}")

    content = file_path.read_text(encoding="utf-8")
    if not content.strip():
        raise ConfigError(f"Configuration file is empty: {file_path.name}")

    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML parsing error in {file_path.name}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(
            f"Root of configuration file {file_path.name} must be a dictionary/mapping"
        )

    return data


def _format_validation_error(exc: ValidationError, filename: str) -> ConfigError:
    """Format a Pydantic ValidationError into a ConfigError naming the file and field."""
    errors = exc.errors()
    if errors:
        err = errors[0]
        loc_str = ".".join(str(loc) for loc in err["loc"]) if err["loc"] else "(root)"
        msg = err["msg"]
        return ConfigError(
            f"Configuration validation failed in {filename} at field '{loc_str}': {msg}"
        )
    return ConfigError(f"Configuration validation failed in {filename}: {exc}")


def _resolve_config_dir(config_dir: Path | None = None) -> Path:
    """Resolve configuration directory, falling back to repository root config."""
    if config_dir is not None:
        if config_dir.is_dir():
            return config_dir
        repo_candidate = get_repo_root() / config_dir
        if repo_candidate.is_dir():
            return repo_candidate
        raise ConfigError(f"Configuration directory does not exist: {config_dir}")

    local_cfg = Path("config")
    if local_cfg.is_dir():
        return local_cfg
    repo_cfg = get_repo_root() / "config"
    if repo_cfg.is_dir():
        return repo_cfg
    raise ConfigError(f"Configuration directory does not exist: {local_cfg}")


def load_config_file(
    file_path: Path,
    model_cls: type[Any],
) -> Any:
    """Load and validate a single configuration YAML file."""
    if not file_path.is_file() and not file_path.is_absolute():
        repo_file = get_repo_root() / file_path
        if repo_file.is_file():
            file_path = repo_file
    data = _load_yaml_file(file_path)
    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        raise _format_validation_error(exc, file_path.name) from exc


def load_all_config(config_dir: Path | None = None) -> AllConfig:
    """Load and validate all configuration files from the config directory."""
    config_dir = _resolve_config_dir(config_dir)

    params = load_config_file(config_dir / "parameters.yaml", ParametersConfig)
    thresholds = load_config_file(config_dir / "thresholds.yaml", ThresholdsConfig)
    plans = load_config_file(config_dir / "plans.yaml", PlansConfig)
    universe = load_config_file(config_dir / "universe.yaml", UniverseConfig)
    episodes = load_config_file(config_dir / "episodes.yaml", EpisodesConfig)
    lexicon = load_config_file(config_dir / "lexicon.yaml", LexiconConfig)

    return AllConfig(
        parameters=params,
        thresholds=thresholds,
        plans=plans,
        universe=universe,
        episodes=episodes,
        lexicon=lexicon,
    )


def resolve_parameters(
    overrides: dict[str, Any] | None = None,
    base_params: ParametersConfig | None = None,
    config_dir: Path | None = None,
) -> dict[str, Any]:
    """Resolve active parameter values applying overrides onto base configuration.

    Raises ParameterError for:
    - unknown parameter name
    - parameter not allowed to be overridden
    - override value out of bounds
    - wrong type (e.g. a bool supplied for int or float)
    """
    if base_params is None:
        config_dir = _resolve_config_dir(config_dir)
        base_params = load_config_file(config_dir / "parameters.yaml", ParametersConfig)

    result: dict[str, Any] = {}
    # Populate defaults
    for name, entry in base_params.parameters.items():
        result[name] = entry.default

    if not overrides:
        return result

    for key, value in overrides.items():
        if key not in base_params.parameters:
            raise ParameterError(
                field=key,
                value=value,
                allowed_range="known parameter",
                reason=f"Unknown parameter '{key}'",
            )

        entry = base_params.parameters[key]

        if not entry.override_allowed:
            raise ParameterError(
                field=key,
                value=value,
                allowed_range=f"override_allowed={entry.override_allowed}",
                reason=f"Parameter '{key}' cannot be overridden",
            )

        # Type checking: bool is a subclass of int in Python, so explicitly check bool first
        if entry.type == "int":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ParameterError(
                    field=key,
                    value=value,
                    allowed_range="int",
                    reason=f"Parameter '{key}' must be of type int, got {type(value).__name__}",
                )
        elif entry.type == "float":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ParameterError(
                    field=key,
                    value=value,
                    allowed_range="float",
                    reason=f"Parameter '{key}' must be of type float, got {type(value).__name__}",
                )
            value = float(value)
        elif entry.type == "bool":
            if not isinstance(value, bool):
                raise ParameterError(
                    field=key,
                    value=value,
                    allowed_range="bool",
                    reason=f"Parameter '{key}' must be of type bool, got {type(value).__name__}",
                )
        elif entry.type == "str":
            if not isinstance(value, str):
                raise ParameterError(
                    field=key,
                    value=value,
                    allowed_range="str",
                    reason=f"Parameter '{key}' must be of type str, got {type(value).__name__}",
                )

        # Bounds checking
        if entry.type in ("int", "float") and entry.min is not None and entry.max is not None:
            if not (entry.min <= value <= entry.max):
                raise ParameterError(
                    field=key,
                    value=value,
                    allowed_range=(entry.min, entry.max),
                    reason=f"Value {value} for '{key}' is out of bounds [{entry.min}, {entry.max}]",
                )

        result[key] = value

    return result


def validate_window_consistency(params: dict[str, Any], history_length: int) -> bool:
    """Verify that baseline B + gap G + current C fits within available history length.

    Formula: B + G + C <= history_length
    """
    baseline = params.get("B")
    gap = params.get("G")
    current = params.get("C")

    if baseline is None or gap is None or current is None:
        raise ValueError("Missing window parameters: 'B', 'G', and 'C' are required")

    total_required = int(baseline) + int(gap) + int(current)
    if total_required > history_length:
        raise ValueError(
            f"Window consistency failure: B ({baseline}) + G ({gap}) + C ({current}) = "
            f"{total_required} exceeds available history length {history_length}"
        )

    return True


def get_risk_free_rate(
    params_config: ParametersConfig | None = None,
    config_dir: Path | None = None,
) -> float:
    """Retrieve the configured risk-free rate value converted explicitly to decimal.

    Raises ParameterError if the configured risk-free rate is null, or if unit is
    missing or unknown.
    """
    if params_config is None:
        config_dir = _resolve_config_dir(config_dir)
        params_config = load_config_file(config_dir / "parameters.yaml", ParametersConfig)

    rf = params_config.risk_free
    if rf.value is None:
        raise ParameterError(
            field="risk_free",
            value=rf.value,
            allowed_range="non-null float",
            reason=f"Risk-free rate is null with status '{rf.status}'",
        )
    if not rf.unit:
        raise ParameterError(
            field="unit",
            value=rf.unit,
            allowed_range="['percent per annum', 'decimal per annum']",
            reason="Risk-free rate unit is missing",
        )
    if rf.unit == "percent per annum":
        return round(float(rf.value) / 100.0, 10)
    elif rf.unit == "decimal per annum":
        return float(rf.value)
    else:
        raise ParameterError(
            field="unit",
            value=rf.unit,
            allowed_range="['percent per annum', 'decimal per annum']",
            reason=f"Unknown risk-free rate unit '{rf.unit}'",
        )


def get_risk_free_rate_parameters(
    params_config: ParametersConfig | None = None,
    config_dir: Path | None = None,
) -> dict[str, Any]:
    """Retrieve recorded parameters for the risk-free rate (value, unit, source, as_of).

    Raises ParameterError if the configured risk-free rate is null or unit is missing/unknown.
    """
    if params_config is None:
        config_dir = _resolve_config_dir(config_dir)
        params_config = load_config_file(config_dir / "parameters.yaml", ParametersConfig)

    rf = params_config.risk_free
    decimal_rate = get_risk_free_rate(params_config, config_dir)
    return {
        "value": rf.value,
        "unit": rf.unit,
        "source": rf.source,
        "as_of": rf.as_of,
        "decimal_rate": decimal_rate,
    }
