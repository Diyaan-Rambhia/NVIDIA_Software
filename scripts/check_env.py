"""Check environment variables against the registry and validate enabled groups."""

import sys

from backend.app.config.env import (
    ConfigError,
    load_runtime_config,
    load_settings,
    presence,
    validate_enabled_groups,
)


def main() -> int:
    settings = load_settings()
    enabled_groups = load_runtime_config()
    pres = presence(settings)

    print("Environment Variable Presence Report:")
    for group_name, var_dict in pres.items():
        is_enabled = group_name in enabled_groups
        status_suffix = " (enabled)" if is_enabled else ""
        print(f"\nGroup: {group_name}{status_suffix}")
        for var_name, is_present in var_dict.items():
            state = "present" if is_present else "absent"
            print(f"  {var_name}: {state}")

    try:
        validate_enabled_groups(settings, enabled_groups)
    except ConfigError as err:
        sys.stderr.write(f"\nConfiguration Error: {err}\n")
        return 1

    print("\nEnvironment check passed for all enabled groups.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
