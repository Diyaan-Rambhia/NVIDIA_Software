"""Portfolio and trade contracts per PROJECT.md §4.8, §7.3, and FR-F3-001."""

from typing import Literal

from pydantic import Field

from backend.app.contracts.common import StrictContractModel

TradeSide = Literal["BUY", "SELL"]


class Trade(StrictContractModel):
    """Single trade per PROJECT.md §4.8, §7.3, and FR-F3-001."""

    date: str
    symbol: str
    side: TradeSide
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    fees: float | None = None
    charges: float | None = None
    exchange: str | None = None
    segment: str | None = None
