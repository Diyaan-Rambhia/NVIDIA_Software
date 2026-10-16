"""Export JSON schemas for registered frozen contract models to docs/contracts/."""

import json
from pathlib import Path

from pydantic import BaseModel

from backend.app.contracts import (
    AgentStep,
    Claim,
    ColumnMapping,
    CorrelationScan,
    DecisionReview,
    ErrorDetail,
    ErrorEnvelope,
    EvidenceItem,
    EvidencePack,
    FilingMetric,
    Hypothesis,
    Inconsistency,
    Portfolio,
    Trade,
    TradeLog,
    WindowRange,
)

CONTRACT_MODELS: dict[str, type[BaseModel]] = {
    "AgentStep": AgentStep,
    "ErrorDetail": ErrorDetail,
    "ErrorEnvelope": ErrorEnvelope,
    "WindowRange": WindowRange,
    "EvidenceItem": EvidenceItem,
    "EvidencePack": EvidencePack,
    "Hypothesis": Hypothesis,
    "Claim": Claim,
    "FilingMetric": FilingMetric,
    "Inconsistency": Inconsistency,
    "Trade": Trade,
    "CorrelationScan": CorrelationScan,
    "ColumnMapping": ColumnMapping,
    "TradeLog": TradeLog,
    "Portfolio": Portfolio,
    "DecisionReview": DecisionReview,
}


def export_schemas(output_dir: Path | None = None) -> list[Path]:
    """Write model JSON schema for every registered contract model."""
    if output_dir is None:
        output_dir = Path("docs") / "contracts"

    output_dir.mkdir(parents=True, exist_ok=True)
    exported: list[Path] = []

    for model_name, model_cls in CONTRACT_MODELS.items():
        schema_file = output_dir / f"{model_name}.json"
        schema_data = model_cls.model_json_schema()
        schema_file.write_text(
            json.dumps(schema_data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        exported.append(schema_file)

    return exported


if __name__ == "__main__":
    out = export_schemas()
    print(f"Exported {len(out)} contract schemas to docs/contracts/")
