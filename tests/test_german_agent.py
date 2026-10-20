import json
import unittest
from german_agent import inspect_rows, ModelConfig, ask_german
from aiohttp import web
from aiohttp.test_utils import TestServer


class AgentTests(unittest.TestCase):
    def test_spanish_mapping_and_missing_values(self):
        result = inspect_rows([{'Empresa': 'AliceLabs', 'Correo': 'test@example.com', 'Ciudad': 'Quito'},
                               {'Empresa': '', 'Correo': 'bad', 'Ciudad': ''}])
        self.assertEqual(result['mapping']['company_name'], 'Empresa')
        self.assertEqual(result['mapping']['email'], 'Correo')
        self.assertEqual(result['metrics']['missing_company'], 1)
        self.assertEqual(result['metrics']['email_status']['invalid_syntax'], 1)
        self.assertNotIn('AliceLabs', json.dumps(result['metrics']))
        self.assertNotIn('test@example.com', json.dumps(result['metrics']))

    def test_unknown_does_not_become_invalid(self):
        result = inspect_rows([{'company_name': 'A', 'MAILBOX_STATUS': 'unknown'}])
        self.assertEqual(result['metrics']['mailbox_status'], {'unknown': 1})
        self.assertTrue(any('unknown' in tip for tip in result['recommendations']))

    def test_remote_requires_https_consent_and_token(self):
        for url, consent, token in [('http://example.com', True, 'a'*32),
                                    ('https://example.com', False, 'a'*32),
                                    ('https://example.com', True, '')]:
            with self.assertRaises(ValueError):
                ModelConfig(base_url=url, allow_remote=consent, token=token)
        ModelConfig(base_url='https://example.com', allow_remote=True, token='a'*32)

    def test_blocks_private_remote_and_cloud_model(self):
        for url in ['http://169.254.169.254', 'https://10.0.0.1', 'https://user:pass@example.com',
                    'https://example.com/path', 'https://example.com?x=1']:
            with self.assertRaises(ValueError):
                ModelConfig(base_url=url, allow_remote=True, token='a'*32)
        with self.assertRaises(ValueError):
            ModelConfig(model='qwen3:cloud')


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_http_protocol_only_sends_aggregates(self):
        captured = []
        async def chat(request):
            captured.append(await request.json())
            return web.json_response({'message': {'content': 'Revisa los unknown.'}})
        app = web.Application()
        app.router.add_post('/api/chat', chat)
        async with TestServer(app) as server:
            summary = inspect_rows([{'company_name': 'Secret Alice', 'email': 'secret@example.com'}])
            answer = await ask_german('¿Qué hago?', summary, ModelConfig(base_url=str(server.make_url('')).rstrip('/')))
        self.assertEqual(answer, 'Revisa los unknown.')
        payload = json.dumps(captured)
        self.assertNotIn('secret@example.com', payload)
        self.assertNotIn('Secret Alice', payload)
        self.assertNotIn('tools', captured[0])
        self.assertFalse(captured[0]['think'])

    async def test_malformed_response_is_safe_error(self):
        async def chat(request):
            return web.json_response({'message': {'content': {'run': 'shell'}}})
        app = web.Application()
        app.router.add_post('/api/chat', chat)
        async with TestServer(app) as server:
            with self.assertRaises(ValueError):
                await ask_german('hola', {}, ModelConfig(base_url=str(server.make_url('')).rstrip('/')))

    async def test_optional_local_gateway_token_is_forwarded(self):
        from german_gateway import create_app
        async def backend(request):
            return web.json_response({'message': {'content': 'Consejo desde gateway'}})
        app = web.Application()
        app.router.add_post('/api/chat', backend)
        async with TestServer(app) as backend_server:
            async with TestServer(create_app(token='a'*40, upstream=str(backend_server.make_url('')).rstrip('/'))) as gateway:
                answer = await ask_german('hola', {}, ModelConfig(
                    base_url=str(gateway.make_url('')).rstrip('/'), token='a'*40))
        self.assertEqual(answer, 'Consejo desde gateway')
