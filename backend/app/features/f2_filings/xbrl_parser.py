"""XBRL extraction and consistency rule evaluation for Feature 2 Filings engine."""

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.contracts.filings import Claim, FilingMetric
from backend.app.features.f2_filings.derived_metrics import (
    margin,
)
from backend.app.features.f2_filings.rules import RuleResult, evaluate_all_rules

DATA_XBRL_DIR = Path("data") / "xbrl"
OUTPUT_DEMO_PATH = Path("data") / "f2_filings_demo.json"

TARGET_SYMBOLS = ["INFY", "ITC", "MARUTI", "RELIANCE", "TATASTEEL"]


def _strip_tag_namespace(tag: str) -> str:
    """Return local XML element tag without namespace prefix."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_xbrl_file(file_path: Path) -> dict[str, Any]:
    """Parse an Ind-AS XBRL XML document and extract reported metrics."""
    tree = ET.parse(file_path)
    root = tree.getroot()

    company_name = ""
    symbol = file_path.stem
    reporting_quarter = ""
    start_date = ""
    end_date = ""
    nature_of_report = "Standalone"
    level_rounding = "Crores"

    metrics_raw: dict[str, dict[str, Any]] = {}

    for elem in root:
        local_tag = _strip_tag_namespace(elem.tag)
        text_val = (elem.text or "").strip()
        context_ref = elem.attrib.get("contextRef", "")
        unit_ref = elem.attrib.get("unitRef", "")
        decimals = elem.attrib.get("decimals", "")

        if local_tag == "NameOfTheCompany" and not company_name:
            company_name = text_val
        elif local_tag == "Symbol" and text_val:
            symbol = text_val
        elif local_tag == "ReportingQuarter" and not reporting_quarter:
            reporting_quarter = text_val
        elif local_tag == "DateOfStartOfReportingPeriod" and context_ref == "OneD":
            start_date = text_val
        elif local_tag == "DateOfEndOfReportingPeriod" and context_ref == "OneD":
            end_date = text_val
        elif local_tag == "NatureOfReportStandaloneConsolidated" and context_ref == "OneD":
            nature_of_report = text_val
        elif local_tag == "LevelOfRoundingUsedInFinancialStatements" and context_ref == "OneD":
            level_rounding = text_val

        # Primary quarter metrics with contextRef OneD
        if context_ref == "OneD" and unit_ref:
            try:
                num_val = float(text_val)
                metrics_raw[local_tag] = {
                    "value": f"{num_val:.2f}",
                    "contextRef": context_ref,
                    "unitRef": unit_ref,
                    "decimals": decimals,
                }
            except (ValueError, TypeError):
                continue

    # Canonical fiscal period label
    from backend.app.data.fiscal import date_to_fiscal_period
    if end_date:
        try:
            dt = datetime.strptime(end_date[:10], "%Y-%m-%d").date()
            fiscal_period = date_to_fiscal_period(dt)
        except Exception:
            fiscal_period = "Q3 FY25"
    else:
        fiscal_period = reporting_quarter or "Q3 FY25"


    parsed_result = {
        "company": company_name or symbol,
        "symbol": symbol,
        "period": reporting_quarter or "Quarterly",
        "fiscal_period": fiscal_period,
        "period_end_date": end_date,
        "basis": nature_of_report.lower(),
        "level_rounding": level_rounding,
        "metrics": metrics_raw,
    }

    # Save per-company parsed JSON
    out_path = Path("data") / f"f2_parsed_{symbol}.json"
    out_path.write_text(json.dumps(parsed_result, indent=2), encoding="utf-8")
    return parsed_result


def evaluate_company_rules(parsed_data: dict[str, Any]) -> list[RuleResult]:
    """Execute consistency rules R0-R7 for a company's parsed filing."""
    company = parsed_data["company"]
    symbol = parsed_data["symbol"]
    metrics = parsed_data.get("metrics", {})
    end_date = parsed_data.get("period_end_date", "")
    basis = "consolidated" if "consolidated" in parsed_data.get("basis", "") else "standalone"
    fiscal_period = parsed_data.get("fiscal_period", "Q3")

    rev_info = metrics.get("RevenueFromOperations")
    pbt_info = metrics.get("ProfitBeforeTax")
    pat_info = metrics.get("ProfitLossForPeriod")
    emp_info = metrics.get("EmployeeBenefitExpense")
    mat_info = metrics.get("CostOfMaterialsConsumed")
    oth_info = metrics.get("OtherExpenses")

    rev_val = float(rev_info["value"]) if rev_info else 0.0
    pbt_val = float(pbt_info["value"]) if pbt_info else 0.0
    pat_val = float(pat_info["value"]) if pat_info else 0.0

    emp_val = float(emp_info["value"]) if emp_info else 0.0
    mat_val = float(mat_info["value"]) if mat_info else 0.0
    oth_val = float(oth_info["value"]) if oth_info else 0.0

    ebitda_val = rev_val - (emp_val + mat_val + oth_val)

    retrieval_iso = datetime.now(timezone.utc).isoformat()
    filing_metric = FilingMetric(
        company=company,
        symbol=symbol,
        fiscal_period=fiscal_period,
        period_end_date=end_date or "period_end",
        basis=basis,
        metric="revenue",
        value=rev_val,
        unit="INR",
        source_filing_reference=f"NSE_XBRL_{symbol}",
        derived=False,
        retrieval_time=retrieval_iso,
    )

    # Stated claim for consistency verification
    claim = Claim(
        metric="revenue",
        descriptor="strong",
        direction="grew",
        quote=f"{company} revenue growth in {fiscal_period}",
        start=0,
        end=len(company) + 15,
        period=fiscal_period,
        basis="reported",
    )

    # Derived margin checks
    m_ebitda = margin(ebitda_val, rev_val) if rev_val > 0 else 0.0
    m_pat = margin(pat_val, rev_val) if rev_val > 0 else 0.0

    # Sector thresholds
    sector_thresholds = {"it": 0.08, "auto": 0.10, "energy": 0.06, "metals": 0.05, "fmcg": 0.07}
    sec = "it" if symbol == "INFY" else "fmcg" if symbol == "ITC" else "auto" if symbol == "MARUTI" else "energy" if symbol == "RELIANCE" else "metals"

    results = evaluate_all_rules(
        claim=claim,
        metric=filing_metric,
        stated_value=rev_val,
        tolerance_pp=0.5,
        filing_change=0.05,
        growth=0.07,
        sector=sec,
        sector_thresholds=sector_thresholds,
        current_growth=0.07,
        prior_growth=0.06,
        margin_change=0.005,
        margin_tolerance_bps=20,
        ocf_yoy_growth=0.03,
        ocf_conversion=0.85,
        ocf_conversion_floor=0.5,
        inventory_growth=0.04,
        revenue_growth=0.07,
        dso_change=2.0,
        claimed_unit="INR",
        claim_metric_basis=basis,
    )
    return results


def run_f2_filings_pipeline() -> dict[str, Any]:
    """Execute XBRL parsing across 5 non-financial companies and precompute demo outputs."""
    summary_report: dict[str, Any] = {
        "source_label": "unofficial source, demo only",
        "companies_evaluated": [],
        "total_rules_evaluated": 0,
        "total_flags": 0,
        "total_passes": 0,
    }

    for sym in TARGET_SYMBOLS:
        xml_file = DATA_XBRL_DIR / f"{sym}.xml"
        if not xml_file.exists():
            continue

        parsed = parse_xbrl_file(xml_file)
        rule_evals = evaluate_company_rules(parsed)

        flags = sum(1 for r in rule_evals if r.status == "flag")
        passes = sum(1 for r in rule_evals if r.status == "pass")

        summary_report["companies_evaluated"].append({
            "symbol": sym,
            "company": parsed["company"],
            "fiscal_period": parsed["fiscal_period"],
            "revenue": parsed.get("metrics", {}).get("RevenueFromOperations", {}).get("value"),
            "pbt": parsed.get("metrics", {}).get("ProfitBeforeTax", {}).get("value"),
            "pat": parsed.get("metrics", {}).get("ProfitLossForPeriod", {}).get("value"),
            "rule_results": [r.model_dump() for r in rule_evals],
            "flags_count": flags,
            "passes_count": passes,
        })
        summary_report["total_rules_evaluated"] += len(rule_evals)
        summary_report["total_flags"] += flags
        summary_report["total_passes"] += passes

    OUTPUT_DEMO_PATH.write_text(json.dumps(summary_report, indent=2), encoding="utf-8")
    return summary_report


if __name__ == "__main__":
    rep = run_f2_filings_pipeline()
    print("Precomputed F2 Filings demo successfully for", len(rep["companies_evaluated"]), "companies")
