import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


class NetworkTests(unittest.IsolatedAsyncioTestCase):
    async def test_redirect_to_private_literal_rejected(self):
        from network_safety import public_trace_config
        trace = public_trace_config()
        response = SimpleNamespace(url='https://acme.com', headers={'Location': 'http://127.0.0.1/admin'})
        with self.assertRaises(OSError):
            await trace.on_request_redirect[0](None, None, SimpleNamespace(response=response))

    async def test_dns_private_address_rejected(self):
        from network_safety import PublicResolver
        resolver = PublicResolver()
        try:
            with patch.object(resolver._resolver, 'resolve', AsyncMock(return_value=[{'host': '10.0.0.1'}])):
                with self.assertRaises(OSError):
                    await resolver.resolve('redirect.example.com')
        finally:
            await resolver.close()

    async def test_dns_public_address_preserved(self):
        from network_safety import PublicResolver
        resolver = PublicResolver()
        records = [{'host': '1.1.1.1'}]
        try:
            with patch.object(resolver._resolver, 'resolve', AsyncMock(return_value=records)):
                self.assertEqual(await resolver.resolve('public.example.com'), records)
        finally:
            await resolver.close()
