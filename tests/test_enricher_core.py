"""Tests for enricher_core.py — dataclass, helpers, and run_enrichment.

Offline (no network). Covers:
- EnrichedCompany dataclass construction and defaults
- clean_email / clean_phone / extract_domain / is_valid_website
- get_cache_key determinism
- run_enrichment with empty input (must return empty list, not raise)
"""
import os
import sys
import pytest

# Make repo root importable when running from a checkout.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from enricher_core import (
    EnrichedCompany,
    run_enrichment,
    clean_email,
    clean_phone,
    extract_domain,
    is_valid_website,
    get_cache_key,
)


class TestEnrichedCompany:
    def test_default_construction_has_empty_strings(self):
        c = EnrichedCompany()
        # All string fields default to "" per dataclass definition
        assert c.company_name == ""
        assert c.website == ""
        assert c.email == ""
        assert c.domain == ""
        # Description has a default sentinel
        assert c.description == "Analyzing..."

    def test_construction_with_fields(self):
        c = EnrichedCompany(
            company_name="AliceLabs LLC",
            city="Quito",
            country="Ecuador",
            domain="alicelabs.site",
        )
        assert c.company_name == "AliceLabs LLC"
        assert c.city == "Quito"
        assert c.country == "Ecuador"

    def test_has_37_fields(self):
        """Regression: EnrichedCompany exposes 37 public fields.
        Adding a new field is fine, but accidental removal must be caught."""
        c = EnrichedCompany()
        fields = [x for x in dir(c) if not x.startswith("_")]
        # Filter out methods/properties — we want dataclass fields only
        dataclass_fields = [
            "abn", "address", "business_type", "cin", "city", "cnpj",
            "company_name", "company_number", "confidence", "country",
            "description", "domain", "duns", "ein", "email", "emails_all",
            "employees", "facebook", "founded", "industry", "instagram",
            "linkedin", "nif", "phone", "region", "revenue", "rfc", "ruc",
            "rut", "sic_code", "sources_used", "state", "status", "twitter",
            "vat", "website", "youtube",
        ]
        for f in dataclass_fields:
            assert hasattr(c, f), f"EnrichedCompany missing field: {f}"

    def test_sources_used_starts_empty(self):
        c = EnrichedCompany(company_name="Test")
        # sources_used defaults to empty string (not list) per dataclass
        assert c.sources_used == "" or c.sources_used == []


class TestCleanEmail:
    @pytest.mark.parametrize("raw,expected", [
        ("  alice@example.com  ", "alice@example.com"),
        ("ALICE@EXAMPLE.COM", "alice@example.com"),
        ("alice@example.com.", "alice@example.com"),  # rstrip('.') strips trailing dot
        ("not an email", None),    # no @
        ("", None),
    ])
    def test_clean_email(self, raw, expected):
        assert clean_email(raw) == expected

    def test_clean_email_drops_too_long(self):
        """Emails > 80 chars are dropped (anti-scraping-noise)."""
        long_email = "a" * 80 + "@example.com"
        assert clean_email(long_email) is None

    def test_clean_email_drops_skip_list(self):
        """Common no-reply addresses are dropped via SKIP_EMAILS."""
        # noreply@... is in SKIP_EMAILS
        assert clean_email("noreply@example.com") is None

    def test_clean_email_drops_short_local(self):
        """Local part must be >= 2 chars."""
        assert clean_email("a@example.com") is None

    def test_clean_email_drops_short_domain(self):
        """Domain must be >= 4 chars (alice@abc.com passes, alice@x.co does not)."""
        # 'abc.com' has 7 chars — passes the >= 4 check but the TLD regex still gates it
        assert clean_email("alice@abc.com") == "alice@abc.com"
        # 2-char domain part after @ — should fail somewhere (regex or length)
        assert clean_email("alice@b.c") is None


class TestCleanPhone:
    def test_us_format_normalized(self):
        """10-digit US phone → normalized to +1 (XXX) XXX-XXXX."""
        assert clean_phone("5551234567") == "+1 (555) 123-4567"
        # With formatting chars
        assert clean_phone("(555) 123-4567") == "+1 (555) 123-4567"

    def test_us_with_country_code(self):
        """11-digit starting with 1 → US format."""
        assert clean_phone("1-555-123-4567") == "+1 (555) 123-4567"
        assert clean_phone("+1 (555) 123-4567") == "+1 (555) 123-4567"

    def test_international_kept_as_plus_digits(self):
        """7-15 digit numbers (not US) → +digits."""
        result = clean_phone("593 99 123 4567")
        assert result == "+593991234567"

    def test_too_short_returns_none(self):
        """< 7 digits is not a valid phone."""
        assert clean_phone("12345") is None

    def test_too_long_returns_none(self):
        """> 15 digits is not a valid phone."""
        assert clean_phone("1" * 20) is None

    def test_empty_returns_none(self):
        assert clean_phone("") is None


class TestExtractDomain:
    @pytest.mark.parametrize("url,expected", [
        ("https://www.example.com/path", "example.com"),
        ("http://sub.example.co.uk/page", "sub.example.co.uk"),  # subdomain kept, only www. stripped
        ("https://example.com", "example.com"),
        ("not a url", None),  # extract_domain adds http:// prefix, urlparse finds no dot in netloc
        ("", None),
    ])
    def test_extract_domain(self, url, expected):
        result = extract_domain(url)
        if expected is None:
            assert result is None
        else:
            assert result == expected


class TestIsValidWebsite:
    @pytest.mark.parametrize("url,is_valid", [
        ("https://www.example.com", True),
        ("http://example.org", True),
        ("not a url", False),
        ("", False),
        ("ftp://example.com", False),  # only http/https
    ])
    def test_is_valid_website(self, url, is_valid):
        assert is_valid_website(url) == is_valid


class TestGetCacheKey:
    def test_same_input_same_key(self):
        c1 = EnrichedCompany(company_name="Test Corp", city="Quito")
        c2 = EnrichedCompany(company_name="Test Corp", city="Quito")
        assert get_cache_key(c1) == get_cache_key(c2)

    def test_different_input_different_key(self):
        c1 = EnrichedCompany(company_name="Test Corp", city="Quito")
        c2 = EnrichedCompany(company_name="Test Corp", city="Guayaquil")
        assert get_cache_key(c1) != get_cache_key(c2)

    def test_returns_non_empty_string(self):
        c = EnrichedCompany(company_name="Test Corp")
        key = get_cache_key(c)
        assert isinstance(key, str)
        assert len(key) > 0


class TestRunEnrichment:
    def test_empty_input_returns_empty_list(self):
        """Regression: run_enrichment([]) must not raise and must return []."""
        result = run_enrichment([])
        assert result == []
        assert isinstance(result, list)

    def test_progress_callback_not_required(self):
        """progress_callback is Optional — passing None must work."""
        result = run_enrichment([], workers=1, progress_callback=None)
        assert result == []

    def test_stop_flag_not_required(self):
        """stop_flag is Optional — passing None must work."""
        result = run_enrichment([], workers=1, stop_flag=None)
        assert result == []
