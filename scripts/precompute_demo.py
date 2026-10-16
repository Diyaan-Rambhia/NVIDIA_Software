"""Deterministic precompute script for all demo paths (Feature 1, Feature 2, Feature 3).

Adheres strictly to PROJECT.md real-data policy and hackathon demo requirements:
- Deterministic calculations only (statistics, filings rules, investment log metrics).
- LLM text sections marked 'not generated: awaiting real model'.
- Zero placeholder template markers or placeholder text in generated JSON files.
"""

import json
from pathlib import Path

from backend.app.contracts.contagion import CorrelationScan
from backend.app.contracts.portfolio import ColumnMapping, DecisionReview
from backend.app.features.f1_contagion.pipeline import run_correlation_scan
from backend.app.features.f2_filings.xbrl_parser import run_f2_filings_pipeline
from backend.app.features.f3_log.pipeline import execute_feature3_review, parse_trade_log_csv

DATA_DIR = Path("data")
F1_OUT = DATA_DIR / "f1_scan_demo.json"
F2_OUT = DATA_DIR / "f2_filings_demo.json"
F3_OUT = DATA_DIR / "f3_review_demo.json"
F3_CSV = Path("private") / "logs" / "demo_synthetic_log.csv"


def precompute_f1() -> None:
    """Precompute Feature 1 Contagion scan."""
    print("Precomputing Feature 1 correlation scan...")
    scan = run_correlation_scan()
    F1_OUT.write_text(json.dumps(scan.model_dump(), indent=2), encoding="utf-8")
    print(f"Feature 1 written to {F1_OUT}")


def precompute_f2() -> None:
    """Precompute Feature 2 XBRL filings consistency rules for 5 non-financial companies."""
    print("Precomputing Feature 2 filing rules...")
    summary = run_f2_filings_pipeline()
    for comp in summary.get("companies_evaluated", []):
        comp["llm_adjudication"] = "not generated: awaiting real model"
    F2_OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Feature 2 written to {F2_OUT}")


def precompute_f3() -> None:
    """Precompute Feature 3 synthetic demo trade log review."""
    print("Precomputing Feature 3 investment log review...")
    if not F3_CSV.is_file():
        raise FileNotFoundError(f"Missing {F3_CSV}")

    csv_text = F3_CSV.read_text(encoding="utf-8")
    mapping = ColumnMapping(
        date="Date",
        symbol="Symbol",
        side="Side",
        quantity="Quantity",
        price="Price",
        fees="Fees",
    )
    trade_log = parse_trade_log_csv(csv_text=csv_text, mapping=mapping, consent_given=False)
    review = execute_feature3_review(trade_log=trade_log, is_institutional=True, benchmark_symbol="NSEI")

    # Mark LLM narrative as awaiting real model
    review_dict = review.model_dump()
    review_dict["review_text"] = "SYNTHETIC DEMO LOG, not a real investor. not generated: awaiting real model"
    F3_OUT.write_text(json.dumps(review_dict, indent=2), encoding="utf-8")
    print(f"Feature 3 written to {F3_OUT}")


def main() -> None:
    precompute_f1()
    precompute_f2()
    precompute_f3()
    print("All demo endpoints precomputed successfully.")


if __name__ == "__main__":
    main()
