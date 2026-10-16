import asyncio
import json
import tempfile
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, patch

import enricher_core as core
from email_warmer import EmailAccount, EmailWarmer, WarmerConfig


class EnrichmentTests(unittest.IsolatedAsyncioTestCase):
    def test_private_and_non_http_websites_rejected(self):
        for url in ('http://127.0.0.1', 'http://169.254.169.254', 'http://[::1]',
                    'file:///etc/passwd', 'https://localhost', 'https://user:pass@acme.com'):
            self.assertFalse(core.is_valid_website(url), url)
        self.assertTrue(core.is_valid_website('https://acme.com'))

    async def test_cache_keeps_results_from_concurrent_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, 'CACHE_FILE', Path(tmp) / 'cache.json'):
            core.save_cache({'one': {'confidence': 50}})
            core.save_cache({'two': {'confidence': 60}})
            self.assertEqual(set(core.load_cache()), {'one', 'two'})

    async def enrich_without_network(self, company, cache):
        with ExitStack() as stack:
            stack.enter_context(patch.object(core, 'load_cache', return_value=cache))
            stack.enter_context(patch.object(core, 'save_cache'))
            for name in ('source_samgov', 'source_opencorp', 'source_uk_companies'):
                stack.enter_context(patch.object(core, name, AsyncMock(return_value={})))
            stack.enter_context(patch.object(core, 'source_website', AsyncMock(return_value={
                'source': 'website', 'description': 'Observed description from company website.',
                'email': 'hello@acme.com', 'phone': '+12025550123',
                'address': '123 Example Street', 'linkedin': 'https://linkedin.com/company/acme',
                'facebook': 'https://facebook.com/acme', 'twitter': 'https://x.com/acme',
                'instagram': 'https://instagram.com/acme', 'founded': '2001',
                'employees': '20', 'revenue': '1000000', 'vat': 'GB123456789',
            })))
            return await core.enrich_company(None, company)

    async def test_expired_cache_refreshes(self):
        company = core.EnrichedCompany(company_name='Acme', website='https://acme.com')
        result = await self.enrich_without_network(company, {
            core.get_cache_key(company): {'ts': time.time() - core.CACHE_TTL - 1, 'confidence': 90}
        })
        self.assertEqual(result.email, 'hello@acme.com')

    async def test_fresh_cache_restores_default_description(self):
        company = core.EnrichedCompany(company_name='Acme')
        result = await self.enrich_without_network(company, {
            core.get_cache_key(company): {'ts': time.time(), 'confidence': 80,
                'description': 'Observed description', 'industry': 'Manufacturing'}
        })
        self.assertEqual(result.description, 'Observed description')
        self.assertEqual(result.industry, 'Manufacturing')

    async def test_observed_description_replaces_heuristic(self):
        result = await self.enrich_without_network(
            core.EnrichedCompany(company_name='Acme Tech', website='https://acme.com'), {})
        self.assertEqual(result.description, 'Observed description from company website.')
        self.assertLessEqual(result.confidence, 100)

    async def test_progress_counts_completions(self):
        companies = [core.EnrichedCompany(company_name=str(i)) for i in range(3)]
        async def enrich(session, company):
            await asyncio.sleep((2 - int(company.company_name)) * .01)
            return company
        progress = []
        with patch.object(core, 'enrich_company', side_effect=enrich):
            result = await core.enrich_batch(companies, progress_callback=lambda n, *_: progress.append(n))
        self.assertEqual(progress, [1, 2, 3])
        self.assertEqual([c.company_name for c in result], ['0', '1', '2'])

    async def test_stop_prevents_queued_work(self):
        stopped = False
        async def enrich(session, company):
            nonlocal stopped
            stopped = True
            return company
        companies = [core.EnrichedCompany(company_name=str(i)) for i in range(3)]
        with patch.object(core, 'enrich_company', side_effect=enrich) as mocked:
            await core.enrich_batch(companies, workers=1, stop_flag=lambda: stopped)
        self.assertEqual(mocked.await_count, 1)

    async def test_invalid_worker_count_rejected(self):
        with self.assertRaises(ValueError):
            await core.enrich_batch([], workers=0)

    def test_cache_key_distinguishes_supplied_website(self):
        a = core.EnrichedCompany(company_name='Acme', website='https://one.com')
        b = core.EnrichedCompany(company_name='Acme', website='https://two.com')
        self.assertNotEqual(core.get_cache_key(a), core.get_cache_key(b))

    def test_cache_key_distinguishes_supplied_email(self):
        a = core.EnrichedCompany(company_name='Acme', email='info@acme.com')
        b = core.EnrichedCompany(company_name='Acme', email='bad')
        self.assertNotEqual(core.get_cache_key(a), core.get_cache_key(b))


class WarmerTests(unittest.IsolatedAsyncioTestCase):
    def test_state_never_contains_password(self):
        account = EmailAccount(email='sender@example.com', password='secret-test-value')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'state.json'
            EmailWarmer([account]).save_state(str(path))
            self.assertNotIn('secret-test-value', path.read_text())

    def test_legacy_password_not_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'state.json'
            path.write_text(json.dumps({'accounts': [{'email': 'sender@example.com', 'password': 'legacy'}]}))
            warmer = EmailWarmer()
            warmer.load_state(str(path))
            self.assertEqual(warmer.accounts[0].password, '')

    async def test_no_invented_recipient(self):
        account = EmailAccount(email='sender@example.com')
        warmer = EmailWarmer([account])
        self.assertIsNone(warmer._get_honeypot_target(account))

    async def test_warmup_does_not_invent_engagement(self):
        account = EmailAccount(email='sender@example.com')
        warmer = EmailWarmer([account])
        with patch.object(warmer, '_get_honeypot_target', return_value='opted-in@example.com'), \
             patch.object(warmer, 'send_email', return_value=True), \
             patch('email_warmer.random.random', return_value=0):
            await warmer.send_warmup_email(account)
        self.assertEqual((account.total_opened, account.total_replied, account.total_bounced), (0, 0, 0))

    def test_smtp_dry_run_by_default(self):
        warmer = EmailWarmer()
        account = EmailAccount(email='sender@example.com')
        with patch.object(warmer, '_connect_smtp') as smtp:
            self.assertFalse(warmer.send_email(account, 'target@example.com', 'Test', 'Body'))
        smtp.assert_not_called()
        self.assertEqual(account.total_sent, 0)


if __name__ == '__main__':
    unittest.main()
