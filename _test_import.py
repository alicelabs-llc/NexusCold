"""Quick import test"""
from enricher_core import EnrichedCompany, run_enrichment

c = EnrichedCompany(company_name="Test Corp")
fields = [x for x in dir(c) if not x.startswith("_")]
print(f"FIELDS: {len(fields)} -> {fields}")
print(f"IMPORT_OK")
