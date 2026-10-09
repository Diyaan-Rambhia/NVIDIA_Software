"""Known-answer and validation tests for contract models."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.contracts import (
    Claim,
    ErrorDetail,
    ErrorEnvelope,
    EvidenceItem,
    EvidencePack,
    FilingMetric,
    Hypothesis,
    Trade,
    WindowRange,
)
from scripts.export_contract_schemas import CONTRACT_MODELS


def test_roundtrip_all_models() -> None:
    """Every model must successfully round-trip to and from dict/JSON."""
    err = ErrorEnvelope(
        error=ErrorDetail(code="BAD_REQ", message="Invalid", request_id="req-123", upstream=None)
    )
    assert ErrorEnvelope.model_validate(err.model_dump()) == err

    wr = WindowRange(baseline=["2025-01-01", "2025-06-01"], current=["2025-06-02", "2025-07-01"])
    assert WindowRange.model_validate(wr.model_dump()) == wr

    ei = EvidenceItem(
        id="E1",
        kind="pair_shift",
        description="Shift observed",
        values={"rho": 0.85},
        source="NSE",
    )
    assert EvidenceItem.model_validate(ei.model_dump()) == ei

    ep = EvidencePack(
        as_of="2025-07-01",
        parameters_used={"W": 60},
        window=wr,
        items=[ei],
        seed=42,
        code_version="v0.1.0",
    )
    assert EvidencePack.model_validate(ep.model_dump()) == ep

    hyp = Hypothesis(
        mechanism_class="global risk-off",
        evidence_supporting=["E1"],
        evidence_weakening=["E2"],
        retrieved_urls=["https://example.com/news1"],
        plausible_mechanism="FPI outflow triggered by rate hike",
    )
    assert Hypothesis.model_validate(hyp.model_dump()) == hyp

    cl = Claim(
        metric="revenue",
        descriptor="strong growth",
        direction="increase",
        quote="revenue grew by 15%",
        start=10,
        end=30,
        period="FY25-Q1",
        basis="reported",
    )
    assert Claim.model_validate(cl.model_dump()) == cl

    fm = FilingMetric(
        company="Tata Motors",
        symbol="TATAMOTORS",
        isin="INE155A01022",
        fiscal_period="2024-2025-Q1",
        period_end_date="2024-06-30",
        basis="consolidated",
        metric="revenue from operations",
        value=105000.5,
        unit="INR crore",
        source_filing_reference="NSE_TATAMOTORS_Q1_RESULTS.pdf",
        derived=False,
        retrieval_time="10:00:00",
    )
    assert FilingMetric.model_validate(fm.model_dump()) == fm

    tr = Trade(
        date="2025-05-10",
        symbol="INFY",
        side="BUY",
        quantity=100.0,
        price=1450.50,
        fees=12.5,
        charges=5.0,
        exchange="NSE",
        segment="EQUITY",
    )
    assert Trade.model_validate(tr.model_dump()) == tr


def test_unknown_field_rejected() -> None:
    """Extra unexpected fields must be rejected per extra='forbid'."""
    with pytest.raises(ValidationError):
        Trade(
            date="2025-05-10",
            symbol="INFY",
            side="BUY",
            quantity=100.0,
            price=1450.50,
            unknown_extra=999,  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        EvidenceItem(
            id="E1",
            kind="pair_shift",
            description="Shift",
            values={"rho": 0.5},
            source="NSE",
            extra_field="rejected",  # type: ignore[call-arg]
        )


def test_evidence_item_id_pattern() -> None:
    """EvidenceItem id must match 'E<digits>' pattern."""
    EvidenceItem(
        id="E1", kind="pair_shift", description="Valid", values={"x": 1.0}, source="NSE"
    )
    EvidenceItem(
        id="E999", kind="pair_shift", description="Valid", values={"x": 1.0}, source="NSE"
    )

    with pytest.raises(ValidationError):
        EvidenceItem(
            id="INVALID1", kind="pair_shift", description="Bad", values={"x": 1.0}, source="NSE"
        )

    with pytest.raises(ValidationError):
        EvidenceItem(
            id="E_1", kind="pair_shift", description="Bad", values={"x": 1.0}, source="NSE"
        )


def test_unique_evidence_item_ids() -> None:
    """EvidencePack must reject duplicate EvidenceItem IDs."""
    wr = WindowRange(baseline=["d0", "d1"], current=["d2", "d3"])
    ei1 = EvidenceItem(
        id="E1", kind="pair_shift", description="Item 1", values={"x": 1.0}, source="S1"
    )
    ei2 = EvidenceItem(
        id="E1", kind="pair_shift", description="Item 2", values={"x": 2.0}, source="S2"
    )

    with pytest.raises(ValidationError):
        EvidencePack(
            as_of="d3",
            parameters_used={},
            window=wr,
            items=[ei1, ei2],  # Duplicate E1
            seed=1,
            code_version="1",
        )


def test_hypothesis_min_evidence_id() -> None:
    """Hypothesis requires at least 1 supporting evidence ID."""
    with pytest.raises(ValidationError):
        Hypothesis(
            mechanism_class="risk-off",
            evidence_supporting=[],  # Empty, must fail
            evidence_weakening=[],
            retrieved_urls=["https://example.com"],
            plausible_mechanism="Shock",
        )


def test_trade_positivity() -> None:
    """Trade quantity and price must be strictly positive."""
    with pytest.raises(ValidationError):
        Trade(date="d", symbol="S", side="BUY", quantity=0.0, price=100.0)

    with pytest.raises(ValidationError):
        Trade(date="d", symbol="S", side="BUY", quantity=10.0, price=-5.0)


def test_claim_end_greater_than_start() -> None:
    """Claim end offset must be strictly greater than start offset."""
    with pytest.raises(ValidationError):
        Claim(
            metric="m",
            descriptor="d",
            direction="dir",
            quote="q",
            start=10,
            end=10,  # end == start must fail
            period="p",
            basis="reported",
        )

    with pytest.raises(ValidationError):
        Claim(
            metric="m",
            descriptor="d",
            direction="dir",
            quote="q",
            start=20,
            end=10,  # end < start must fail
            period="p",
            basis="reported",
        )


def test_committed_schemas_match_generated() -> None:
    """Committed schema files in docs/contracts/ must match freshly generated schemas."""
    contracts_dir = Path("docs") / "contracts"
    assert contracts_dir.is_dir(), "docs/contracts directory must exist"

    for model_name, model_cls in CONTRACT_MODELS.items():
        schema_file = contracts_dir / f"{model_name}.json"
        assert schema_file.is_file(), f"Missing committed schema file: {schema_file}"

        fresh_schema = model_cls.model_json_schema()
        committed_schema = json.loads(schema_file.read_text(encoding="utf-8"))
        assert fresh_schema == committed_schema, f"Schema mismatch for {model_name}"
