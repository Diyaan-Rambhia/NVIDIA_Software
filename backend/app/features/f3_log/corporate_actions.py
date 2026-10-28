"""Feature 3 Corporate Actions processing and lot adjustment module.

Per PROJECT.md §4.10, §5.11, and FR-F3-003.
Handles stock splits, bonus share distributions, and cash dividends
adjusting FIFO position lots and portfolio cash flows before metrics calculation.
"""

import csv
import io
from collections import deque
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

CorporateActionType = Literal["SPLIT", "BONUS", "DIVIDEND"]


@dataclass(frozen=True)
class CorporateAction:
    """Single corporate action event."""

    date: str
    symbol: str
    action_type: CorporateActionType
    ratio_numerator: float = 1.0
    ratio_denominator: float = 1.0
    dividend_per_share: float = 0.0

    def get_adjustment_factor(self) -> float:
        """Calculate quantity multiplier factor for lot adjustment."""
        if self.action_type == "SPLIT":
            if self.ratio_denominator <= 0.0:
                raise ValueError("Split ratio denominator must be strictly positive")
            return self.ratio_numerator / self.ratio_denominator
        elif self.action_type == "BONUS":
            if self.ratio_denominator <= 0.0:
                raise ValueError("Bonus ratio denominator must be strictly positive")
            return (self.ratio_numerator + self.ratio_denominator) / self.ratio_denominator
        elif self.action_type == "DIVIDEND":
            return 1.0
        raise ValueError(f"Unknown corporate action type: {self.action_type}")


def parse_corporate_actions_csv(csv_text: str) -> list[CorporateAction]:
    """Parse corporate actions CSV table."""
    if not csv_text or not csv_text.strip():
        return []

    lines = [line for line in csv_text.splitlines() if not line.strip().startswith("#")]
    reader = csv.DictReader(io.StringIO("\n".join(lines).strip()))
    if reader.fieldnames is None:
        return []

    actions: list[CorporateAction] = []
    for row_idx, row in enumerate(reader, start=2):
        action_date = (row.get("date") or "").strip()
        symbol = (row.get("symbol") or "").strip().upper()
        act_type_raw = (row.get("action_type") or "").strip().upper()

        if not action_date or not symbol or not act_type_raw:
            continue

        if act_type_raw not in ("SPLIT", "BONUS", "DIVIDEND"):
            raise ValueError(f"Row {row_idx}: unsupported action_type '{act_type_raw}'")

        num = float(row.get("ratio_numerator") or 1.0)
        den = float(row.get("ratio_denominator") or 1.0)
        div = float(row.get("dividend_per_share") or 0.0)

        actions.append(
            CorporateAction(
                date=action_date,
                symbol=symbol,
                action_type=act_type_raw,  # type: ignore[arg-type]
                ratio_numerator=num,
                ratio_denominator=den,
                dividend_per_share=div,
            )
        )

    actions.sort(key=lambda a: a.date)
    return actions


def adjust_lots_for_corporate_action(
    open_lots: deque[tuple[float, float]],
    action: CorporateAction,
) -> tuple[deque[tuple[float, float]], float]:
    """Adjust open FIFO lots for a corporate action.

    Returns:
        (adjusted_lots, cash_inflow_generated)
    """
    if action.action_type == "DIVIDEND":
        total_open_qty = sum(qty for qty, _ in open_lots)
        cash_flow = total_open_qty * action.dividend_per_share
        return open_lots, cash_flow

    factor = action.get_adjustment_factor()
    if factor <= 0.0:
        raise ValueError(f"Invalid adjustment factor {factor} for action {action}")

    new_lots: deque[tuple[float, float]] = deque()
    for lot_qty, lot_price in open_lots:
        adjusted_qty = lot_qty * factor
        adjusted_price = lot_price / factor
        new_lots.append((adjusted_qty, adjusted_price))

    return new_lots, 0.0
