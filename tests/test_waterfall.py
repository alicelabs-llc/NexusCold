import json
import unittest
from unittest.mock import patch, AsyncMock
from enricher_core import EnrichedCompany, enrich_company


class WaterfallTests(unittest.IsolatedAsyncioTestCase):
    async def test_stops_after_first_website_and_does_not_use_cache(self):
        with patch('enricher_core.source_ddg', AsyncMock(return_value={'website': 'https://acme.com', 'source': 'ddg'})) as ddg, \
             patch('enricher_core.source_bing', AsyncMock()) as bing, \
             patch('enricher_core.source_website', AsyncMock(return_value={})), \
             patch('enricher_core.save_cache') as cache:
            result = await enrich_company(None, EnrichedCompany(company_name='Acme'),
                discovery_sources=('ddg', 'bing'), waterfall=True, registry_sources=(), use_cache=False)
        self.assertEqual(result.website, 'https://acme.com')
        ddg.assert_awaited_once()
        bing.assert_not_awaited()
        cache.assert_not_called()

    async def test_falls_through_empty_source_and_preserves_conflict(self):
        with patch('enricher_core.source_ddg', AsyncMock(return_value={})), \
             patch('enricher_core.source_bing', AsyncMock(return_value={'website': 'https://acme.com', 'source': 'bing'})), \
             patch('enricher_core.source_website', AsyncMock(return_value={
                 'email': 'new@acme.com', 'source': 'website', 'evidence': {'new@acme.com': ['https://acme.com/contact']}})):
            result = await enrich_company(None, EnrichedCompany(company_name='Acme', email='old@acme.com'),
                discovery_sources=('ddg', 'bing'), waterfall=True, registry_sources=(), use_cache=False)
        self.assertEqual(result.email, 'old@acme.com')
        evidence = json.loads(result.evidence)
        self.assertEqual(evidence['_fields']['website']['source'], 'bing')
        self.assertEqual(evidence['_conflicts'][0]['field'], 'email')

    async def test_invalid_source_rejected_before_work(self):
        with self.assertRaises(ValueError):
            await enrich_company(None, EnrichedCompany(company_name='Acme'), discovery_sources=('shell',))
