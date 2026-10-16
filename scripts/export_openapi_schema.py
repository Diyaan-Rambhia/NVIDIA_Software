"""Export OpenAPI JSON schema to docs/openapi.json."""

import json
from pathlib import Path

from backend.app.config.env import Settings
from backend.app.main import create_app


def export_openapi(output_path: Path | None = None) -> Path:
    """Generate and write the application's OpenAPI schema to docs/openapi.json."""
    if output_path is None:
        output_path = Path("docs") / "openapi.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # In development mode, OpenAPI is enabled
    app = create_app(settings=Settings(app_env="development"), runtime_groups=[])
    schema = app.openapi()

    output_path.write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


if __name__ == "__main__":
    out = export_openapi()
    print(f"Exported OpenAPI schema to {out}")
