"""Tests for environment variable registry, settings loading, validation, and redaction."""

import io
import logging
from pathlib import Path

import pytest

from backend.app.config.env import (
    REGISTRY_BY_NAME,
    ConfigError,
    SecretRedactionFilter,
    load_runtime_config,
    load_settings,
    presence,
    validate_enabled_groups,
    verify_registry_against_example,
)


def test_registry_matches_example() -> None:
    """Verify registry exactly matches the repository .env.example file."""
    verify_registry_against_example()


def test_registry_mismatch_detection(tmp_path: Path) -> None:
    """Verify that any mismatch between registry and template file raises ConfigError."""
    bad_template = tmp_path / "bad.env.example"
    bad_template.write_text("APP_ENV=\nUNKNOWN_VARIABLE=\n", encoding="utf-8")
    with pytest.raises(ConfigError) as exc_info:
        verify_registry_against_example(bad_template)
    err_msg = str(exc_info.value)
    assert "UNKNOWN_VARIABLE" in err_msg or "missing from registry" in err_msg


def test_core_defaults_and_presence(tmp_path: Path) -> None:
    """Verify APP_ENV and LOG_LEVEL default, presence reports them, and core group validates."""
    empty_env = tmp_path / "empty.env"
    empty_env.write_text("", encoding="utf-8")

    settings = load_settings(env_file=empty_env)
    assert settings.app_env == "production"
    assert settings.log_level == "INFO"

    pres = presence(settings)
    assert pres["core"]["APP_ENV"] is True
    assert pres["core"]["LOG_LEVEL"] is True

    # Core group requires nothing when enabled because both have defaults
    assert REGISTRY_BY_NAME["APP_ENV"].required_when_group_enabled is False
    assert REGISTRY_BY_NAME["LOG_LEVEL"].required_when_group_enabled is False
    validate_enabled_groups(settings, ["core"])


def test_load_settings_from_real_temp_file(tmp_path: Path) -> None:
    """Verify settings can be loaded from a real temporary .env file."""
    env_file = tmp_path / "custom.env"
    env_file.write_text(
        "APP_ENV=staging\n"
        "LOG_LEVEL=DEBUG\n"
        "NEBIUS_BASE_URL=https://api.example.com\n"
        "NEBIUS_API_KEY=test_secret_value_12345\n",
        encoding="utf-8",
    )

    settings = load_settings(env_file=env_file)
    assert settings.app_env == "staging"
    assert settings.log_level == "DEBUG"
    assert settings.nebius_base_url == "https://api.example.com"
    assert settings.nebius_api_key is not None
    assert settings.nebius_api_key.get_secret_value() == "test_secret_value_12345"


def test_process_env_overrides_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify process environment variables take precedence over file values."""
    env_file = tmp_path / "test.env"
    env_file.write_text(
        "APP_ENV=from_file\n" "NEBIUS_BASE_URL=https://file.example.com\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("APP_ENV", "from_process_env")
    monkeypatch.setenv("NEBIUS_BASE_URL", "https://override.example.com")

    settings = load_settings(env_file=env_file)
    assert settings.app_env == "from_process_env"
    assert settings.nebius_base_url == "https://override.example.com"


def test_absent_env_file_allowed(tmp_path: Path) -> None:
    """Verify loading from an absent .env file succeeds with defaults."""
    nonexistent = tmp_path / "does_not_exist.env"
    settings = load_settings(env_file=nonexistent)

    assert settings.app_env == "production"
    assert settings.log_level == "INFO"
    assert settings.nebius_api_key is None


def test_presence_mapping(tmp_path: Path) -> None:
    """Verify presence returns correct boolean mapping per group and variable."""
    env_file = tmp_path / "presence.env"
    env_file.write_text(
        "APP_ENV=production\n" "TAVILY_API_KEY=tavily_secret_key_123456\n",
        encoding="utf-8",
    )

    settings = load_settings(env_file=env_file)
    pres = presence(settings)

    assert pres["core"]["APP_ENV"] is True
    assert pres["search"]["TAVILY_API_KEY"] is True
    assert pres["llm"]["NEBIUS_API_KEY"] is False
    assert pres["llm"]["NEBIUS_BASE_URL"] is False


def test_validate_enabled_groups_reports_all_missing(tmp_path: Path) -> None:
    """Verify validation reports every missing variable for all enabled groups."""
    env_file = tmp_path / "incomplete.env"
    env_file.write_text("APP_ENV=production\n", encoding="utf-8")

    settings = load_settings(env_file=env_file)
    with pytest.raises(ConfigError) as exc_info:
        validate_enabled_groups(settings, ["llm", "search"])

    err_text = str(exc_info.value)
    assert "group 'llm'" in err_text
    assert "NEBIUS_API_KEY" in err_text
    assert "NEBIUS_BASE_URL" in err_text
    assert "group 'search'" in err_text
    assert "TAVILY_API_KEY" in err_text


def test_no_secret_values_in_exception_text(tmp_path: Path) -> None:
    """Verify that secret values never appear in exception error text."""
    secret_val = "super_sensitive_password_abcdef"
    env_file = tmp_path / "partial_secret.env"
    env_file.write_text(
        f"NEBIUS_API_KEY={secret_val}\n",
        encoding="utf-8",
    )

    settings = load_settings(env_file=env_file)
    with pytest.raises(ConfigError) as exc_info:
        validate_enabled_groups(settings, ["llm"])

    err_text = str(exc_info.value)
    assert secret_val not in err_text
    assert "NEBIUS_BASE_URL" in err_text


def test_secret_redaction_filter_basic(tmp_path: Path) -> None:
    """Verify that logging filter replaces sensitive strings of 6+ chars with ***."""
    secret_token = "secret_auth_token_987654321"
    env_file = tmp_path / "secrets.env"
    env_file.write_text(f"SUPABASE_ANON_KEY={secret_token}\n", encoding="utf-8")

    settings = load_settings(env_file=env_file)
    redaction_filter = SecretRedactionFilter.from_settings(settings)

    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(redaction_filter)

    logger = logging.getLogger("test_redaction_logger_basic")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False

    logger.info("Initializing client with key %s for authentication", secret_token)
    logger.info("Direct message mentioning secret_auth_token_987654321 here")

    log_output = log_stream.getvalue()
    assert secret_token not in log_output
    assert "***" in log_output


def test_redaction_exc_info_and_exception(tmp_path: Path) -> None:
    """Verify that exception tracebacks and logger.exception redact sensitive values."""
    secret_exc = "super_secret_exception_token_12345"
    env_file = tmp_path / "exc_secrets.env"
    env_file.write_text(f"NEBIUS_API_KEY={secret_exc}\n", encoding="utf-8")

    settings = load_settings(env_file=env_file)
    redaction_filter = SecretRedactionFilter.from_settings(settings)

    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter("%(message)s\n%(exc_text)s"))
    handler.addFilter(redaction_filter)

    logger = logging.getLogger("test_redaction_exc_logger")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False

    # Test exc_info=True
    try:
        raise ValueError(f"Connection failed using {secret_exc}")
    except ValueError:
        logger.error("Caught error during call", exc_info=True)

    # Test logger.exception
    try:
        raise RuntimeError(f"Runtime error with {secret_exc}")
    except RuntimeError:
        logger.exception("Exception occurred in pipeline")

    output = log_stream.getvalue()
    assert secret_exc not in output
    assert "***" in output


def test_redaction_stack_info(tmp_path: Path) -> None:
    """Verify that stack_info output is redacted when present."""
    secret_stack = "super_secret_stack_token_12345"
    filter_obj = SecretRedactionFilter(secrets={secret_stack})

    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter("%(message)s\n%(stack_info)s"))
    handler.addFilter(filter_obj)

    logger = logging.getLogger("test_redaction_stack_logger")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False

    logger.info("Message mentioning %s", secret_stack, stack_info=True)

    output = log_stream.getvalue()
    assert secret_stack not in output
    assert "***" in output


def test_redaction_tuple_dict_and_exception_args() -> None:
    """Verify that tuple args, dict args, and exception objects as args are redacted."""
    secret_arg = "secret_argument_val_9999"
    filter_obj = SecretRedactionFilter(secrets={secret_arg})

    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(filter_obj)

    logger = logging.getLogger("test_redaction_args_logger")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False

    # Tuple args
    logger.info("Tuple args: %s and %s", "regular", secret_arg)
    # Dict args
    logger.info("Dict arg: %(token)s", {"token": secret_arg})
    # Exception object passed as arg
    exc_obj = ValueError(f"Inner error with {secret_arg}")
    logger.error("Exception arg: %s", exc_obj)

    output = log_stream.getvalue()
    assert secret_arg not in output
    assert "***" in output


def test_short_secret_not_redacted() -> None:
    """Rule: Secrets must be at least 6 characters or they are not redacted in logs.

    Verify that a secret shorter than 6 characters is intentionally excluded from redaction.
    """
    short_secret = "short"  # 5 characters
    filter_obj = SecretRedactionFilter(secrets={short_secret})

    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(filter_obj)

    logger = logging.getLogger("test_short_secret_logger")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False

    logger.info("Short secret is: %s", short_secret)

    output = log_stream.getvalue()
    # Shorter than 6 characters: not in self.secrets, remains unredacted
    assert short_secret in output


def test_runtime_yaml_validation_cases(tmp_path: Path) -> None:
    """Verify strict validation and ConfigError naming the file for runtime.yaml failure cases."""
    # 1. Missing file
    missing_file = tmp_path / "nonexistent.yaml"
    with pytest.raises(ConfigError) as exc_info:
        load_runtime_config(missing_file)
    assert str(missing_file) in str(exc_info.value)
    assert "not found" in str(exc_info.value)

    # 2. Empty file
    empty_file = tmp_path / "empty.yaml"
    empty_file.write_text("", encoding="utf-8")
    with pytest.raises(ConfigError) as exc_info:
        load_runtime_config(empty_file)
    assert str(empty_file) in str(exc_info.value)
    assert "empty" in str(exc_info.value)

    # 3. Missing enabled_groups key
    no_key_file = tmp_path / "no_key.yaml"
    no_key_file.write_text("other_field: true\n", encoding="utf-8")
    with pytest.raises(ConfigError) as exc_info:
        load_runtime_config(no_key_file)
    assert str(no_key_file) in str(exc_info.value)
    assert "missing required key 'enabled_groups'" in str(exc_info.value)

    # 4. Non-list enabled_groups
    non_list_file = tmp_path / "non_list.yaml"
    non_list_file.write_text("enabled_groups: 'llm'\n", encoding="utf-8")
    with pytest.raises(ConfigError) as exc_info:
        load_runtime_config(non_list_file)
    assert str(non_list_file) in str(exc_info.value)
    assert "must be a list" in str(exc_info.value)

    # 5. Non-string item in enabled_groups
    non_str_file = tmp_path / "non_str.yaml"
    non_str_file.write_text("enabled_groups:\n  - 123\n", encoding="utf-8")
    with pytest.raises(ConfigError) as exc_info:
        load_runtime_config(non_str_file)
    assert str(non_str_file) in str(exc_info.value)
    assert "all items in 'enabled_groups' must be strings" in str(exc_info.value)

    # 6. Valid empty list
    valid_file = tmp_path / "valid.yaml"
    valid_file.write_text("enabled_groups: []\n", encoding="utf-8")
    assert load_runtime_config(valid_file) == []
