"""Known-answer and edge case tests for configuration schemas and loaders."""

from pathlib import Path

import pytest
import yaml

from backend.app.config.env import ConfigError
from backend.app.config.loader import (
    ParameterError,
    load_all_config,
    load_config_file,
    resolve_parameters,
    validate_window_consistency,
)
from backend.app.config.models import (
    EpisodesConfig,
    LexiconConfig,
    ParametersConfig,
    PlansConfig,
    ThresholdsConfig,
    UniverseConfig,
)


def test_load_all_config_success() -> None:
    """Verify that all six real config files load through load_all_config()."""
    config = load_all_config(Path("config"))
    assert "W" in config.parameters.parameters
    assert "chunk_size" in config.parameters.parameters
    assert config.parameters.parameters["chunk_size"].default == 1200
    assert "chunk_overlap" in config.parameters.parameters
    assert config.parameters.parameters["chunk_overlap"].default == 150
    assert "annualisation_factor" in config.parameters.parameters
    assert config.parameters.parameters["annualisation_factor"].default == 252
    assert "return_frequency" in config.parameters.parameters
    assert config.parameters.parameters["return_frequency"].default == "daily"
    assert "risk_free_series" in config.parameters.parameters
    assert "xirr_bracket_low" in config.parameters.parameters
    assert config.parameters.parameters["xirr_bracket_low"].default == -0.99
    assert "xirr_bracket_high" in config.parameters.parameters
    assert config.parameters.parameters["xirr_bracket_high"].default == 10.0
    assert "xirr_tol" in config.parameters.parameters
    assert "xirr_max_iter" in config.parameters.parameters
    assert "xirr_grid_points" in config.parameters.parameters
    assert config.thresholds.strong_growth_yoy_default == 0.08
    assert "retail_free" in config.plans.plans
    assert "judge_all" in config.plans.plans
    assert "fmcg" in config.universe.sectors
    assert "ilfs_crisis" in config.episodes.episodes
    assert len(config.lexicon.positive_phrases) > 0


# ---------------------------------------------------------------------------
# Rejection Tests with Real Temp Files
# ---------------------------------------------------------------------------


def test_reject_default_outside_bounds(tmp_path: Path) -> None:
    """Default outside min/max bounds must raise ConfigError naming file and field."""
    temp_file = tmp_path / "parameters.yaml"
    content = {
        "parameters": {
            "bad_param": {
                "type": "int",
                "default": 100,
                "min": 10,
                "max": 50,
                "override_allowed": True,
                "unit": "days",
            }
        }
    }
    temp_file.write_text(yaml.safe_dump(content), encoding="utf-8")

    with pytest.raises(ConfigError) as exc_info:
        load_config_file(temp_file, ParametersConfig)
    err = str(exc_info.value)
    assert "parameters.yaml" in err
    assert "parameters.bad_param" in err


def test_reject_locked_without_unlocks_with(tmp_path: Path) -> None:
    """Locked feature without unlocks_with must raise ConfigError naming file and field."""
    temp_file = tmp_path / "plans.yaml"
    content = {
        "plans": {
            "retail_free": {
                "segment": "retail",
                "purchasable": True,
                "price_inr_per_month": 0,
                "features": {
                    "feature1_contagion": {"access": "limited", "quota_per_day": 10},
                    "feature2_filings": {"access": "limited", "quota_per_day": 5},
                    "feature3_forensic": {"access": "locked"},  # missing unlocks_with
                },
            },
            "judge_all": {
                "segment": "internal",
                "purchasable": False,
                "price_inr_per_month": None,
                "features": {
                    "feature1_contagion": {"access": "full"},
                    "feature2_filings": {"access": "full"},
                    "feature3_forensic": {"access": "full"},
                },
            },
        }
    }
    temp_file.write_text(yaml.safe_dump(content), encoding="utf-8")

    with pytest.raises(ConfigError) as exc_info:
        load_config_file(temp_file, PlansConfig)
    err = str(exc_info.value)
    assert "plans.yaml" in err
    assert "feature3_forensic" in err


def test_reject_locked_naming_plan_in_other_segment(tmp_path: Path) -> None:
    """Locked feature unlocking with plan in different segment must raise ConfigError."""
    temp_file = tmp_path / "plans.yaml"
    content = {
        "plans": {
            "retail_free": {
                "segment": "retail",
                "purchasable": True,
                "price_inr_per_month": 0,
                "features": {
                    "feature1_contagion": {"access": "limited", "quota_per_day": 10},
                    "feature2_filings": {"access": "limited", "quota_per_day": 5},
                    "feature3_forensic": {
                        "access": "locked",
                        "unlocks_with": "institutional_paid",  # Cross-segment
                    },
                },
            },
            "institutional_paid": {
                "segment": "institutional",
                "purchasable": True,
                "price_inr_per_month": 4999,
                "features": {
                    "feature1_contagion": {"access": "full"},
                    "feature2_filings": {"access": "full"},
                    "feature3_forensic": {"access": "full"},
                },
            },
            "judge_all": {
                "segment": "internal",
                "purchasable": False,
                "price_inr_per_month": None,
                "features": {
                    "feature1_contagion": {"access": "full"},
                    "feature2_filings": {"access": "full"},
                    "feature3_forensic": {"access": "full"},
                },
            },
        }
    }
    temp_file.write_text(yaml.safe_dump(content), encoding="utf-8")

    with pytest.raises(ConfigError) as exc_info:
        load_config_file(temp_file, PlansConfig)
    err = str(exc_info.value)
    assert "plans.yaml" in err
    assert "retail_free" in err
    assert "institutional_paid" in err


def test_reject_none_access_with_unlocks_with(tmp_path: Path) -> None:
    """Access 'none' with unlocks_with specified must raise ConfigError."""
    temp_file = tmp_path / "plans.yaml"
    content = {
        "plans": {
            "retail_free": {
                "segment": "retail",
                "purchasable": True,
                "price_inr_per_month": 0,
                "features": {
                    "feature1_contagion": {"access": "limited", "quota_per_day": 10},
                    "feature2_filings": {"access": "limited", "quota_per_day": 5},
                    "feature3_forensic": {"access": "none", "unlocks_with": "retail_paid"},
                },
            },
            "retail_paid": {
                "segment": "retail",
                "purchasable": True,
                "price_inr_per_month": 499,
                "features": {
                    "feature1_contagion": {"access": "full"},
                    "feature2_filings": {"access": "full"},
                    "feature3_forensic": {"access": "full"},
                },
            },
            "judge_all": {
                "segment": "internal",
                "purchasable": False,
                "price_inr_per_month": None,
                "features": {
                    "feature1_contagion": {"access": "full"},
                    "feature2_filings": {"access": "full"},
                    "feature3_forensic": {"access": "full"},
                },
            },
        }
    }
    temp_file.write_text(yaml.safe_dump(content), encoding="utf-8")

    with pytest.raises(ConfigError) as exc_info:
        load_config_file(temp_file, PlansConfig)
    err = str(exc_info.value)
    assert "plans.yaml" in err
    assert "feature3_forensic" in err


def test_reject_null_price_on_non_internal_plan(tmp_path: Path) -> None:
    """Null price on non-internal plan must raise ConfigError."""
    temp_file = tmp_path / "plans.yaml"
    content = {
        "plans": {
            "retail_paid": {
                "segment": "retail",
                "purchasable": True,
                "price_inr_per_month": None,  # invalid for retail
                "features": {
                    "feature1_contagion": {"access": "full"},
                    "feature2_filings": {"access": "full"},
                    "feature3_forensic": {"access": "full"},
                },
            },
            "judge_all": {
                "segment": "internal",
                "purchasable": False,
                "price_inr_per_month": None,
                "features": {
                    "feature1_contagion": {"access": "full"},
                    "feature2_filings": {"access": "full"},
                    "feature3_forensic": {"access": "full"},
                },
            },
        }
    }
    temp_file.write_text(yaml.safe_dump(content), encoding="utf-8")

    with pytest.raises(ConfigError) as exc_info:
        load_config_file(temp_file, PlansConfig)
    err = str(exc_info.value)
    assert "plans.yaml" in err
    assert "retail_paid" in err


def test_reject_second_internal_plan(tmp_path: Path) -> None:
    """Having more than one internal plan must raise ConfigError."""
    temp_file = tmp_path / "plans.yaml"
    content = {
        "plans": {
            "judge_all": {
                "segment": "internal",
                "purchasable": False,
                "price_inr_per_month": None,
                "features": {
                    "feature1_contagion": {"access": "full"},
                    "feature2_filings": {"access": "full"},
                    "feature3_forensic": {"access": "full"},
                },
            },
            "admin_plan": {
                "segment": "internal",
                "purchasable": False,
                "price_inr_per_month": None,
                "features": {
                    "feature1_contagion": {"access": "full"},
                    "feature2_filings": {"access": "full"},
                    "feature3_forensic": {"access": "full"},
                },
            },
        }
    }
    temp_file.write_text(yaml.safe_dump(content), encoding="utf-8")

    with pytest.raises(ConfigError) as exc_info:
        load_config_file(temp_file, PlansConfig)
    err = str(exc_info.value)
    assert "plans.yaml" in err
    assert "judge_all" in err


def test_reject_judge_all_purchasable(tmp_path: Path) -> None:
    """Internal plan judge_all being purchasable must raise ConfigError."""
    temp_file = tmp_path / "plans.yaml"
    content = {
        "plans": {
            "judge_all": {
                "segment": "internal",
                "purchasable": True,  # invalid
                "price_inr_per_month": None,
                "features": {
                    "feature1_contagion": {"access": "full"},
                    "feature2_filings": {"access": "full"},
                    "feature3_forensic": {"access": "full"},
                },
            }
        }
    }
    temp_file.write_text(yaml.safe_dump(content), encoding="utf-8")

    with pytest.raises(ConfigError) as exc_info:
        load_config_file(temp_file, PlansConfig)
    err = str(exc_info.value)
    assert "plans.yaml" in err
    assert "judge_all" in err


def test_reject_missing_feature_in_plan(tmp_path: Path) -> None:
    """Plan missing one of the 3 features must raise ConfigError."""
    temp_file = tmp_path / "plans.yaml"
    content = {
        "plans": {
            "judge_all": {
                "segment": "internal",
                "purchasable": False,
                "price_inr_per_month": None,
                "features": {
                    "feature1_contagion": {"access": "full"},
                    "feature2_filings": {"access": "full"},
                    # feature3_forensic is missing
                },
            }
        }
    }
    temp_file.write_text(yaml.safe_dump(content), encoding="utf-8")

    with pytest.raises(ConfigError) as exc_info:
        load_config_file(temp_file, PlansConfig)
    err = str(exc_info.value)
    assert "plans.yaml" in err
    assert "feature3_forensic" in err


def test_reject_non_positive_quota(tmp_path: Path) -> None:
    """Quota <= 0 in limited access must raise ConfigError."""
    temp_file = tmp_path / "plans.yaml"
    content = {
        "plans": {
            "judge_all": {
                "segment": "internal",
                "purchasable": False,
                "price_inr_per_month": None,
                "features": {
                    "feature1_contagion": {"access": "limited", "quota_per_day": 0},
                    "feature2_filings": {"access": "full"},
                    "feature3_forensic": {"access": "full"},
                },
            }
        }
    }
    temp_file.write_text(yaml.safe_dump(content), encoding="utf-8")

    with pytest.raises(ConfigError) as exc_info:
        load_config_file(temp_file, PlansConfig)
    err = str(exc_info.value)
    assert "plans.yaml" in err
    assert "quota_per_day" in err


def test_reject_pharma_and_health_identifiers(tmp_path: Path) -> None:
    """Universe rejecting any ID or sector name with 'pharma' or 'health'."""
    temp_file1 = tmp_path / "universe1.yaml"
    content1 = {"sectors": {"pharma_sector": ["SUNPHARMA"]}}
    temp_file1.write_text(yaml.safe_dump(content1), encoding="utf-8")

    with pytest.raises(ConfigError) as exc_info1:
        load_config_file(temp_file1, UniverseConfig)
    assert "universe1.yaml" in str(exc_info1.value)
    assert "pharma" in str(exc_info1.value).lower()

    temp_file2 = tmp_path / "universe2.yaml"
    content2 = {"sectors": {"specialty": ["HEALTHCARE_INC"]}}
    temp_file2.write_text(yaml.safe_dump(content2), encoding="utf-8")

    with pytest.raises(ConfigError) as exc_info2:
        load_config_file(temp_file2, UniverseConfig)
    assert "universe2.yaml" in str(exc_info2.value)
    assert "health" in str(exc_info2.value).lower()


def test_reject_confirmed_episode_invalid_dates(tmp_path: Path) -> None:
    """Confirmed episode with start >= end or null dates must raise ConfigError."""
    temp_file1 = tmp_path / "episodes1.yaml"
    content1 = {
        "episodes": {
            "crisis_a": {
                "name": "Crisis A",
                "start": None,
                "end": None,
                "status": "confirmed",
            }
        }
    }
    temp_file1.write_text(yaml.safe_dump(content1), encoding="utf-8")

    with pytest.raises(ConfigError) as exc1:
        load_config_file(temp_file1, EpisodesConfig)
    assert "episodes1.yaml" in str(exc1.value)

    temp_file2 = tmp_path / "episodes2.yaml"
    content2 = {
        "episodes": {
            "crisis_b": {
                "name": "Crisis B",
                "start": "2020-05-01",
                "end": "2020-04-01",
                "status": "confirmed",
            }
        }
    }
    temp_file2.write_text(yaml.safe_dump(content2), encoding="utf-8")

    with pytest.raises(ConfigError) as exc2:
        load_config_file(temp_file2, EpisodesConfig)
    assert "episodes2.yaml" in str(exc2.value)


def test_reject_lexicon_uppercase_or_empty(tmp_path: Path) -> None:
    """Uppercase or empty phrases in lexicon must raise ConfigError."""
    temp_file1 = tmp_path / "lexicon1.yaml"
    content1 = {
        "positive_phrases": ["Strong Growth"],
        "negative_phrases": ["headwinds"],
        "never_trigger_alone": ["stable"],
    }
    temp_file1.write_text(yaml.safe_dump(content1), encoding="utf-8")

    with pytest.raises(ConfigError) as exc1:
        load_config_file(temp_file1, LexiconConfig)
    assert "lexicon1.yaml" in str(exc1.value)
    assert "lowercase" in str(exc1.value)

    temp_file2 = tmp_path / "lexicon2.yaml"
    content2 = {
        "positive_phrases": [""],
        "negative_phrases": ["headwinds"],
        "never_trigger_alone": ["stable"],
    }
    temp_file2.write_text(yaml.safe_dump(content2), encoding="utf-8")

    with pytest.raises(ConfigError) as exc2:
        load_config_file(temp_file2, LexiconConfig)
    assert "lexicon2.yaml" in str(exc2.value)


def test_reject_empty_file(tmp_path: Path) -> None:
    """Empty configuration file must raise ConfigError."""
    temp_file = tmp_path / "empty.yaml"
    temp_file.write_text("   \n", encoding="utf-8")

    with pytest.raises(ConfigError) as exc:
        load_config_file(temp_file, LexiconConfig)
    assert "empty.yaml" in str(exc.value)
    assert "empty" in str(exc.value)


def test_reject_missing_file(tmp_path: Path) -> None:
    """Non-existent file must raise ConfigError."""
    temp_file = tmp_path / "non_existent.yaml"

    with pytest.raises(ConfigError) as exc:
        load_config_file(temp_file, LexiconConfig)
    assert "non_existent.yaml" in str(exc.value)


def test_reject_unknown_field_extra_forbid(tmp_path: Path) -> None:
    """Extra unexpected field must raise ConfigError naming file and field."""
    temp_file = tmp_path / "thresholds.yaml"
    content = {
        "strong_growth_yoy_default": 0.08,
        "strong_growth_yoy_sectors": {},
        "stated_number_tolerance_pp": 0.5,
        "direction_tolerance": 0.005,
        "margin_tolerance_bps": 20,
        "ocf_conversion_floor": 0.5,
        "inventory_vs_revenue_gap_pp": 15.0,
        "dso_increase_days": 10,
        "understatement_gap_pp": 10.0,
        "max_flags_per_document": 5,
        "precision_target": 0.80,
        "unknown_extra_field": 123,  # forbidden
    }
    temp_file.write_text(yaml.safe_dump(content), encoding="utf-8")

    with pytest.raises(ConfigError) as exc:
        load_config_file(temp_file, ThresholdsConfig)
    err = str(exc.value)
    assert "thresholds.yaml" in err
    assert "unknown_extra_field" in err


# ---------------------------------------------------------------------------
# resolve_parameters Tests
# ---------------------------------------------------------------------------


def test_resolve_parameters_valid_override() -> None:
    """Valid override should update the returned parameter dictionary."""
    base = load_all_config(Path("config")).parameters
    res = resolve_parameters({"W": 120, "lambda": 0.90}, base_params=base)
    assert res["W"] == 120
    assert res["lambda"] == 0.90
    assert res["B"] == 250  # unchanged default


def test_resolve_parameters_unknown_name() -> None:
    """Unknown parameter name must raise ParameterError."""
    base = load_all_config(Path("config")).parameters
    with pytest.raises(ParameterError) as exc:
        resolve_parameters({"non_existent_param": 10}, base_params=base)
    assert exc.value.field == "non_existent_param"
    assert "Unknown parameter" in exc.value.reason


def test_resolve_parameters_non_overridable() -> None:
    """Overriding parameter with override_allowed=False must raise ParameterError."""
    base = load_all_config(Path("config")).parameters
    with pytest.raises(ParameterError) as exc:
        resolve_parameters({"us_series_lag_days": 2}, base_params=base)
    assert exc.value.field == "us_series_lag_days"
    assert "cannot be overridden" in exc.value.reason


def test_resolve_parameters_out_of_bounds() -> None:
    """Value outside min/max bounds must raise ParameterError."""
    base = load_all_config(Path("config")).parameters
    # W has bounds [20, 500]
    with pytest.raises(ParameterError) as exc:
        resolve_parameters({"W": 600}, base_params=base)
    assert exc.value.field == "W"
    assert exc.value.value == 600
    assert exc.value.allowed_range == (20, 500)


def test_resolve_parameters_wrong_type() -> None:
    """Supplying boolean for integer parameter must raise ParameterError."""
    base = load_all_config(Path("config")).parameters
    with pytest.raises(ParameterError) as exc:
        resolve_parameters({"W": True}, base_params=base)
    assert exc.value.field == "W"
    assert "type int" in exc.value.reason

    with pytest.raises(ParameterError) as exc2:
        resolve_parameters({"W": "60"}, base_params=base)
    assert exc2.value.field == "W"
    assert "type int" in exc2.value.reason


# ---------------------------------------------------------------------------
# validate_window_consistency Tests
# ---------------------------------------------------------------------------


def test_validate_window_consistency() -> None:
    """baseline 250 + gap 20 + current 20 fails for history 289 and passes for 290."""
    params = {"B": 250, "G": 20, "C": 20}

    # Total window required = 250 + 20 + 20 = 290
    # Must fail for 289
    with pytest.raises(ValueError) as exc:
        validate_window_consistency(params, history_length=289)
    assert "290 exceeds available history length 289" in str(exc.value)

    # Must pass for 290
    assert validate_window_consistency(params, history_length=290) is True

    # Must pass for history > 290
    assert validate_window_consistency(params, history_length=300) is True
