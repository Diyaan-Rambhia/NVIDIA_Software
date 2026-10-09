"""Verify that all core scaffold packages import successfully."""

import importlib

import pytest

PACKAGES = [
    "backend",
    "backend.app",
    "backend.app.config",
    "backend.app.auth",
    "backend.app.entitlements",
    "backend.app.payments",
    "backend.app.llm",
    "backend.app.agent",
    "backend.app.data",
    "backend.app.db",
    "backend.app.ops",
    "backend.app.features",
    "backend.app.features.f1_contagion",
    "backend.app.features.f2_filings",
    "backend.app.features.f3_log",
]


@pytest.mark.parametrize("package_name", PACKAGES)
def test_all_packages_import(package_name: str) -> None:
    """Ensure each backend package imports without error."""
    module = importlib.import_module(package_name)
    assert module is not None
