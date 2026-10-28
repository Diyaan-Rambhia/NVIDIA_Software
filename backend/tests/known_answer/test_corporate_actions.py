"""Known-answer tests for Feature 3 Corporate Actions and lot adjustments."""

from collections import deque
from datetime import date
import pytest

from backend.app.contracts.portfolio import ColumnMapping, Trade, TradeLog
from backend.app.features.f3_log.corporate_actions import (
    CorporateAction,
    adjust_lots_for_corporate_action,
    parse_corporate_actions_csv,
)
from backend.app.features.f3_log.pipeline import build_portfolio_ledger
from backend.app.features.f3_log.xirr import xirr


def test_stock_split_lot_adjustment():
    """Verify 2-for-1 stock split doubles quantity and halves price basis."""
    lots: deque[tuple[float, float]] = deque([(100.0, 1000.0)])
    action = CorporateAction(
        date="2024-06-01",
        symbol="INFY",
        action_type="SPLIT",
        ratio_numerator=2.0,
        ratio_denominator=1.0,
    )
    new_lots, div_cash = adjust_lots_for_corporate_action(lots, action)
    assert div_cash == 0.0
    assert len(new_lots) == 1
    qty, price = new_lots[0]
    assert qty == 200.0
    assert price == 500.0
    assert qty * price == 100000.0


def test_bonus_issue_lot_adjustment():
    """Verify 1-for-1 bonus issue doubles quantity and halves cost basis."""
    lots: deque[tuple[float, float]] = deque([(100.0, 3000.0)])
    action = CorporateAction(
        date="2024-07-01",
        symbol="TCS",
        action_type="BONUS",
        ratio_numerator=1.0,
        ratio_denominator=1.0,
    )
    new_lots, div_cash = adjust_lots_for_corporate_action(lots, action)
    assert div_cash == 0.0
    assert len(new_lots) == 1
    qty, price = new_lots[0]
    assert qty == 200.0
    assert price == 1500.0
    assert qty * price == 300000.0


def test_dividend_cash_flow():
    """Verify cash dividend computes cash inflow on open holdings without changing lots."""
    lots: deque[tuple[float, float]] = deque([(100.0, 400.0)])
    action = CorporateAction(
        date="2024-08-01",
        symbol="ITC",
        action_type="DIVIDEND",
        dividend_per_share=10.0,
    )
    new_lots, div_cash = adjust_lots_for_corporate_action(lots, action)
    assert div_cash == 1000.0
    assert len(new_lots) == 1
    qty, price = new_lots[0]
    assert qty == 100.0
    assert price == 400.0


def test_portfolio_ledger_with_split_and_sell():
    """Verify trade log lifecycle with split allows selling split quantity correctly."""
    trades = [
        Trade(
            date="2023-01-01",
            symbol="INFY",
            side="BUY",
            quantity=10.0,
            price=100.0,
        ),
        Trade(
            date="2024-01-01",
            symbol="INFY",
            side="SELL",
            quantity=20.0,
            price=55.0,
        ),
    ]
    trade_log = TradeLog(
        trades=trades,
        total_trades=2,
        symbols=["INFY"],
        start_date="2023-01-01",
        end_date="2024-01-01",
    )

    action = CorporateAction(
        date="2023-06-01",
        symbol="INFY",
        action_type="SPLIT",
        ratio_numerator=2.0,
        ratio_denominator=1.0,
    )

    portfolio, cash_flows, gain_events, loss_events = build_portfolio_ledger(
        trade_log,
        latest_prices={"INFY": 55.0},
        corporate_actions=[action],
    )

    # Open position should be 0 because 20 shares were sold out of 20 split shares
    infy_pos = [p for p in portfolio.positions if p.symbol == "INFY"][0]
    assert infy_pos.quantity == 0.0
    # Realized PnL: Sold 20 at 55 (1100), cost basis was 20 at 50 (1000) => +100
    assert infy_pos.realized_pnl == 100.0

    # Solved XIRR on cash flows: -1000 on day 0, +1100 exactly 365 days later = 10%
    rate = xirr(
        cash_flows,
        bracket=(-0.99, 10.0),
        tol=1e-6,
        max_iter=100,
        grid_points=100,
    )
    assert pytest.approx(rate, abs=1e-3) == 0.10


def test_parse_corporate_actions_csv():
    """Verify parsing corporate actions CSV format."""
    csv_text = (
        "date,symbol,action_type,ratio_numerator,ratio_denominator,dividend_per_share\n"
        "2024-01-15,RELIANCE,BONUS,1,1,0\n"
        "2024-03-20,INFY,DIVIDEND,0,0,15.5\n"
        "2024-05-10,TCS,SPLIT,5,1,0\n"
    )
    actions = parse_corporate_actions_csv(csv_text)
    assert len(actions) == 3
    assert actions[0].symbol == "RELIANCE"
    assert actions[0].action_type == "BONUS"
    assert actions[1].dividend_per_share == 15.5
    assert actions[2].action_type == "SPLIT"
    assert actions[2].ratio_numerator == 5.0
