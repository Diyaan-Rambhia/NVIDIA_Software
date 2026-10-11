"""Pydantic v2 configuration schemas for FinInsight."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictBaseModel(BaseModel):
    """Base model forbidding all extra attributes."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Parameters Schema
# ---------------------------------------------------------------------------

ParameterType = Literal["int", "float", "bool", "str"]


class ParameterEntry(StrictBaseModel):
    """Single parameter definition with bounds and override rule."""

    type: ParameterType
    default: int | float | bool | str
    min: int | float | None = None
    max: int | float | None = None
    override_allowed: bool
    unit: str

    @model_validator(mode="after")
    def validate_bounds_and_default(self) -> "ParameterEntry":
        # Check type conformity for default
        if self.type == "int":
            if isinstance(self.default, bool) or not isinstance(self.default, int):
                raise ValueError(f"Default value {self.default!r} is not an integer")
        elif self.type == "float":
            if isinstance(self.default, bool) or not isinstance(self.default, (int, float)):
                raise ValueError(f"Default value {self.default!r} is not a float")
        elif self.type == "bool":
            if not isinstance(self.default, bool):
                raise ValueError(f"Default value {self.default!r} is not a bool")
        elif self.type == "str":
            if not isinstance(self.default, str):
                raise ValueError(f"Default value {self.default!r} is not a str")

        # Check bounds for numeric types
        if self.type in ("int", "float"):
            if self.min is None or self.max is None:
                raise ValueError("Numeric parameter requires both min and max bounds")
            if self.min > self.max:
                raise ValueError(f"min ({self.min}) cannot exceed max ({self.max})")
            if not (self.min <= float(self.default) <= self.max):
                raise ValueError(
                    f"Default value {self.default} is outside bounds [{self.min}, {self.max}]"
                )
        return self


class ParametersConfig(StrictBaseModel):
    """Root model for config/parameters.yaml."""

    parameters: dict[str, ParameterEntry]


# ---------------------------------------------------------------------------
# Thresholds Schema
# ---------------------------------------------------------------------------


class ThresholdsConfig(StrictBaseModel):
    """Root model for config/thresholds.yaml."""

    strong_growth_yoy_default: Annotated[float, Field(ge=0.0)]
    strong_growth_yoy_sectors: dict[str, float]
    stated_number_tolerance_pp: Annotated[float, Field(ge=0.0)]
    direction_tolerance: Annotated[float, Field(ge=0.0)]
    margin_tolerance_bps: Annotated[int, Field(ge=0)]
    ocf_conversion_floor: Annotated[float, Field(ge=0.0)]
    inventory_vs_revenue_gap_pp: Annotated[float, Field(ge=0.0)]
    dso_increase_days: Annotated[int, Field(ge=0)]
    understatement_gap_pp: Annotated[float, Field(ge=0.0)]
    max_flags_per_document: Annotated[int, Field(gt=0)]
    precision_target: Annotated[float, Field(ge=0.0, le=1.0)]


# ---------------------------------------------------------------------------
# Plans Schema
# ---------------------------------------------------------------------------

PlanAccess = Literal["none", "locked", "limited", "full"]
PlanSegment = Literal["retail", "institutional", "internal"]


class FeatureRule(StrictBaseModel):
    """Feature access configuration in a plan."""

    access: PlanAccess
    quota_per_day: int | Literal["pending"] | None = None
    unlocks_with: str | None = None

    @model_validator(mode="after")
    def validate_feature_rules(self) -> "FeatureRule":
        if self.access == "locked":
            if not self.unlocks_with:
                raise ValueError("Feature access 'locked' requires 'unlocks_with' to be specified")
        else:
            if self.unlocks_with is not None:
                raise ValueError(f"Feature access '{self.access}' forbids 'unlocks_with'")

        if self.access == "limited":
            if self.quota_per_day is None:
                raise ValueError("Feature access 'limited' requires 'quota_per_day'")
            if isinstance(self.quota_per_day, int) and self.quota_per_day <= 0:
                raise ValueError("Feature access 'limited' requires positive 'quota_per_day'")
        else:
            if self.quota_per_day is not None:
                raise ValueError(f"Feature access '{self.access}' forbids 'quota_per_day'")

        return self


class PlanEntry(StrictBaseModel):
    """Plan definition with segment, pricing, and features."""

    segment: PlanSegment
    purchasable: bool
    price_inr_per_month: int | None = None
    features: dict[str, FeatureRule]

    @model_validator(mode="after")
    def validate_plan_entry(self) -> "PlanEntry":
        required_features = {"feature1_contagion", "feature2_filings", "feature3_forensic"}
        missing = required_features - set(self.features.keys())
        if missing:
            raise ValueError(f"Plan is missing required features: {sorted(missing)}")

        if self.segment == "internal":
            if self.price_inr_per_month is not None:
                raise ValueError("Internal plan requires price_inr_per_month to be null")
        else:
            if self.price_inr_per_month is None:
                raise ValueError("Non-internal plan forbids null price_inr_per_month")
            if self.price_inr_per_month < 0:
                raise ValueError("price_inr_per_month cannot be negative")

        return self


class PlansConfig(StrictBaseModel):
    """Root model for config/plans.yaml."""

    reset_rule: str = "utc_calendar_day"
    plans: dict[str, PlanEntry]

    @model_validator(mode="after")
    def validate_cross_plan_rules(self) -> "PlansConfig":
        # 1. Exactly one internal plan ('judge_all')
        internal_plans = [name for name, p in self.plans.items() if p.segment == "internal"]
        if internal_plans != ["judge_all"]:
            raise ValueError(
                f"Expected exactly one internal plan named 'judge_all', found: {internal_plans}"
            )

        # 2. judge_all is never purchasable
        judge = self.plans.get("judge_all")
        if judge and judge.purchasable:
            raise ValueError("judge_all is an internal plan and must not be purchasable")

        # 3. Validate unlocks_with references existing purchasable plan in the same segment
        for plan_name, plan in self.plans.items():
            for feat_name, feat in plan.features.items():
                if feat.access == "locked" and feat.unlocks_with:
                    target = feat.unlocks_with
                    if target not in self.plans:
                        raise ValueError(
                            f"Plan '{plan_name}' feature '{feat_name}' unlocks_with "
                            f"unknown plan '{target}'"
                        )
                    target_plan = self.plans[target]
                    if target_plan.segment != plan.segment:
                        raise ValueError(
                            f"Plan '{plan_name}' ({plan.segment}) feature '{feat_name}' "
                            f"unlocks_with plan '{target}' from different segment "
                            f"'{target_plan.segment}'"
                        )
                    if not target_plan.purchasable:
                        raise ValueError(
                            f"Plan '{plan_name}' feature '{feat_name}' unlocks_with "
                            f"non-purchasable plan '{target}'"
                        )

        # 4. Quota pending marker is only permitted for institutional_paid feature3_forensic
        for plan_name, plan in self.plans.items():
            for feat_name, feat in plan.features.items():
                if feat.quota_per_day == "pending":
                    if plan_name != "institutional_paid" or feat_name != "feature3_forensic":
                        raise ValueError(
                            "Quota pending marker is only permitted for institutional_paid "
                            f"feature3_forensic, found on '{plan_name}.{feat_name}'"
                        )

        return self


# ---------------------------------------------------------------------------
# Universe Schema
# ---------------------------------------------------------------------------


class UniverseConfig(StrictBaseModel):
    """Root model for config/universe.yaml."""

    sectors: dict[str, list[str]]

    @model_validator(mode="after")
    def validate_no_pharma_or_health(self) -> "UniverseConfig":
        for sector_name, symbols in self.sectors.items():
            s_lower = sector_name.lower()
            if "pharma" in s_lower or "health" in s_lower:
                raise ValueError(
                    f"Sector '{sector_name}' rejected: prohibited word 'pharma' or 'health'"
                )
            for sym in symbols:
                sym_lower = sym.lower()
                if "pharma" in sym_lower or "health" in sym_lower:
                    raise ValueError(
                        f"Symbol '{sym}' in '{sector_name}' rejected: "
                        "prohibited word 'pharma' or 'health'"
                    )
        return self


# ---------------------------------------------------------------------------
# Episodes Schema
# ---------------------------------------------------------------------------

EpisodeStatus = Literal["pending_confirmation", "confirmed"]


class EpisodeEntry(StrictBaseModel):
    """Single episode definition."""

    name: str
    start: str | None = None
    end: str | None = None
    status: EpisodeStatus

    @model_validator(mode="after")
    def validate_episode_dates_and_status(self) -> "EpisodeEntry":
        if self.status == "pending_confirmation":
            if self.start is not None or self.end is not None:
                raise ValueError(
                    f"Episode '{self.name}' with 'pending_confirmation' status "
                    "must have null dates"
                )
        elif self.status == "confirmed":
            if self.start is None or self.end is None:
                raise ValueError(
                    f"Episode '{self.name}' with 'confirmed' status requires non-null dates"
                )
            if self.start >= self.end:
                raise ValueError(
                    f"Episode '{self.name}' with 'confirmed' status requires start < end"
                )
        return self


class EpisodesConfig(StrictBaseModel):
    """Root model for config/episodes.yaml."""

    episodes: dict[str, EpisodeEntry]


# ---------------------------------------------------------------------------
# Lexicon Schema
# ---------------------------------------------------------------------------


class LexiconConfig(StrictBaseModel):
    """Root model for config/lexicon.yaml."""

    positive_phrases: list[str]
    negative_phrases: list[str]
    never_trigger_alone: list[str]

    @model_validator(mode="after")
    def validate_phrases(self) -> "LexiconConfig":
        for list_name, phrases in [
            ("positive_phrases", self.positive_phrases),
            ("negative_phrases", self.negative_phrases),
            ("never_trigger_alone", self.never_trigger_alone),
        ]:
            for phrase in phrases:
                if not phrase or not phrase.strip():
                    raise ValueError(f"Lexicon list '{list_name}' contains an empty phrase")
                if phrase != phrase.lower():
                    raise ValueError(
                        f"Lexicon phrase {phrase!r} in '{list_name}' must be all lowercase"
                    )
        return self


# ---------------------------------------------------------------------------
# All Config Container
# ---------------------------------------------------------------------------


class AllConfig(StrictBaseModel):
    """Container holding all parsed configuration files."""

    parameters: ParametersConfig
    thresholds: ThresholdsConfig
    plans: PlansConfig
    universe: UniverseConfig
    episodes: EpisodesConfig
    lexicon: LexiconConfig
