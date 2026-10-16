"""Portfolio and trade contracts per PROJECT.md §4.8, §5.11, §7.3, and FR-F3-001..012."""

from typing import Literal

from pydantic import Field

from backend.app.contracts.common import StrictContractModel

TradeSide = Literal["BUY", "SELL"]


class ColumnMapping(StrictContractModel):
    """Explicit mapping from raw CSV headers to canonical trade fields."""

    date: str
    symbol: str
    side: str
    quantity: str
    price: str
    fees: str | None = None
    charges: str | None = None
    exchange: str | None = None
    segment: str | None = None
    marker: str | None = None


class Trade(StrictContractModel):
    """Single trade execution record."""

    date: str
    symbol: str
    side: TradeSide
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    fees: float | None = None
    charges: float | None = None
    exchange: str | None = None
    segment: str | None = None
    marker: str | None = None


class TradeLog(StrictContractModel):
    """Container for parsed trades and retention metadata."""

    trades: list[Trade]
    total_trades: int
    symbols: list[str]
    start_date: str
    end_date: str
    consent_given: bool = False
    is_retained: bool = False
    is_synthetic_demo: bool = False
    synthetic_marker: str | None = None


class Position(StrictContractModel):
    """Open or closed position summary for a single instrument."""

    symbol: str
    quantity: float
    average_buy_price: float
    realized_pnl: float
    current_price: float | None = None
    current_value: float | None = None
    unrealized_pnl: float | None = None


class Portfolio(StrictContractModel):
    """Aggregated portfolio positions and valuations."""

    positions: list[Position]
    cash_balance: float = 0.0
    total_cost: float
    total_market_value: float
    total_realized_pnl: float
    total_unrealized_pnl: float


class BenchmarkReplay(StrictContractModel):
    """Cash flow replay into a benchmark series."""

    benchmark_name: str
    terminal_value: float
    xirr: float | None = None
    partial_shortfall: bool = False


class ProcessMetrics(StrictContractModel):
    """Execution and decision process metrics."""

    concentration_hhi: float
    turnover: float
    disposition_effect: dict[str, float]
    max_drawdown: float
    process_label: str | None = None


class InstitutionalMetrics(StrictContractModel):
    """Institutional relative performance metrics."""

    beta: float
    alpha: float
    tracking_error: float
    information_ratio: float


class DecisionReview(StrictContractModel):
    """Complete Feature 3 decision review output."""

    portfolio: Portfolio
    portfolio_xirr: float | None = None
    benchmark_replays: list[BenchmarkReplay]
    process_metrics: ProcessMetrics
    institutional_metrics: InstitutionalMetrics | None = None
    review_text: str
    disclaimer: str
    parameters_used: dict[str, float | int | bool | str]
    is_synthetic_demo: bool = False
    synthetic_label: str | None = None
