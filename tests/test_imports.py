"""Smoke tests: every Python file in the repo root imports cleanly.

Catches syntax errors, missing imports, broken dataclass definitions.
"""
import importlib
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Modules expected to be importable on a clean checkout with deps installed.
IMPORTABLE_MODULES = [
    "enricher_core",
    "email_warmer",
]


@pytest.mark.parametrize("module_name", IMPORTABLE_MODULES)
def test_module_imports(module_name):
    """Each top-level module must import without raising."""
    mod = importlib.import_module(module_name)
    assert mod is not None
    assert hasattr(mod, "__file__")


def test_enricher_core_exposes_run_enrichment():
    """run_enrichment is the public entry point."""
    from enricher_core import run_enrichment
    assert callable(run_enrichment)


def test_enricher_core_exposes_enriched_company():
    """EnrichedCompany is the public dataclass."""
    from enricher_core import EnrichedCompany
    assert EnrichedCompany is not None
    # Construction with no args must work (all fields have defaults)
    c = EnrichedCompany()
    assert c is not None
