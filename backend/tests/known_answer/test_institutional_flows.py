"""Known-answer tests for Feature 1 Institutional Flows (FPI/DII) and Sector Attribution."""

import pytest

from backend.app.features.f1_contagion.institutional_flows import (
    attribute_portfolio_to_sector_flows,
    compute_institutional_summary,
    parse_institutional_flow_csv,
)


SAMPLE_BULLETIN_CSV = (
    "date,category,gross_purchases_inr_cr,gross_sales_inr_cr,net_investment_inr_cr,sector\n"
    "2024-01-15,FPI,8500.0,12500.0,-4000.0,Financial Services\n"
    "2024-01-15,DII,9000.0,4000.0,5000.0,Financial Services\n"
    "2024-01-15,FPI,3000.0,4500.0,-1500.0,Information Technology\n"
    "2024-01-15,DII,4000.0,2000.0,2000.0,Information Technology\n"
)


def test_parse_bulletin_csv():
    """Verify parsing institutional bulletin CSV records."""
    records = parse_institutional_flow_csv(SAMPLE_BULLETIN_CSV)
    assert len(records) == 4
    assert records[0].category == "FPI"
    assert records[0].net_investment_inr_cr == -4000.0
    assert records[1].category == "DII"
    assert records[1].net_investment_inr_cr == 5000.0


def test_parse_bulletin_csv_unknown_category_raises():
    """Verify unknown investor category raises ValueError."""
    bad_csv = (
        "date,category,gross_purchases_inr_cr,gross_sales_inr_cr,net_investment_inr_cr\n"
        "2024-01-15,RETAIL,1000.0,500.0,500.0\n"
    )
    with pytest.raises(ValueError, match="unknown investor category"):
        parse_institutional_flow_csv(bad_csv)


def test_compute_institutional_summary():
    """Verify institutional net flow totals, divergence, and regime classification."""
    records = parse_institutional_flow_csv(SAMPLE_BULLETIN_CSV)
    summary = compute_institutional_summary(records)

    # FPI net = -4000 + -1500 = -5500 Cr
    assert summary.total_fpi_net_cr == -5500.0
    # DII net = +5000 + +2000 = +7000 Cr
    assert summary.total_dii_net_cr == 7000.0
    # Total net = 1500 Cr
    assert summary.net_institutional_liquidity_cr == 1500.0
    # Divergence = abs(-5500 - 7000) = 12500 Cr
    assert summary.fpi_dii_divergence_cr == 12500.0
    # FPI < 0 and DII > 0 regime is FPI flight with DII absorption
    assert summary.primary_regime == "fpi_flight_dii_absorption"


def test_attribute_portfolio_to_sector_flows():
    """Verify sector-weighted macro flow attribution math."""
    holdings = {
        "Financial Services": 0.60,
        "Information Technology": 0.40,
    }
    # Net sector institutional flows (FPI + DII)
    # Financial Services: -4000 + 5000 = +1000 Cr
    # IT: -1500 + 2000 = +500 Cr
    sector_flows = {
        "Financial Services": 1000.0,
        "Information Technology": 500.0,
    }

    result = attribute_portfolio_to_sector_flows(holdings, sector_flows)
    # Expected weighted flow = 0.6 * 1000 + 0.4 * 500 = 600 + 200 = 800 Cr
    assert result["attributed_net_flow_cr"] == 800.0
    assert result["portfolio_exposure_status"] == "inflow_supported"

    breakdown = result["sector_breakdown"]
    assert breakdown["Financial Services"]["flow_contribution_cr"] == 600.0
    assert breakdown["Financial Services"]["liquidity_impact"] == "tailwind"
    assert breakdown["Information Technology"]["flow_contribution_cr"] == 200.0
    assert breakdown["Information Technology"]["liquidity_impact"] == "tailwind"
