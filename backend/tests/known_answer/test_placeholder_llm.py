"""Known-answer and validation tests for Placeholder LLM provider and X7, X8, X9 layers."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.app.config.env import Settings
from backend.app.contracts.contagion import CorrelationScan, Hypothesis, ShiftedPair
from backend.app.contracts.filings import Claim, FilingMetric, Inconsistency
from backend.app.contracts.portfolio import (
    BenchmarkReplay,
    DecisionReview,
    Portfolio,
    Position,
    ProcessMetrics,
)
from backend.app.features.f1_contagion.explanation import (
    build_evidence_pack,
    fetch_tavily_news,
    generate_hypotheses,
)
from backend.app.features.f2_filings.adjudication import (
    extract_claims_from_text,
    match_and_adjudicate,
    verify_inconsistency_flag,
)
from backend.app.features.f3_log.review_llm import generate_decision_review_narrative
from backend.app.llm.exceptions import BudgetExceededError, FinancialAdviceError, LLMError
from backend.app.llm.guard import assert_no_financial_advice
from backend.app.llm.placeholder import PLACEHOLDER_MARKER, PlaceholderProvider
from backend.app.llm.structured import complete_structured


def test_placeholder_refuses_in_production(tmp_path: Path) -> None:
    """Placeholder provider must strictly refuse execution when APP_ENV is production."""
    prod_env = tmp_path / "prod.env"
    prod_env.write_text("APP_ENV=production\n", encoding="utf-8")
    settings = Settings(_env_file=prod_env)

    with pytest.raises(RuntimeError, match="strictly forbidden in 'production' environment"):
        PlaceholderProvider(settings=settings)


def test_placeholder_returns_placeholder_marker_and_ledger_shape() -> None:
    """Placeholder completions carry the required marker and return standard completion structure."""
    provider = PlaceholderProvider()
    resp = provider.complete(
        alias="fast",
        messages=[{"role": "user", "content": "Analyze recent performance"}],
    )

    assert resp["is_placeholder"] is True
    assert PLACEHOLDER_MARKER in resp["placeholder_label"]
    choice = resp["choices"][0]
    content = choice["message"]["content"]
    assert PLACEHOLDER_MARKER in content
    assert resp["usage"]["total_tokens"] > 0


def test_placeholder_caching() -> None:
    """Second identical call hits the cache."""
    provider = PlaceholderProvider()
    msgs = [{"role": "user", "content": "Unique cache test query 12345"}]
    res1 = provider.complete("fast", msgs)
    res2 = provider.complete("fast", msgs)
    assert res1["id"] == res2["id"]


def test_placeholder_budget_guard_exercises_real_path() -> None:
    """Placeholder provider exercises real budget guard when conn is provided."""
    mock_conn = MagicMock()
    provider = PlaceholderProvider(conn=mock_conn)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "backend.app.llm.placeholder.check_budget_guard",
            MagicMock(side_effect=BudgetExceededError("Daily LLM budget exceeded")),
        )
        with pytest.raises(BudgetExceededError, match="Daily LLM budget exceeded"):
            provider.complete("fast", [{"role": "user", "content": "test prompt"}])


def test_x7_f1_hypotheses_and_tavily_step() -> None:
    """F1 hypotheses cite real evidence IDs, have hedged language, and Tavily step raises if no key."""
    # 1. Tavily news step raises 'not run: no key'
    with pytest.raises(ValueError, match="not run: no key"):
        fetch_tavily_news("RBI monetary policy")

    # 2. Build EvidencePack from scan
    scan = CorrelationScan(
        as_of="as_of_scan_day",
        regime_flag="watch",
        absorption_ratio=0.42,
        ar_delta_std=1.85,
        significant_pairs_count=3,
        mean_correlation=0.55,
        top_shifted_pairs=[
            ShiftedPair(
                pair=["INFY", "TCS"],
                baseline_corr=0.4,
                current_corr=0.8,
                fr_adjusted_corr=0.75,
                p_value=0.01,
                q_value=0.02,
            )
        ],
        parameters_used={"W": 60},
        seed=42,
        code_version="v0.1.0",
    )
    pack = build_evidence_pack(scan)
    assert len(pack.items) >= 2
    assert pack.items[0].id == "E1"
    assert pack.items[1].id == "E2"

    # 3. Generate hypotheses
    hypotheses = generate_hypotheses(pack)
    assert 2 <= len(hypotheses) <= 4
    for h in hypotheses:
        assert isinstance(h, Hypothesis)
        assert len(h.evidence_supporting) >= 1
        for eid in h.evidence_supporting:
            assert any(item.id == eid for item in pack.items)
        assert len(h.retrieved_urls) >= 1
        assert PLACEHOLDER_MARKER in h.plausible_mechanism


def test_x8_f2_claim_extraction_and_adjudication() -> None:
    """Extract claims from text and match against FilingMetric to produce Inconsistency."""
    source_text = "The management reported that revenue from operations grew by 15% in Q1."
    claims = extract_claims_from_text(source_text, fiscal_period="FY_Q1")
    assert len(claims) == 1
    assert claims[0].quote in source_text
    assert claims[0].start >= 0
    assert claims[0].end <= len(source_text)
    assert source_text[claims[0].start : claims[0].end] == claims[0].quote

    metrics = [
        FilingMetric(
            company="Test Corp",
            symbol="TEST",
            fiscal_period="FY_Q1",
            period_end_date="period_end_ref",
            basis="consolidated",
            metric="revenue from operations",
            value=8.5,
            unit="percent",
            source_filing_reference="test.xml",
            derived=False,
            retrieval_time="10:00:00",
        )
    ]
    inconsistencies = match_and_adjudicate(claims, metrics, source_text)
    assert len(inconsistencies) == 1
    inc = inconsistencies[0]
    assert inc.rule_id == "R0"
    assert inc.verdict == "confirm"
    assert inc.stated_value == 15.0
    assert inc.filed_value == 8.5
    assert inc.difference_value == 6.5
    assert inc.is_placeholder is True
    assert PLACEHOLDER_MARKER in inc.placeholder_label


def test_x8_f2_verifier_blocks_bad_inputs() -> None:
    """Deterministic verifier blocks quotes not in source, wrong numbers, and advice phrases."""
    source_text = "Company reported revenue grew by 12% in the quarter."

    # Valid inconsistency
    valid_inc = Inconsistency(
        rule_id="R0",
        verdict="confirm",
        severity="high",
        metric="revenue from operations",
        claim_quote="revenue grew by 12%",
        quote_start=17,
        quote_end=36,
        stated_value=12.0,
        filed_value=6.0,
        difference_value=6.0,
        explanation="Stated growth differs from filed.",
    )
    assert verify_inconsistency_flag(valid_inc, source_text) is True

    # Bad 1: Quote not in source
    bad_quote_inc = Inconsistency(
        rule_id="R0",
        verdict="confirm",
        severity="high",
        metric="revenue from operations",
        claim_quote="completely fabricated quote",
        quote_start=0,
        quote_end=27,
        stated_value=12.0,
        filed_value=6.0,
        difference_value=6.0,
        explanation="Stated growth differs from filed.",
    )
    with pytest.raises(ValueError, match="Blocked: quote"):
        verify_inconsistency_flag(bad_quote_inc, source_text)

    # Bad 2: Stated number not literally in source quote
    bad_num_inc = Inconsistency(
        rule_id="R0",
        verdict="confirm",
        severity="high",
        metric="revenue from operations",
        claim_quote="revenue grew by 12%",
        quote_start=17,
        quote_end=36,
        stated_value=99.0,  # 99 is not in quote
        filed_value=6.0,
        difference_value=93.0,
        explanation="Stated growth differs from filed.",
    )
    with pytest.raises(ValueError, match="Blocked: stated number"):
        verify_inconsistency_flag(bad_num_inc, source_text)

    # Bad 3: Prohibited advice phrase in explanation
    bad_advice_inc = Inconsistency(
        rule_id="R0",
        verdict="confirm",
        severity="high",
        metric="revenue from operations",
        claim_quote="revenue grew by 12%",
        quote_start=17,
        quote_end=36,
        stated_value=12.0,
        filed_value=6.0,
        difference_value=6.0,
        explanation="Investors should recommend to buy because margins are high.",
    )
    with pytest.raises(FinancialAdviceError, match="Prohibited financial advice detected"):
        verify_inconsistency_flag(bad_advice_inc, source_text)


def test_x9_f3_decision_review_narrative() -> None:
    """X9 review text evaluates process-versus-outcome and preserves synthetic demo label."""
    pos = Position(
        symbol="INFY",
        quantity=10.0,
        average_buy_price=1500.0,
        realized_pnl=500.0,
        current_price=1600.0,
        current_value=16000.0,
        unrealized_pnl=1000.0,
    )
    port = Portfolio(
        positions=[pos],
        cash_balance=0.0,
        total_cost=15000.0,
        total_market_value=16000.0,
        total_realized_pnl=500.0,
        total_unrealized_pnl=1000.0,
    )
    pm = ProcessMetrics(
        concentration_hhi=0.25,
        turnover=0.45,
        disposition_effect={"pgr": 0.65, "plr": 0.35},
        max_drawdown=0.08,
    )
    bm = BenchmarkReplay(
        benchmark_name="NIFTY 50",
        terminal_value=16500.0,
        xirr=0.14,
        partial_shortfall=False,
    )

    review_synthetic = DecisionReview(
        portfolio=port,
        portfolio_xirr=0.18,
        benchmark_replays=[bm],
        process_metrics=pm,
        institutional_metrics=None,
        review_text="Initial deterministic audit.",
        disclaimer="Educational only.",
        parameters_used={},
        is_synthetic_demo=True,
        synthetic_label="SYNTHETIC DEMO LOG, not a real investor",
    )
    narrative = generate_decision_review_narrative(review_synthetic)

    assert "SYNTHETIC DEMO LOG, not a real investor" in narrative
    assert PLACEHOLDER_MARKER in narrative
    assert "Process-versus-outcome" in narrative
    assert "concentration HHI of 0.2500" in narrative
    assert "Educational and research review only" in narrative
    # Assert no advice in narrative
    assert_no_financial_advice(narrative)


def test_output_guard_rejects_financial_advice() -> None:
    """Response path rejects buy, sell, or hold advice from config."""
    with pytest.raises(FinancialAdviceError, match="Prohibited financial advice detected"):
        assert_no_financial_advice("We advise to buy this stock immediately.")

    with pytest.raises(FinancialAdviceError, match="Prohibited financial advice detected"):
        assert_no_financial_advice("Strong sell signal observed across portfolio.")

    with pytest.raises(FinancialAdviceError, match="Prohibited financial advice detected"):
        assert_no_financial_advice("Given the upside, our target price is 2000.")


def test_structured_completion_error_handling() -> None:
    """Invalid JSON or empty response raises LLMError after max retries."""
    class DummyClient:
        def complete(self, **kwargs: Any) -> dict[str, Any]:
            # Always return unparsable response
            return {
                "choices": [{"message": {"content": "This is definitely not valid JSON"}}],
            }

    dummy = DummyClient()
    with pytest.raises(LLMError, match="Structured output validation failed"):
        complete_structured(
            client=dummy,  # type: ignore[arg-type]
            alias="fast",
            messages=[{"role": "user", "content": "test"}],
            schema_model=Claim,
            max_retries=1,
        )
