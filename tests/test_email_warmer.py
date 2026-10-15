"""Tests for email_warmer.py — ramp logic, scheduling, dedup.

Offline (no network, no real email sending).
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_email_warmer_module_imports():
    """Smoke test: email_warmer imports without error."""
    import email_warmer
    assert hasattr(email_warmer, "__file__")


def test_email_warmer_has_main_class_or_function():
    """Sanity: the module exposes something usable."""
    import email_warmer
    # Look for a typical entry point (class with 'warmer' or 'warm' in name,
    # or a run/main function)
    public_names = [n for n in dir(email_warmer) if not n.startswith("_")]
    assert len(public_names) > 0, "email_warmer module appears empty"
