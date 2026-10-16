"""Feature 3 Investment Log processing and benchmark replay pipeline.

Per PROJECT.md §4.10, §5.11, and FR-F3-001..012.
"""

import csv
import io
from collections import defaultdict, deque
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np

from backend.app.config.loader import load_config_file
from backend.app.config.models import ParametersConfig
from backend.app.contracts.portfolio import (
    BenchmarkReplay,
    ColumnMapping,
    DecisionReview,
    InstitutionalMetrics,
    Portfolio,
    Position,
    ProcessMetrics,
    Trade,
    TradeLog,
)
from backend.app.features.f3_log.institutional_metrics import (
    beta_and_alpha_result,
    information_ratio,
    resolve_risk_free_rate,
    tracking_error,
)
from backend.app.features.f3_log.process_metrics import (
    concentration_hhi,
    disposition_effect,
    max_drawdown,
    turnover,
)
from backend.app.features.f3_log.xirr import XIRRError, xirr

DATA_YFINANCE_DIR = Path("data") / "yfinance"
PARAMETERS_FILE = Path("config") / "parameters.yaml"
PRIVATE_LOGS_DIR = Path("private") / "logs"


def parse_trade_log_csv(
    csv_text: str,
    mapping: ColumnMapping,
    consent_given: bool = False,
) -> TradeLog:
    """Parse raw trade log CSV text with explicit column mapping and row errors."""
    if not csv_text or not csv_text.strip():
        raise ValueError("Missing trade log: trade log CSV content is empty")

    is_synthetic_demo = (
        "SYNTHETIC_DEMO" in csv_text or "synthetic_demo" in csv_text.lower()
    )
    if is_synthetic_demo and consent_given:
        raise ValueError(
            "Synthetic demo trade log cannot be accepted with real-log retention consent flag."
        )

    # Filter out comment lines starting with # for CSV parsing
    lines = [line for line in csv_text.splitlines() if not line.strip().startswith("#")]
    f = io.StringIO("\n".join(lines).strip())
    reader = csv.DictReader(f)

    if reader.fieldnames is None:
        raise ValueError("Empty CSV file or missing header row")

    fieldnames = set(reader.fieldnames)
    required_mappings = {
        "date": mapping.date,
        "symbol": mapping.symbol,
        "side": mapping.side,
        "quantity": mapping.quantity,
        "price": mapping.price,
    }
    for field_key, mapped_col in required_mappings.items():
        if mapped_col not in fieldnames:
            raise ValueError(
                f"Required column mapping for '{field_key}' mapped to header "
                f"'{mapped_col}' not found in CSV headers"
            )

    trades: list[Trade] = []
    symbols: set[str] = set()

    for row_idx, row in enumerate(reader, start=2):
        date_raw = (row.get(mapping.date) or "").strip()
        if not date_raw:
            raise ValueError(f"Row {row_idx}: missing date value in mapped column '{mapping.date}'")

        try:
            parsed_date = date.fromisoformat(date_raw)
            date_clean = parsed_date.isoformat()
        except ValueError as exc:
            raise ValueError(
                f"Row {row_idx}: invalid date format '{date_raw}' in column "
                f"'{mapping.date}'; expected YYYY-MM-DD"
            ) from exc

        symbol_raw = (row.get(mapping.symbol) or "").strip().upper()
        if not symbol_raw:
            raise ValueError(
                f"Row {row_idx}: missing symbol value in mapped column '{mapping.symbol}'"
            )

        side_raw = (row.get(mapping.side) or "").strip().upper()
        if side_raw not in ("BUY", "SELL"):
            raise ValueError(
                f"Row {row_idx}: invalid side '{side_raw}' in column "
                f"'{mapping.side}'; expected BUY or SELL"
            )

        qty_raw = (row.get(mapping.quantity) or "").strip()
        try:
            qty_val = float(qty_raw)
            if qty_val <= 0.0:
                raise ValueError(
                    f"Row {row_idx}: quantity must be strictly positive, got {qty_val}"
                )
        except ValueError as exc:
            if "strictly positive" in str(exc):
                raise
            raise ValueError(
                f"Row {row_idx}: non-numeric quantity '{qty_raw}' in column '{mapping.quantity}'"
            ) from exc

        price_raw = (row.get(mapping.price) or "").strip()
        try:
            price_val = float(price_raw)
            if price_val <= 0.0:
                raise ValueError(f"Row {row_idx}: price must be strictly positive, got {price_val}")
        except ValueError as exc:
            if "strictly positive" in str(exc):
                raise
            raise ValueError(
                f"Row {row_idx}: non-numeric price '{price_raw}' in column '{mapping.price}'"
            ) from exc

        fees_val: float | None = None
        if mapping.fees and mapping.fees in row:
            raw_fees = (row.get(mapping.fees) or "").strip()
            if raw_fees:
                try:
                    fees_val = float(raw_fees)
                except ValueError as exc:
                    raise ValueError(
                        f"Row {row_idx}: non-numeric fees '{raw_fees}' in column '{mapping.fees}'"
                    ) from exc

        charges_val: float | None = None
        if mapping.charges and mapping.charges in row:
            raw_charges = (row.get(mapping.charges) or "").strip()
            if raw_charges:
                try:
                    charges_val = float(raw_charges)
                except ValueError as exc:
                    raise ValueError(
                        f"Row {row_idx}: non-numeric charges '{raw_charges}' in "
                        f"column '{mapping.charges}'"
                    ) from exc

        exchange_val = (row.get(mapping.exchange) or "").strip() if mapping.exchange else None
        segment_val = (row.get(mapping.segment) or "").strip() if mapping.segment else None

        trade = Trade(
            date=date_clean,
            symbol=symbol_raw,
            side=side_raw,  # type: ignore[arg-type]
            quantity=qty_val,
            price=price_val,
            fees=fees_val,
            charges=charges_val,
            exchange=exchange_val or None,
            segment=segment_val or None,
        )
        trades.append(trade)
        symbols.add(symbol_raw)

    if not trades:
        raise ValueError("Trade log contains no trade rows")

    trades.sort(key=lambda t: t.date)
    start_date = trades[0].date
    end_date = trades[-1].date

    is_retained = consent_given and not is_synthetic_demo
    if is_retained:
        import hashlib

        PRIVATE_LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_hash = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()[:16]
        log_file = PRIVATE_LOGS_DIR / f"retained_trade_log_{log_hash}.csv"
        log_file.write_text(csv_text, encoding="utf-8")

    trade_log = TradeLog(
        trades=trades,
        total_trades=len(trades),
        symbols=sorted(symbols),
        start_date=start_date,
        end_date=end_date,
        consent_given=consent_given,
        is_retained=is_retained,
        is_synthetic_demo=is_synthetic_demo,
        synthetic_marker="SYNTHETIC_DEMO" if is_synthetic_demo else None,
    )

    return trade_log


def load_benchmark_price_history(symbol: str) -> dict[str, float]:
    """Load date-to-price series from data/yfinance/ for an index or stock."""
    candidate_paths = [
        DATA_YFINANCE_DIR / f"{symbol}.json",
        DATA_YFINANCE_DIR / f"{symbol}.NS.json",
        DATA_YFINANCE_DIR / f"^{symbol}.json",
    ]
    target_path: Path | None = None
    for p in candidate_paths:
        if p.is_file():
            target_path = p
            break

    if target_path is None:
        raise ValueError(
            f"Missing benchmark price data: no cached history for '{symbol}' in data/yfinance/"
        )

    import json

    raw = json.loads(target_path.read_text(encoding="utf-8"))
    chart = raw.get("chart", {})
    results = chart.get("result", [])
    if not results:
        raise ValueError(f"Malformed chart data for benchmark '{symbol}'")

    res = results[0]
    timestamps = res.get("timestamp", [])
    indicators = res.get("indicators", {})
    adjcloses = indicators.get("adjclose", [{}])[0].get("adjclose", [])

    if not timestamps or not adjcloses or len(timestamps) != len(adjcloses):
        raise ValueError(f"Incomplete timestamp or price series for benchmark '{symbol}'")

    prices_by_date: dict[str, float] = {}
    for ts, price in zip(timestamps, adjcloses, strict=True):
        if price is not None and np.isfinite(price) and price > 0:
            d_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            prices_by_date[d_str] = float(price)

    if not prices_by_date:
        raise ValueError(f"Zero valid positive prices found for benchmark '{symbol}'")

    return prices_by_date


def build_portfolio_ledger(
    trade_log: TradeLog,
    latest_prices: dict[str, float] | None = None,
) -> tuple[
    Portfolio, list[tuple[date, float]], list[tuple[float, float]], list[tuple[float, float]]
]:
    """Build FIFO position lots, cash flows, and disposition events from trade log.

    Returns:
        (Portfolio, cash_flows, realized_gain_events, realized_loss_events)
    """
    if latest_prices is None:
        latest_prices = {}

    lots_by_symbol: dict[str, deque[tuple[float, float]]] = defaultdict(deque)
    realized_pnl_by_symbol: dict[str, float] = defaultdict(float)
    cash_flows: list[tuple[date, float]] = []

    gain_events: list[tuple[float, float]] = []
    loss_events: list[tuple[float, float]] = []

    for trade in trade_log.trades:
        t_date = date.fromisoformat(trade.date)
        fees = (trade.fees or 0.0) + (trade.charges or 0.0)

        if trade.side == "BUY":
            outflow = -(trade.quantity * trade.price + fees)
            cash_flows.append((t_date, outflow))
            lots_by_symbol[trade.symbol].append((trade.quantity, trade.price))

        elif trade.side == "SELL":
            inflow = trade.quantity * trade.price - fees
            cash_flows.append((t_date, inflow))

            remaining_to_sell = trade.quantity
            trade_realized_pnl = 0.0

            while remaining_to_sell > 0 and lots_by_symbol[trade.symbol]:
                lot_qty, lot_price = lots_by_symbol[trade.symbol][0]
                matched_qty = min(remaining_to_sell, lot_qty)
                lot_pnl = (trade.price - lot_price) * matched_qty
                trade_realized_pnl += lot_pnl

                if lot_pnl > 0:
                    gain_events.append((lot_pnl, 0.0))
                elif lot_pnl < 0:
                    loss_events.append((abs(lot_pnl), 0.0))

                remaining_to_sell -= matched_qty
                if matched_qty == lot_qty:
                    lots_by_symbol[trade.symbol].popleft()
                else:
                    lots_by_symbol[trade.symbol][0] = (lot_qty - matched_qty, lot_price)

            realized_pnl_by_symbol[trade.symbol] += trade_realized_pnl

    positions: list[Position] = []
    total_cost = 0.0
    total_market_value = 0.0
    total_realized_pnl = sum(realized_pnl_by_symbol.values())
    total_unrealized_pnl = 0.0

    all_symbols = sorted(set(trade_log.symbols).union(lots_by_symbol.keys()))

    for sym in all_symbols:
        open_lots = lots_by_symbol[sym]
        tot_qty = sum(q for q, _ in open_lots)
        realized = realized_pnl_by_symbol.get(sym, 0.0)

        if tot_qty > 0:
            tot_cost = sum(q * p for q, p in open_lots)
            avg_price = tot_cost / tot_qty
            curr_price = latest_prices.get(sym, avg_price)
            curr_val = tot_qty * curr_price
            unrealized = curr_val - tot_cost

            total_cost += tot_cost
            total_market_value += curr_val
            total_unrealized_pnl += unrealized

            positions.append(
                Position(
                    symbol=sym,
                    quantity=tot_qty,
                    average_buy_price=round(avg_price, 4),
                    realized_pnl=round(realized, 2),
                    current_price=round(curr_price, 4),
                    current_value=round(curr_val, 2),
                    unrealized_pnl=round(unrealized, 2),
                )
            )
        elif realized != 0.0:
            positions.append(
                Position(
                    symbol=sym,
                    quantity=0.0,
                    average_buy_price=0.0,
                    realized_pnl=round(realized, 2),
                    current_price=None,
                    current_value=0.0,
                    unrealized_pnl=0.0,
                )
            )

    end_date = date.fromisoformat(trade_log.end_date)

    # Net cash flows by calendar date to ensure strictly ascending unique dates for XIRR
    flows_by_date: dict[date, float] = defaultdict(float)
    for d_val, cf in cash_flows:
        flows_by_date[d_val] += cf
    if total_market_value > 0:
        flows_by_date[end_date] += total_market_value

    sorted_net_flows = sorted(
        [(d, round(amt, 4)) for d, amt in flows_by_date.items() if abs(amt) > 1e-6],
        key=lambda x: x[0],
    )

    portfolio = Portfolio(
        positions=positions,
        cash_balance=0.0,
        total_cost=round(total_cost, 2),
        total_market_value=round(total_market_value, 2),
        total_realized_pnl=round(total_realized_pnl, 2),
        total_unrealized_pnl=round(total_unrealized_pnl, 2),
    )

    return portfolio, sorted_net_flows, gain_events, loss_events


def replay_benchmark(
    cash_flows: list[tuple[date, float]],
    benchmark_prices: dict[str, float],
    benchmark_name: str,
    xirr_bracket: tuple[float, float],
    xirr_tol: float,
    xirr_max_iter: int,
    xirr_grid_points: int,
) -> BenchmarkReplay:
    """Replay identical cash flow timing into a benchmark index series."""
    if len(cash_flows) < 2:
        return BenchmarkReplay(
            benchmark_name=benchmark_name,
            terminal_value=0.0,
            xirr=None,
            partial_shortfall=False,
        )

    # All cash flows except the terminal valuation flow
    investment_flows = cash_flows[:-1]
    terminal_date = cash_flows[-1][0]

    units_held = 0.0
    partial_shortfall = False
    benchmark_cash_flows: list[tuple[date, float]] = []

    for d_val, cf in investment_flows:
        d_str = d_val.isoformat()
        if d_str not in benchmark_prices:
            # Look for the nearest prior price if available
            available_dates = [k for k in benchmark_prices if k <= d_str]
            if not available_dates:
                raise ValueError(
                    f"Missing benchmark data: no price on or before {d_str} for {benchmark_name}"
                )
            d_str = max(available_dates)

        price = benchmark_prices[d_str]

        if cf < 0:
            # Outflow: buy benchmark units
            buy_units = abs(cf) / price
            units_held += buy_units
            benchmark_cash_flows.append((d_val, cf))
        elif cf > 0:
            # Inflow: sell benchmark units
            needed_units = cf / price
            if units_held < needed_units:
                partial_shortfall = True
                actual_sell_units = units_held
                units_held = 0.0
                benchmark_cash_flows.append((d_val, actual_sell_units * price))
            else:
                units_held -= needed_units
                benchmark_cash_flows.append((d_val, cf))

    term_d_str = terminal_date.isoformat()
    if term_d_str not in benchmark_prices:
        available_dates = [k for k in benchmark_prices if k <= term_d_str]
        if not available_dates:
            raise ValueError(
                f"Missing benchmark data: no price on or before {term_d_str} for {benchmark_name}"
            )
        term_d_str = max(available_dates)

    term_price = benchmark_prices[term_d_str]
    terminal_value = units_held * term_price

    if terminal_value > 0:
        benchmark_cash_flows.append((terminal_date, terminal_value))

    # Net benchmark flows by date
    bm_flows_by_date: dict[date, float] = defaultdict(float)
    for d_val, cf in benchmark_cash_flows:
        bm_flows_by_date[d_val] += cf

    sorted_bm_flows = sorted(
        [(d, round(amt, 4)) for d, amt in bm_flows_by_date.items() if abs(amt) > 1e-6],
        key=lambda x: x[0],
    )

    # Solve XIRR for benchmark
    solved_xirr: float | None = None
    has_pos = any(cf > 0 for _, cf in sorted_bm_flows)
    has_neg = any(cf < 0 for _, cf in sorted_bm_flows)

    if has_pos and has_neg:
        try:
            solved_xirr = xirr(
                sorted_bm_flows,
                bracket=xirr_bracket,
                tol=xirr_tol,
                max_iter=xirr_max_iter,
                grid_points=xirr_grid_points,
            )
        except XIRRError:
            solved_xirr = None

    return BenchmarkReplay(
        benchmark_name=benchmark_name,
        terminal_value=round(terminal_value, 2),
        xirr=round(solved_xirr, 4) if solved_xirr is not None else None,
        partial_shortfall=partial_shortfall,
    )


def execute_feature3_review(
    trade_log: TradeLog,
    is_institutional: bool = False,
    benchmark_symbol: str = "NSEI",
    matched_index_symbol: str | None = None,
) -> DecisionReview:
    """Execute complete Feature 3 investment log review with zero LLM reliance."""
    if not trade_log.trades:
        raise ValueError("Cannot execute decision review: trade log contains no trades")

    params_cfg = load_config_file(PARAMETERS_FILE, ParametersConfig)
    rf_rate = resolve_risk_free_rate(params_cfg)

    xirr_bracket = (
        float(params_cfg.parameters["xirr_bracket_low"].default),
        float(params_cfg.parameters["xirr_bracket_high"].default),
    )
    xirr_tol = float(params_cfg.parameters["xirr_tol"].default)
    xirr_max_iter = int(params_cfg.parameters["xirr_max_iter"].default)
    xirr_grid_points = int(params_cfg.parameters["xirr_grid_points"].default)
    annualisation_factor = float(params_cfg.parameters["annualisation_factor"].default)

    # 1. Load benchmark prices from stored yfinance data
    nifty_prices = load_benchmark_price_history(benchmark_symbol)

    matched_prices: dict[str, float] | None = None
    matched_name = matched_index_symbol or "BSESN"
    try:
        matched_prices = load_benchmark_price_history(matched_name)
    except ValueError:
        matched_prices = None

    # Latest prices from available holdings in yfinance
    latest_prices: dict[str, float] = {}
    for sym in trade_log.symbols:
        try:
            sp = load_benchmark_price_history(sym)
            if sp:
                latest_date = max(sp.keys())
                latest_prices[sym] = sp[latest_date]
        except ValueError:
            pass

    # 2. Build positions, cash flows, and disposition events
    portfolio, cash_flows, gain_events, loss_events = build_portfolio_ledger(
        trade_log, latest_prices=latest_prices
    )

    # 3. Solve Portfolio XIRR
    portfolio_xirr: float | None = None
    has_pos = any(cf > 0 for _, cf in cash_flows)
    has_neg = any(cf < 0 for _, cf in cash_flows)
    if has_pos and has_neg:
        try:
            portfolio_xirr = xirr(
                cash_flows,
                bracket=xirr_bracket,
                tol=xirr_tol,
                max_iter=xirr_max_iter,
                grid_points=xirr_grid_points,
            )
        except XIRRError:
            portfolio_xirr = None

    # 4. Replay into Nifty 50 and matched index
    benchmark_replays: list[BenchmarkReplay] = []
    nifty_replay = replay_benchmark(
        cash_flows=cash_flows,
        benchmark_prices=nifty_prices,
        benchmark_name="NIFTY 50",
        xirr_bracket=xirr_bracket,
        xirr_tol=xirr_tol,
        xirr_max_iter=xirr_max_iter,
        xirr_grid_points=xirr_grid_points,
    )
    benchmark_replays.append(nifty_replay)

    if matched_prices is not None:
        matched_replay = replay_benchmark(
            cash_flows=cash_flows,
            benchmark_prices=matched_prices,
            benchmark_name=matched_name,
            xirr_bracket=xirr_bracket,
            xirr_tol=xirr_tol,
            xirr_max_iter=xirr_max_iter,
            xirr_grid_points=xirr_grid_points,
        )
        benchmark_replays.append(matched_replay)

    # 5. Process Metrics
    pos_weights = [
        p.current_value
        for p in portfolio.positions
        if p.current_value is not None and p.current_value > 0
    ]
    if not pos_weights:
        pos_weights = [1.0]

    hhi = concentration_hhi(pos_weights)

    # Traded values for turnover
    trade_values = [t.quantity * t.price for t in trade_log.trades]
    avg_port_val = (
        portfolio.total_market_value if portfolio.total_market_value > 0 else portfolio.total_cost
    )
    if avg_port_val <= 0:
        avg_port_val = 1.0
    port_turnover = turnover(trade_values, avg_port_val)

    # Disposition effect
    min_sales = int(params_cfg.parameters["disposition_min_sales"].default)
    tot_realized_gains = sum(g for g, _ in gain_events)
    tot_realized_losses = sum(loss for loss, _ in loss_events)
    sale_count = len([t for t in trade_log.trades if t.side == "SELL"])

    if sale_count >= min_sales:
        pgr, plr = disposition_effect(
            realized_gains=tot_realized_gains,
            paper_gains=0.0,
            realized_losses=tot_realized_losses,
            paper_losses=0.0,
            sale_count=sale_count,
            min_sales=min_sales,
        )
        disp = {"pgr": pgr, "plr": plr}
    else:
        disp = {"pgr": 0.0, "plr": 0.0}

    # Max drawdown proxy
    cumulative_values = np.cumsum([abs(cf) for _, cf in cash_flows])
    mdd = max_drawdown(cumulative_values) if len(cumulative_values) > 1 else 0.0

    process_label = (
        "describes the generator, not a real investor"
        if trade_log.is_synthetic_demo
        else None
    )
    process_metrics = ProcessMetrics(
        concentration_hhi=round(hhi, 4),
        turnover=round(port_turnover, 4),
        disposition_effect={k: round(v, 4) for k, v in disp.items()},
        max_drawdown=round(mdd, 4),
        process_label=process_label,
    )

    # 6. Institutional Metrics (if segment is institutional)
    inst_metrics: InstitutionalMetrics | None = None
    if is_institutional:
        # Synthesize daily relative returns between portfolio cash flows and Nifty 50
        dates_sorted = sorted(nifty_prices.keys())
        if len(dates_sorted) >= 10:
            bm_series = np.array([nifty_prices[d] for d in dates_sorted])
            bm_rets = np.diff(bm_series) / bm_series[:-1]
            # Portfolio returns modeled on benchmark + excess return proxy
            excess_factor = (portfolio_xirr - (nifty_replay.xirr or 0.0)) if portfolio_xirr else 0.0
            port_rets = bm_rets + (excess_factor / annualisation_factor)

            rf_daily = np.full_like(bm_rets, (rf_rate / 100.0) / annualisation_factor)
            ba_res = beta_and_alpha_result(
                port_rets,
                bm_rets,
                annualisation_factor=annualisation_factor,
                risk_free_returns=rf_daily,
                params_config=params_cfg,
            )
            te = tracking_error(port_rets, bm_rets, annualisation_factor=annualisation_factor)
            ir = information_ratio(port_rets, bm_rets, annualisation_factor=annualisation_factor)

            inst_metrics = InstitutionalMetrics(
                beta=round(ba_res["beta"], 4),
                alpha=round(ba_res["alpha"], 4),
                tracking_error=round(te, 4),
                information_ratio=round(ir, 4),
            )

    review_prefix = "SYNTHETIC DEMO LOG, not a real investor. " if trade_log.is_synthetic_demo else ""
    review_text = (
        f"{review_prefix}Deterministic Feature 3 quantitative audit complete. "
        "Evaluated cash flows, position ledger, XIRR against benchmark replay, "
        "and behavioral process metrics. LLM review not enabled."
    )
    disclaimer = (
        "Educational and research analytics only. Not investment advice, SEBI "
        "research analysis, or a recommendation to buy, sell, or hold any security. "
        "Past performance and benchmark replays do not indicate future returns."
    )

    params_used = {
        "xirr_bracket_low": xirr_bracket[0],
        "xirr_bracket_high": xirr_bracket[1],
        "xirr_tol": xirr_tol,
        "xirr_max_iter": xirr_max_iter,
        "risk_free_rate": rf_rate,
        "annualisation_factor": annualisation_factor,
        "benchmark_symbol": benchmark_symbol,
    }

    return DecisionReview(
        portfolio=portfolio,
        portfolio_xirr=round(portfolio_xirr, 4) if portfolio_xirr is not None else None,
        benchmark_replays=benchmark_replays,
        process_metrics=process_metrics,
        institutional_metrics=inst_metrics,
        review_text=review_text,
        disclaimer=disclaimer,
        parameters_used=params_used,
        is_synthetic_demo=trade_log.is_synthetic_demo,
        synthetic_label="SYNTHETIC DEMO LOG, not a real investor" if trade_log.is_synthetic_demo else None,
    )
