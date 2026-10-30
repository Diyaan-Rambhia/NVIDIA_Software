"""Environment variable registry, configuration loading, validation, and redaction."""

import logging
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(Exception):
    """Raised when configuration validation fails."""


@dataclass(frozen=True)
class EnvVarDef:
    """Definition of a registered environment variable."""

    name: str
    group: str
    secret: bool
    required_when_group_enabled: bool = True


# Registry containing all supported environment variables.
# Single source of truth matching .env.example exactly.
REGISTRY: tuple[EnvVarDef, ...] = (
    # Core group (APP_ENV and LOG_LEVEL have default values,
    # so required_when_group_enabled is False)
    EnvVarDef("APP_ENV", "core", secret=False, required_when_group_enabled=False),
    EnvVarDef("LOG_LEVEL", "core", secret=False, required_when_group_enabled=False),
    # LLM group
    EnvVarDef("NEBIUS_API_KEY", "llm", secret=True, required_when_group_enabled=True),
    EnvVarDef("NEBIUS_BASE_URL", "llm", secret=False, required_when_group_enabled=True),
    # Search group
    EnvVarDef("TAVILY_API_KEY", "search", secret=True, required_when_group_enabled=True),
    # Supabase group
    EnvVarDef("SUPABASE_URL", "supabase", secret=False, required_when_group_enabled=True),
    EnvVarDef("SUPABASE_ANON_KEY", "supabase", secret=True, required_when_group_enabled=True),
    EnvVarDef(
        "SUPABASE_SERVICE_ROLE_KEY", "supabase", secret=True, required_when_group_enabled=True
    ),
    EnvVarDef("SUPABASE_JWT_SECRET", "supabase", secret=True, required_when_group_enabled=True),
    EnvVarDef("DATABASE_URL", "supabase", secret=True, required_when_group_enabled=True),
    EnvVarDef("SUPABASE_PASSWORD", "supabase", secret=True, required_when_group_enabled=True),
    # Market data group
    EnvVarDef("PRICE_API_KEY", "market_data", secret=True, required_when_group_enabled=True),
    EnvVarDef("FRED_API_KEY", "market_data", secret=True, required_when_group_enabled=True),
    # Filings group
    EnvVarDef("HTTP_USER_AGENT", "filings", secret=False, required_when_group_enabled=True),
    # Payments group
    EnvVarDef("PAYMENT_KEY_ID", "payments", secret=True, required_when_group_enabled=True),
    EnvVarDef("PAYMENT_KEY_SECRET", "payments", secret=True, required_when_group_enabled=True),
    EnvVarDef("PAYMENT_WEBHOOK_SECRET", "payments", secret=True, required_when_group_enabled=True),
    # OAuth group
    EnvVarDef("GOOGLE_OAUTH_CLIENT_ID", "oauth", secret=False, required_when_group_enabled=True),
    EnvVarDef("GOOGLE_OAUTH_CLIENT_SECRET", "oauth", secret=True, required_when_group_enabled=True),
    # Accounts seed group
    EnvVarDef("JUDGE_PASSWORD", "accounts_seed", secret=True, required_when_group_enabled=True),
    EnvVarDef(
        "DEMO_RETAIL_PASSWORD", "accounts_seed", secret=True, required_when_group_enabled=True
    ),
    EnvVarDef(
        "DEMO_INSTITUTIONAL_PASSWORD",
        "accounts_seed",
        secret=True,
        required_when_group_enabled=True,
    ),
    # Budget group
    EnvVarDef("DAILY_LLM_BUDGET_USD", "budget", secret=False, required_when_group_enabled=True),
    EnvVarDef(
        "TEST_DAILY_LLM_BUDGET_USD", "budget", secret=False, required_when_group_enabled=True
    ),
    # Optional group
    EnvVarDef("PINECONE_API_KEY", "optional", secret=True, required_when_group_enabled=False),
    EnvVarDef("SMTP_HOST", "optional", secret=False, required_when_group_enabled=False),
    EnvVarDef("SMTP_USER", "optional", secret=False, required_when_group_enabled=False),
    EnvVarDef("SMTP_PASSWORD", "optional", secret=True, required_when_group_enabled=False),
)

REGISTRY_BY_NAME: dict[str, EnvVarDef] = {v.name: v for v in REGISTRY}
REGISTRY_BY_GROUP: dict[str, list[EnvVarDef]] = {}
for _var in REGISTRY:
    REGISTRY_BY_GROUP.setdefault(_var.group, []).append(_var)


def get_repo_root() -> Path:
    """Return the absolute path to the repository root directory."""
    return Path(__file__).resolve().parent.parent.parent.parent


def verify_registry_against_example(example_path: Optional[Path] = None) -> None:
    """Verify registry covers exactly the variables defined in .env.example.

    When running in a managed cloud environment (RENDER=true or CI=true),
    the .env.example file may not be present in the deployment bundle.
    In that case the check is skipped because all required variables are
    supplied directly via the platform's environment variable system.
    """
    import os as _os
    target_path = example_path if example_path is not None else get_repo_root() / ".env.example"
    if not target_path.exists():
        if _os.environ.get("RENDER") or _os.environ.get("CI"):
            return
        raise ConfigError(f"Environment template file not found: {target_path}")

    lines = target_path.read_text(encoding="utf-8").splitlines()
    example_vars = {
        line.split("=")[0].strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    }

    registry_vars = set(REGISTRY_BY_NAME.keys())
    missing_in_registry = example_vars - registry_vars
    extra_in_registry = registry_vars - example_vars

    if missing_in_registry or extra_in_registry:
        errors: list[str] = []
        if missing_in_registry:
            errors.append(
                f"Variables in .env.example missing from registry: {sorted(missing_in_registry)}"
            )
        if extra_in_registry:
            errors.append(
                f"Variables in registry missing from .env.example: {sorted(extra_in_registry)}"
            )
        raise ConfigError("; ".join(errors))


class Settings(BaseSettings):
    """Application settings loaded from environment and optional .env file."""

    # Core group
    app_env: str = "production"
    log_level: str = "INFO"

    # LLM group
    nebius_api_key: Optional[SecretStr] = None
    nebius_base_url: Optional[str] = None

    # Search group
    tavily_api_key: Optional[SecretStr] = None

    # Supabase group
    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[SecretStr] = None
    supabase_service_role_key: Optional[SecretStr] = None
    supabase_jwt_secret: Optional[SecretStr] = None
    database_url: Optional[SecretStr] = None
    supabase_password: Optional[SecretStr] = None

    # Market data group
    price_api_key: Optional[SecretStr] = None
    fred_api_key: Optional[SecretStr] = None

    # Filings group
    http_user_agent: Optional[str] = None

    # Payments group
    payment_key_id: Optional[SecretStr] = None
    payment_key_secret: Optional[SecretStr] = None
    payment_webhook_secret: Optional[SecretStr] = None

    # OAuth group
    google_oauth_client_id: Optional[str] = None
    google_oauth_client_secret: Optional[SecretStr] = None

    # Accounts seed group
    judge_password: Optional[SecretStr] = None
    demo_retail_password: Optional[SecretStr] = None
    demo_institutional_password: Optional[SecretStr] = None

    # Budget group
    daily_llm_budget_usd: Optional[str] = None
    test_daily_llm_budget_usd: Optional[str] = None

    # Optional group
    pinecone_api_key: Optional[SecretStr] = None
    smtp_host: Optional[str] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[SecretStr] = None

    model_config = SettingsConfigDict(
        extra="ignore",
        case_sensitive=False,
    )

    def __init__(
        self,
        _env_file: Optional[Path | str] = None,
        **values: Any,
    ) -> None:
        super().__init__(_env_file=_env_file, **values)

    def get_var_value(self, name: str) -> Optional[str]:
        """Return raw string value for variable name (exposing secret string for internal use)."""
        attr_name = name.lower()
        if not hasattr(self, attr_name):
            return None
        val: Any = getattr(self, attr_name)
        if val is None:
            return None
        if isinstance(val, SecretStr):
            return val.get_secret_value()
        return str(val)


def load_settings(env_file: Optional[Path | str] = None) -> Settings:
    """Load settings from an explicit path or repository root .env file if it exists."""
    verify_registry_against_example()
    if env_file is not None:
        target = Path(env_file)
        if target.exists():
            return Settings(_env_file=target)
        return Settings(_env_file=None)

    default_env = get_repo_root() / ".env"
    if default_env.exists():
        return Settings(_env_file=default_env)
    return Settings(_env_file=None)


def is_var_present(settings: Settings, var_def: EnvVarDef) -> bool:
    """Return True if variable is configured and non-empty."""
    raw = settings.get_var_value(var_def.name)
    if raw is None:
        return False
    return len(raw.strip()) > 0


def presence(settings: Settings) -> dict[str, dict[str, bool]]:
    """Return presence status {group: {NAME: bool}} for all registered variables."""
    result: dict[str, dict[str, bool]] = {}
    for group_name, var_list in REGISTRY_BY_GROUP.items():
        result[group_name] = {}
        for var_def in var_list:
            result[group_name][var_def.name] = is_var_present(settings, var_def)
    return result


def load_runtime_config(config_path: Optional[Path | str] = None) -> list[str]:
    """Read enabled groups from runtime YAML configuration.

    Raises ConfigError naming the target file if the file is missing, empty,
    lacks 'enabled_groups', or contains invalid types.
    """
    target = (
        Path(config_path)
        if config_path is not None
        else get_repo_root() / "config" / "runtime.yaml"
    )
    if not target.exists():
        raise ConfigError(f"Runtime configuration file not found: {target}")

    content = target.read_text(encoding="utf-8")
    if not content.strip():
        raise ConfigError(f"Runtime configuration file is empty: {target}")

    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        raise ConfigError(f"Runtime configuration file {target} must contain a YAML mapping")

    if "enabled_groups" not in data:
        raise ConfigError(
            f"Runtime configuration file {target} is missing required key 'enabled_groups'"
        )

    enabled = data["enabled_groups"]
    if not isinstance(enabled, list):
        raise ConfigError(f"Runtime configuration file {target}: 'enabled_groups' must be a list")

    for item in enabled:
        if not isinstance(item, str):
            raise ConfigError(
                f"Runtime configuration file {target}: all items in 'enabled_groups' "
                "must be strings"
            )

    return enabled


def validate_enabled_groups(settings: Settings, enabled_groups: list[str]) -> None:
    """Validate that every required variable for each enabled group is present.

    Raises ConfigError naming EVERY missing variable per group.
    Never includes values in error text.
    """
    missing_by_group: dict[str, list[str]] = {}

    for group in enabled_groups:
        if group not in REGISTRY_BY_GROUP:
            raise ConfigError(f"Unknown configuration group '{group}' in enabled_groups")
        for var_def in REGISTRY_BY_GROUP[group]:
            if var_def.required_when_group_enabled and not is_var_present(settings, var_def):
                missing_by_group.setdefault(group, []).append(var_def.name)

    if missing_by_group:
        formatted_groups = [
            f"group '{g}': {', '.join(vars_list)}" for g, vars_list in missing_by_group.items()
        ]
        raise ConfigError(
            "Missing required environment variables for enabled groups: "
            + "; ".join(formatted_groups)
        )


class SecretRedactionFilter(logging.Filter):
    """Logging filter replacing any sensitive value of 6 or more characters with ***."""

    def __init__(self, secrets: Optional[set[str]] = None) -> None:
        super().__init__()
        self.secrets: set[str] = {s for s in (secrets or set()) if len(s) >= 6}

    @classmethod
    def from_settings(cls, settings: Settings) -> "SecretRedactionFilter":
        """Build filter collecting all registered secrets with length >= 6."""
        found_secrets: set[str] = set()
        for var_def in REGISTRY:
            if var_def.secret:
                raw_val = settings.get_var_value(var_def.name)
                if raw_val and len(raw_val) >= 6:
                    found_secrets.add(raw_val)
        return cls(secrets=found_secrets)

    def _redact_text(self, text: str) -> str:
        """Replace all registered secret occurrences in text with ***."""
        for secret in self.secrets:
            if secret in text:
                text = text.replace(secret, "***")
        return text

    def _redact_value(self, val: Any) -> Any:
        """Redact strings or stringified representations of non-string values."""
        if isinstance(val, str):
            return self._redact_text(val)
        val_str = str(val)
        for secret in self.secrets:
            if secret in val_str:
                return self._redact_text(val_str)
        return val

    def filter(self, record: logging.LogRecord) -> bool:
        if not self.secrets:
            return True

        if isinstance(record.msg, str):
            record.msg = self._redact_text(record.msg)

        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(self._redact_value(arg) for arg in record.args)
            elif isinstance(record.args, dict):
                record.args = {
                    self._redact_value(k): self._redact_value(v) for k, v in record.args.items()
                }
            else:
                record.args = self._redact_value(record.args)

        # Redact exception tracebacks: render, redact, store in exc_text, clear exc_info
        if record.exc_info:
            rendered_exc = "".join(traceback.format_exception(*record.exc_info))
            record.exc_text = self._redact_text(rendered_exc)
            record.exc_info = None
        elif record.exc_text:
            record.exc_text = self._redact_text(record.exc_text)

        # Redact stack_info if present
        if getattr(record, "stack_info", None) and isinstance(record.stack_info, str):
            record.stack_info = self._redact_text(record.stack_info)

        return True
