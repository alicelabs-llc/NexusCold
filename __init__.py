"""NexusCold — AliceLabs B2B Data Enrichment Engine.

Multi-source parallel enrichment with 20+ async workers.
Coverage: USA, UK, EU, LATAM, AU, IN, SG, HK + more.

Public API:
    from nexuscold import EnrichedCompany, run_enrichment

    companies = [EnrichedCompany(company_name="Microsoft", city="Redmond", country="USA")]
    results = run_enrichment(companies, workers=20)

Modules:
    enricher_core  — main enrichment engine + dataclass + helpers
    email_warmer   — email warm-up ramp scheduler (separate process)

GUI:
    python -m nexuscold.gui   # equivalent to python ALICELABS_EXTRACTOR_GUI.py
"""

__version__ = "6.0.0"
__all__ = ["EnrichedCompany", "run_enrichment"]
