"""Consistency rule engine R0-R7 per PROJECT.md §5.10 and PROGRESS.md A2.13."""

from typing import Any, Literal

from backend.app.config.loader import ParameterError
from backend.app.contracts.common import StrictContractModel
from backend.app.contracts.filings import Claim, FilingMetric

RuleStatus = Literal["pass", "flag", "not_applicable"]
RuleSeverity = Literal["none", "low", "low_medium", "medium", "high"]


class RuleResult(StrictContractModel):
    """Structured result of evaluating a consistency rule."""

    rule_id: str
    status: RuleStatus
    severity: RuleSeverity
    evidence: dict[str, Any]
    reason: str | None = None


# Descriptor lexicons aligned with config/lexicon.yaml and finance/04
POSITIVE_DIRECTION_WORDS = {
    "grew",
    "growth",
    "increased",
    "increase",
    "expanded",
    "expansion",
    "improved",
    "improvement",
    "positive",
    "up",
}

NEGATIVE_DIRECTION_WORDS = {
    "declined",
    "decline",
    "contracted",
    "contraction",
    "de-grew",
    "fell",
    "fall",
    "dropped",
    "negative",
    "down",
}

STRONG_MAGNITUDE_WORDS = {
    "strong",
    "robust",
    "record",
    "all-time high",
    "outstanding",
    "exceptional",
    "stellar",
    "unprecedented",
    "double-digit",
}

TREND_WORDS = {
    "accelerating",
    "accelerated",
    "improving momentum",
    "gained momentum",
    "sequential improvement",
    "picked up",
}

MARGIN_WORDS = {
    "margin expansion",
    "expansion",
    "improved profitability",
    "margin improvement",
}

CASH_WORDS = {
    "strong cash generation",
    "robust cash",
    "healthy cash flow",
    "strong cash flow",
}

WORKING_CAPITAL_WORDS = {
    "disciplined inventory",
    "healthy collections",
    "working capital discipline",
    "disciplined working capital",
    "efficient collections",
}

CAUTIOUS_WORDS = {
    "muted",
    "soft",
    "subdued",
    "challenging",
    "headwinds",
    "moderated",
}


def validate_alignment(
    claim: Claim,
    metric: FilingMetric,
    claimed_unit: str | None = None,
    claim_metric_basis: str | None = None,
) -> None:
    """Validate fiscal period, unit, and reporting basis alignment.

    Raises
    ------
    ParameterError
        If fiscal period, unit, or standalone/consolidated basis mismatch.
    """
    if claim.period != metric.fiscal_period:
        raise ParameterError(
            field="period",
            value=claim.period,
            allowed_range=metric.fiscal_period,
            reason=(
                f"Fiscal period mismatch: claim ({claim.period}) != metric ({metric.fiscal_period})"
            ),
        )
    if claimed_unit is not None and claimed_unit != metric.unit:
        raise ParameterError(
            field="unit",
            value=claimed_unit,
            allowed_range=metric.unit,
            reason=f"Unit mismatch: claim unit ({claimed_unit}) != metric unit ({metric.unit})",
        )
    if claim_metric_basis is not None and claim_metric_basis != metric.basis:
        raise ParameterError(
            field="basis",
            value=claim_metric_basis,
            allowed_range=metric.basis,
            reason=(
                f"Basis mismatch: claim basis ({claim_metric_basis}) "
                f"!= metric basis ({metric.basis})"
            ),
        )


def _check_adjusted_guard(claim: Claim, rule_id: str) -> RuleResult | None:
    """FR-F2-005 adjusted-figure guard: suppresses non-GAAP / adjusted claims."""
    if claim.basis in ("adjusted", "constant-currency"):
        return RuleResult(
            rule_id=rule_id,
            status="not_applicable",
            severity="none",
            evidence={"claim_basis": claim.basis},
            reason="Adjusted or constant-currency figure guard applies",
        )
    return None


def assert_not_same_field(stated_field: str | None, source_field: str | None) -> None:
    """Guard against comparing a filed value with itself.

    Raises ValueError if stated_value source and metric source field are identical.
    """
    if stated_field and source_field and stated_field.strip().lower() == source_field.strip().lower():
        raise ValueError(
            f"Invalid comparison: stated_value source '{stated_field}' cannot be the same field as filed metric '{source_field}'"
        )


def evaluate_r0_stated_number(
    claim: Claim | None,
    metric: FilingMetric,
    stated_value: float | None = None,
    tolerance_pp: float = 0.5,
    claimed_unit: str | None = None,
    claim_metric_basis: str | None = None,
    stated_value_source: str | None = None,
) -> RuleResult:
    """R0: Management states a specific figure on a reported basis."""
    if stated_value_source is not None:
        assert_not_same_field(stated_value_source, metric.metric)

    if claim is None or not getattr(claim, "quote", "").strip():
        return RuleResult(
            rule_id="R0",
            status="not_applicable",
            severity="none",
            evidence={},
            reason="no management claim text available",
        )

    validate_alignment(claim, metric, claimed_unit, claim_metric_basis)
    guard = _check_adjusted_guard(claim, "R0")
    if guard is not None:
        return guard

    if stated_value is None:
        return RuleResult(
            rule_id="R0",
            status="not_applicable",
            severity="none",
            evidence={},
            reason="no management claim text available",
        )

    diff = abs(stated_value - metric.value)
    evidence = {
        "stated_value": stated_value,
        "filed_value": metric.value,
        "diff": diff,
        "tolerance_pp": tolerance_pp,
    }
    if diff > tolerance_pp:
        return RuleResult(
            rule_id="R0",
            status="flag",
            severity="high",
            evidence=evidence,
            reason=(
                f"Stated figure {stated_value} differs from filed figure "
                f"{metric.value} by {diff:.2f} (tolerance {tolerance_pp})"
            ),
        )
    return RuleResult(
        rule_id="R0",
        status="pass",
        severity="none",
        evidence=evidence,
    )


def evaluate_r1_direction(
    claim: Claim | None,
    metric: FilingMetric,
    filing_change: float | None = None,
    claimed_unit: str | None = None,
    claim_metric_basis: str | None = None,
) -> RuleResult:
    """R1: Direction of change (rose/grew vs declined/fell)."""
    if claim is None or not getattr(claim, "quote", "").strip():
        return RuleResult(
            rule_id="R1",
            status="not_applicable",
            severity="none",
            evidence={},
            reason="no management claim text available",
        )

    validate_alignment(claim, metric, claimed_unit, claim_metric_basis)
    guard = _check_adjusted_guard(claim, "R1")
    if guard is not None:
        return guard

    direction_norm = claim.direction.lower().strip()
    if filing_change is None:
        return RuleResult(
            rule_id="R1",
            status="not_applicable",
            severity="none",
            evidence={"direction": claim.direction},
            reason="Filing change value not provided",
        )

    evidence = {"direction": claim.direction, "filing_change": filing_change}

    if direction_norm in POSITIVE_DIRECTION_WORDS:
        if filing_change <= 0.0:
            return RuleResult(
                rule_id="R1",
                status="flag",
                severity="high",
                evidence=evidence,
                reason=f"Claimed positive growth but filed change was {filing_change}",
            )
        return RuleResult(rule_id="R1", status="pass", severity="none", evidence=evidence)

    if direction_norm in NEGATIVE_DIRECTION_WORDS:
        if filing_change >= 0.0:
            return RuleResult(
                rule_id="R1",
                status="flag",
                severity="high",
                evidence=evidence,
                reason=f"Claimed decline but filed change was {filing_change}",
            )
        return RuleResult(rule_id="R1", status="pass", severity="none", evidence=evidence)

    return RuleResult(
        rule_id="R1",
        status="not_applicable",
        severity="none",
        evidence=evidence,
        reason=f"Unrecognized or neutral direction '{claim.direction}'",
    )


def evaluate_r2_magnitude(
    claim: Claim | None,
    metric: FilingMetric,
    growth: float | None = None,
    strong_threshold: float | None = None,
    sector: str | None = None,
    sector_thresholds: dict[str, float] | None = None,
    claimed_unit: str | None = None,
    claim_metric_basis: str | None = None,
) -> RuleResult:
    """R2: Strong-intensity magnitude descriptor on growth."""
    if claim is None or not getattr(claim, "quote", "").strip():
        return RuleResult(
            rule_id="R2",
            status="not_applicable",
            severity="none",
            evidence={},
            reason="no management claim text available",
        )

    validate_alignment(claim, metric, claimed_unit, claim_metric_basis)
    guard = _check_adjusted_guard(claim, "R2")
    if guard is not None:
        return guard

    descriptor_norm = claim.descriptor.lower().strip()
    if descriptor_norm not in STRONG_MAGNITUDE_WORDS:
        return RuleResult(
            rule_id="R2",
            status="not_applicable",
            severity="none",
            evidence={"descriptor": claim.descriptor},
            reason=f"Descriptor '{claim.descriptor}' is not a strong magnitude descriptor",
        )

    is_sector_threshold = False
    if strong_threshold is None:
        if sector and sector_thresholds and sector.lower() in sector_thresholds:
            val = sector_thresholds[sector.lower()]
            if isinstance(val, (int, float)):
                strong_threshold = float(val)
                is_sector_threshold = True
            else:
                return RuleResult(
                    rule_id="R2",
                    status="not_applicable",
                    severity="none",
                    evidence={},
                    reason="threshold pending",
                )
        else:
            return RuleResult(
                rule_id="R2",
                status="not_applicable",
                severity="none",
                evidence={},
                reason="threshold pending",
            )

    if growth is None:
        return RuleResult(
            rule_id="R2",
            status="not_applicable",
            severity="none",
            evidence={"descriptor": claim.descriptor},
            reason="Growth value not provided",
        )

    evidence: dict[str, Any] = {
        "descriptor": claim.descriptor,
        "growth": growth,
        "strong_threshold": strong_threshold,
    }
    if is_sector_threshold:
        evidence["threshold_label"] = "provisional threshold"

    if growth < strong_threshold:
        suffix = " (provisional threshold)" if is_sector_threshold else ""
        return RuleResult(
            rule_id="R2",
            status="flag",
            severity="medium",
            evidence=evidence,
            reason=f"Growth {growth:.4f} is below strong threshold {strong_threshold:.4f}{suffix}",
        )
    return RuleResult(rule_id="R2", status="pass", severity="none", evidence=evidence)


def evaluate_r3_trend(
    claim: Claim | None,
    metric: FilingMetric,
    current_growth: float | None = None,
    prior_growth: float | None = None,
    claimed_unit: str | None = None,
    claim_metric_basis: str | None = None,
) -> RuleResult:
    """R3: Accelerating or improving momentum trend claim."""
    if claim is None or not getattr(claim, "quote", "").strip():
        return RuleResult(
            rule_id="R3",
            status="not_applicable",
            severity="none",
            evidence={},
            reason="no management claim text available",
        )

    validate_alignment(claim, metric, claimed_unit, claim_metric_basis)
    guard = _check_adjusted_guard(claim, "R3")
    if guard is not None:
        return guard

    descriptor_norm = claim.descriptor.lower().strip()
    if descriptor_norm not in TREND_WORDS:
        return RuleResult(
            rule_id="R3",
            status="not_applicable",
            severity="none",
            evidence={"descriptor": claim.descriptor},
            reason=f"Descriptor '{claim.descriptor}' is not a trend descriptor",
        )

    if current_growth is None or prior_growth is None:
        return RuleResult(
            rule_id="R3",
            status="not_applicable",
            severity="none",
            evidence={"descriptor": claim.descriptor},
            reason="Current or prior period growth missing",
        )

    evidence = {"current_growth": current_growth, "prior_growth": prior_growth}
    if current_growth < prior_growth:
        return RuleResult(
            rule_id="R3",
            status="flag",
            severity="medium",
            evidence=evidence,
            reason=(
                f"Current growth {current_growth:.4f} is lower than "
                f"prior period growth {prior_growth:.4f}"
            ),
        )
    return RuleResult(rule_id="R3", status="pass", severity="none", evidence=evidence)


def evaluate_r4_profitability(
    claim: Claim | None,
    metric: FilingMetric,
    margin_change: float | None = None,
    margin_tolerance_bps: int = 20,
    claimed_unit: str | None = None,
    claim_metric_basis: str | None = None,
) -> RuleResult:
    """R4: Margin expansion or improved profitability."""
    if claim is None or not getattr(claim, "quote", "").strip():
        return RuleResult(
            rule_id="R4",
            status="not_applicable",
            severity="none",
            evidence={},
            reason="no management claim text available",
        )

    validate_alignment(claim, metric, claimed_unit, claim_metric_basis)
    guard = _check_adjusted_guard(claim, "R4")
    if guard is not None:
        return guard

    desc_norm = claim.descriptor.lower().strip()
    metric_norm = claim.metric.lower().strip()
    is_margin_claim = (desc_norm in MARGIN_WORDS) or ("margin" in metric_norm)

    if not is_margin_claim:
        return RuleResult(
            rule_id="R4",
            status="not_applicable",
            severity="none",
            evidence={"descriptor": claim.descriptor, "metric": claim.metric},
            reason="Claim is not a margin expansion claim",
        )

    if margin_change is None:
        return RuleResult(
            rule_id="R4",
            status="not_applicable",
            severity="none",
            evidence={},
            reason="Margin change not provided",
        )

    tolerance_fraction = margin_tolerance_bps / 10000.0
    evidence = {
        "margin_change": margin_change,
        "margin_tolerance_bps": margin_tolerance_bps,
        "tolerance_fraction": tolerance_fraction,
    }
    if margin_change < -tolerance_fraction:
        return RuleResult(
            rule_id="R4",
            status="flag",
            severity="high",
            evidence=evidence,
            reason=(
                f"Margin declined by {margin_change:.4f}, exceeding tolerance "
                f"{margin_tolerance_bps} bps"
            ),
        )
    return RuleResult(rule_id="R4", status="pass", severity="none", evidence=evidence)


def evaluate_r5_cash_quality(
    claim: Claim | None,
    metric: FilingMetric,
    ocf_yoy_growth: float | None = None,
    ocf_conversion: float | None = None,
    ocf_conversion_floor: float = 0.5,
    claimed_unit: str | None = None,
    claim_metric_basis: str | None = None,
    is_annual: bool = True,
) -> RuleResult:
    """R5: Strong cash generation claim."""
    if not is_annual:
        return RuleResult(
            rule_id="R5",
            status="not_applicable",
            severity="none",
            evidence={},
            reason="Operating cash flow and working capital rules evaluate only on annual filings",
        )

    if claim is None or not getattr(claim, "quote", "").strip():
        return RuleResult(
            rule_id="R5",
            status="not_applicable",
            severity="none",
            evidence={},
            reason="no management claim text available",
        )

    validate_alignment(claim, metric, claimed_unit, claim_metric_basis)
    guard = _check_adjusted_guard(claim, "R5")
    if guard is not None:
        return guard

    desc_norm = claim.descriptor.lower().strip()
    is_cash_claim = (desc_norm in CASH_WORDS) or ("cash" in claim.metric.lower())

    if not is_cash_claim:
        return RuleResult(
            rule_id="R5",
            status="not_applicable",
            severity="none",
            evidence={"descriptor": claim.descriptor},
            reason="Claim is not a cash quality claim",
        )

    if ocf_yoy_growth is None and ocf_conversion is None:
        return RuleResult(
            rule_id="R5",
            status="not_applicable",
            severity="none",
            evidence={},
            reason="Neither OCF YoY growth nor OCF conversion provided",
        )

    evidence = {
        "ocf_yoy_growth": ocf_yoy_growth,
        "ocf_conversion": ocf_conversion,
        "floor": ocf_conversion_floor,
    }

    flagged = False
    reasons: list[str] = []
    if ocf_yoy_growth is not None and ocf_yoy_growth < 0.0:
        flagged = True
        reasons.append(f"Operating cash flow declined YoY ({ocf_yoy_growth:.4f})")
    if ocf_conversion is not None and ocf_conversion < ocf_conversion_floor:
        flagged = True
        reasons.append(
            f"OCF conversion {ocf_conversion:.4f} is below floor {ocf_conversion_floor:.4f}"
        )

    if flagged:
        return RuleResult(
            rule_id="R5",
            status="flag",
            severity="medium",
            evidence=evidence,
            reason="; ".join(reasons),
        )
    return RuleResult(rule_id="R5", status="pass", severity="none", evidence=evidence)


def evaluate_r6_working_capital(
    claim: Claim | None,
    metric: FilingMetric,
    inventory_growth: float | None = None,
    revenue_growth: float | None = None,
    dso_change: float | None = None,
    inventory_gap_threshold_pp: float = 15.0,
    dso_increase_threshold_days: int = 10,
    claimed_unit: str | None = None,
    claim_metric_basis: str | None = None,
    is_annual: bool = True,
) -> RuleResult:
    """R6: Working capital discipline (inventory build or collections slipping)."""
    if not is_annual:
        return RuleResult(
            rule_id="R6",
            status="not_applicable",
            severity="none",
            evidence={},
            reason="Operating cash flow and working capital rules evaluate only on annual filings",
        )

    if claim is None or not getattr(claim, "quote", "").strip():
        return RuleResult(
            rule_id="R6",
            status="not_applicable",
            severity="none",
            evidence={},
            reason="no management claim text available",
        )

    validate_alignment(claim, metric, claimed_unit, claim_metric_basis)
    guard = _check_adjusted_guard(claim, "R6")
    if guard is not None:
        return guard

    desc_norm = claim.descriptor.lower().strip()
    is_wc_claim = (
        (desc_norm in WORKING_CAPITAL_WORDS)
        or ("inventory" in claim.metric.lower())
        or ("receivable" in claim.metric.lower())
        or ("collection" in claim.metric.lower())
    )

    if not is_wc_claim:
        return RuleResult(
            rule_id="R6",
            status="not_applicable",
            severity="none",
            evidence={"descriptor": claim.descriptor},
            reason="Claim is not a working capital discipline claim",
        )

    evidence = {
        "inventory_growth": inventory_growth,
        "revenue_growth": revenue_growth,
        "dso_change": dso_change,
        "inventory_gap_threshold_pp": inventory_gap_threshold_pp,
        "dso_increase_threshold_days": dso_increase_threshold_days,
    }

    flagged = False
    reasons: list[str] = []

    if inventory_growth is not None and revenue_growth is not None:
        gap_pp = (inventory_growth - revenue_growth) * 100.0
        evidence["inventory_vs_revenue_gap_pp"] = gap_pp
        if gap_pp > inventory_gap_threshold_pp:
            flagged = True
            reasons.append(
                f"Inventory growth exceeded revenue growth by {gap_pp:.2f} pp "
                f"(threshold {inventory_gap_threshold_pp} pp)"
            )

    if dso_change is not None:
        evidence["dso_change_days"] = dso_change
        if dso_change > dso_increase_threshold_days:
            flagged = True
            reasons.append(
                f"DSO increased by {dso_change:.1f} days "
                f"(threshold {dso_increase_threshold_days} days)"
            )

    if not flagged and (
        (inventory_growth is not None and revenue_growth is not None) or dso_change is not None
    ):
        return RuleResult(rule_id="R6", status="pass", severity="none", evidence=evidence)

    if flagged:
        return RuleResult(
            rule_id="R6",
            status="flag",
            severity="low_medium",
            evidence=evidence,
            reason="; ".join(reasons),
        )

    return RuleResult(
        rule_id="R6",
        status="not_applicable",
        severity="none",
        evidence=evidence,
        reason="Missing working capital comparison metrics",
    )


def evaluate_r7_understatement(
    claim: Claim | None,
    metric: FilingMetric,
    growth: float | None = None,
    strong_threshold: float | None = None,
    understatement_gap_pp: float = 10.0,
    sector: str | None = None,
    sector_thresholds: dict[str, float] | None = None,
    claimed_unit: str | None = None,
    claim_metric_basis: str | None = None,
) -> RuleResult:
    """R7: Understatement: cautious word on strongly improved metric."""
    if claim is None or not getattr(claim, "quote", "").strip():
        return RuleResult(
            rule_id="R7",
            status="not_applicable",
            severity="none",
            evidence={},
            reason="no management claim text available",
        )

    validate_alignment(claim, metric, claimed_unit, claim_metric_basis)
    guard = _check_adjusted_guard(claim, "R7")
    if guard is not None:
        return guard

    desc_norm = claim.descriptor.lower().strip()
    if desc_norm not in CAUTIOUS_WORDS:
        return RuleResult(
            rule_id="R7",
            status="not_applicable",
            severity="none",
            evidence={"descriptor": claim.descriptor},
            reason=f"Descriptor '{claim.descriptor}' is not a cautious word candidate",
        )

    is_sector_threshold = False
    if strong_threshold is None:
        if sector and sector_thresholds and sector.lower() in sector_thresholds:
            val = sector_thresholds[sector.lower()]
            if isinstance(val, (int, float)):
                strong_threshold = float(val)
                is_sector_threshold = True
            else:
                return RuleResult(
                    rule_id="R7",
                    status="not_applicable",
                    severity="none",
                    evidence={},
                    reason="threshold pending",
                )
        else:
            return RuleResult(
                rule_id="R7",
                status="not_applicable",
                severity="none",
                evidence={},
                reason="threshold pending",
            )

    if growth is None:
        return RuleResult(
            rule_id="R7",
            status="not_applicable",
            severity="none",
            evidence={"descriptor": claim.descriptor},
            reason="Growth value not provided",
        )

    gap_fraction = understatement_gap_pp / 100.0
    trigger_level = strong_threshold + gap_fraction
    evidence: dict[str, Any] = {
        "descriptor": claim.descriptor,
        "growth": growth,
        "trigger_level": trigger_level,
        "strong_threshold": strong_threshold,
        "understatement_gap_pp": understatement_gap_pp,
    }
    if is_sector_threshold:
        evidence["threshold_label"] = "provisional threshold"

    if growth >= trigger_level:
        suffix = " (provisional threshold)" if is_sector_threshold else ""
        return RuleResult(
            rule_id="R7",
            status="flag",
            severity="low",
            evidence=evidence,
            reason=(
                f"Metric growth {growth:.4f} was well above strong threshold "
                f"({trigger_level:.4f}) despite cautious description{suffix}"
            ),
        )
    return RuleResult(rule_id="R7", status="pass", severity="none", evidence=evidence)


def evaluate_all_rules(
    claim: Claim | None = None,
    metric: FilingMetric | None = None,
    *,
    stated_value: float | None = None,
    stated_value_source: str | None = None,
    tolerance_pp: float = 0.5,
    filing_change: float | None = None,
    growth: float | None = None,
    strong_threshold: float | None = None,
    sector: str | None = None,
    sector_thresholds: dict[str, float] | None = None,
    current_growth: float | None = None,
    prior_growth: float | None = None,
    margin_change: float | None = None,
    margin_tolerance_bps: int = 20,
    ocf_yoy_growth: float | None = None,
    ocf_conversion: float | None = None,
    ocf_conversion_floor: float = 0.5,
    inventory_growth: float | None = None,
    revenue_growth: float | None = None,
    dso_change: float | None = None,
    inventory_gap_threshold_pp: float = 15.0,
    dso_increase_threshold_days: int = 10,
    understatement_gap_pp: float = 10.0,
    claimed_unit: str | None = None,
    claim_metric_basis: str | None = None,
    is_annual: bool = False,
) -> list[RuleResult]:
    """Evaluate all consistency rules in strict order: R0, then R1 through R7."""
    if stated_value_source is not None and metric is not None:
        assert_not_same_field(stated_value_source, metric.metric)

    if claim is not None and getattr(claim, "quote", "").strip() and metric is not None:
        validate_alignment(claim, metric, claimed_unit, claim_metric_basis)

    return [
        evaluate_r0_stated_number(
            claim,
            metric,
            stated_value=stated_value,
            tolerance_pp=tolerance_pp,
            claimed_unit=claimed_unit,
            claim_metric_basis=claim_metric_basis,
            stated_value_source=stated_value_source,
        ),
        evaluate_r1_direction(
            claim,
            metric,
            filing_change=filing_change,
            claimed_unit=claimed_unit,
            claim_metric_basis=claim_metric_basis,
        ),
        evaluate_r2_magnitude(
            claim,
            metric,
            growth=growth,
            strong_threshold=strong_threshold,
            sector=sector,
            sector_thresholds=sector_thresholds,
            claimed_unit=claimed_unit,
            claim_metric_basis=claim_metric_basis,
        ),
        evaluate_r3_trend(
            claim,
            metric,
            current_growth=current_growth,
            prior_growth=prior_growth,
            claimed_unit=claimed_unit,
            claim_metric_basis=claim_metric_basis,
        ),
        evaluate_r4_profitability(
            claim,
            metric,
            margin_change=margin_change,
            margin_tolerance_bps=margin_tolerance_bps,
            claimed_unit=claimed_unit,
            claim_metric_basis=claim_metric_basis,
        ),
        evaluate_r5_cash_quality(
            claim,
            metric,
            ocf_yoy_growth=ocf_yoy_growth,
            ocf_conversion=ocf_conversion,
            ocf_conversion_floor=ocf_conversion_floor,
            claimed_unit=claimed_unit,
            claim_metric_basis=claim_metric_basis,
            is_annual=is_annual,
        ),
        evaluate_r6_working_capital(
            claim,
            metric,
            inventory_growth=inventory_growth,
            revenue_growth=revenue_growth,
            dso_change=dso_change,
            inventory_gap_threshold_pp=inventory_gap_threshold_pp,
            dso_increase_threshold_days=dso_increase_threshold_days,
            claimed_unit=claimed_unit,
            claim_metric_basis=claim_metric_basis,
            is_annual=is_annual,
        ),
        evaluate_r7_understatement(
            claim,
            metric,
            growth=growth,
            strong_threshold=strong_threshold,
            understatement_gap_pp=understatement_gap_pp,
            sector=sector,
            sector_thresholds=sector_thresholds,
            claimed_unit=claimed_unit,
            claim_metric_basis=claim_metric_basis,
        ),
    ]
