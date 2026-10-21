import unittest
from aiohttp import web
from aiohttp.test_utils import TestServer, TestClient
from german_gateway import create_app

TOKEN = 'a' * 40


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_requires_strong_secret(self):
        for token in ['', 'short', 'change-me']:
            with self.assertRaises(ValueError):
                create_app(token=token)

    async def test_auth_routes_and_fixed_model_over_real_http(self):
        calls = []
        async def backend(request):
            calls.append(await request.json())
            return web.json_response({'message': {'content': 'Respuesta controlada'}})
        upstream = web.Application()
        upstream.router.add_post('/api/chat', backend)
        async with TestServer(upstream) as server:
            async with TestClient(TestServer(create_app(token=TOKEN, upstream=str(server.make_url('')).rstrip('/')))) as client:
                self.assertEqual((await client.post('/api/chat', json={})).status, 401)
                self.assertEqual((await client.post('/api/pull', headers={'Authorization': 'Bearer '+TOKEN})).status, 404)
                response = await client.post('/api/chat', json={'model': 'huge:cloud', 'stream': True,
                    'options': {'num_predict': 999999}, 'messages': [{'role': 'user', 'content': 'hola'}]},
                    headers={'Authorization': 'Bearer '+TOKEN})
                self.assertEqual(response.status, 200)
                self.assertEqual((await response.json())['message']['content'], 'Respuesta controlada')
                self.assertEqual(calls[0]['model'], 'qwen3.5:4b')
                self.assertEqual(calls[0]['options']['num_predict'], 512)
                self.assertFalse(calls[0]['stream'])
                too_big = await client.post('/api/chat', data='x'*18000, headers={'Authorization': 'Bearer '+TOKEN})
                self.assertEqual(too_big.status, 413)

    async def test_rejects_arbitrary_tool_or_image_payload(self):
        async with TestClient(TestServer(create_app(token=TOKEN))) as client:
            for messages in [[], 'not a list', [{'role': 'user', 'content': 'hello', 'images': ['base64']}],
                             [{'role': 'assistant', 'content': 'hello'}]]:
                response = await client.post('/api/chat', json={'messages': messages},
                    headers={'Authorization': 'Bearer '+TOKEN})
                self.assertEqual(response.status, 400)

    async def test_rate_limit_and_unavailable_backend(self):
        async def backend(request):
            return web.Response(status=503)
        upstream = web.Application()
        upstream.router.add_post('/api/chat', backend)
        async with TestServer(upstream) as server:
            async with TestClient(TestServer(create_app(token=TOKEN, limit_per_minute=1,
                    upstream=str(server.make_url('')).rstrip('/')))) as client:
                data = {'messages': [{'role': 'user', 'content': 'hello'}]}
                headers = {'Authorization': 'Bearer '+TOKEN}
                self.assertEqual((await client.post('/api/chat', json=data, headers=headers)).status, 502)
                self.assertEqual((await client.post('/api/chat', json=data, headers=headers)).status, 429)
