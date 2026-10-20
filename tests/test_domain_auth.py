import unittest
from types import SimpleNamespace
import dns.resolver
import dns.rrset
from domain_auth import check_domain


class AuthTests(unittest.IsolatedAsyncioTestCase):
    def resolver(self, records):
        async def resolve(name, kind, **kwargs):
            value = records[name]
            if isinstance(value, Exception):
                raise value
            return dns.rrset.from_text(name, 60, 'IN', 'TXT', *value)
        return SimpleNamespace(resolve=resolve)

    async def test_published_policy_is_not_delivery_guarantee(self):
        r = self.resolver({'example.com': ['"v=spf1 -all"'],
                           '_dmarc.example.com': ['"v=DMARC1; p=reject"']})
        result = await check_domain('example.com', r)
        self.assertEqual(result['spf']['status'], 'published')
        self.assertEqual(result['dmarc']['policy'], 'reject')
        self.assertEqual(result['scope'], 'exact_domain_publication_only')

    async def test_dns_timeout_is_unknown_not_missing(self):
        r = self.resolver({'example.com': dns.resolver.LifetimeTimeout(),
                           '_dmarc.example.com': dns.resolver.NoAnswer()})
        result = await check_domain('example.com', r)
        self.assertEqual(result['spf']['status'], 'unknown')
        self.assertEqual(result['dmarc']['status'], 'missing')

    async def test_duplicate_policies_are_invalid(self):
        r = self.resolver({'example.com': ['"v=spf1 -all"', '"v=spf1 ~all"'],
                           '_dmarc.example.com': ['"v=DMARC1; p=reject; p=none"']})
        result = await check_domain('example.com', r)
        self.assertEqual(result['spf']['status'], 'invalid')
        self.assertEqual(result['dmarc']['status'], 'invalid')

    async def test_split_txt_and_monitoring_policy(self):
        r = self.resolver({'example.com': ['"v=spf1 " "~all"'],
                           '_dmarc.example.com': ['"v=DMARC1; p=none"']})
        result = await check_domain('example.com', r)
        self.assertEqual(result['spf']['record'], 'v=spf1 ~all')
        self.assertEqual(result['dmarc']['status'], 'monitoring')

    async def test_private_and_injected_names_rejected(self):
        for domain in ['127.0.0.1', 'x.local', 'a\r\nb.com', 'https://example.com', 'example.com/path']:
            with self.assertRaises(ValueError):
                await check_domain(domain)
