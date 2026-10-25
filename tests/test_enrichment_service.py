import pytest
from aiohttp.test_utils import TestClient, TestServer
from enrichment_service import ContactParser, create_app, crawl_site


def test_contact_parser_only_observed_contact_links():
    p = ContactParser()
    p.feed('<a href="mailto:sales@example.org">Email</a><a href="tel:+1234567890">Call</a><meta name="description" content="Widgets"><a href="/contact">Contact</a><script>"fake@other.org"</script>')
    assert p.fields == {'email': 'sales@example.org', 'phone': '+1234567890', 'description': 'Widgets'}
    assert p.links == ['/contact']


def test_token_required():
    with pytest.raises(ValueError):
        create_app(token='short')


@pytest.mark.asyncio
async def test_auth_origin_and_private_destination_blocking():
    calls = []
    async def crawler(session, website):
        calls.append(website)
        return {'fields': {'email': 'info@example.org'}, 'sources': [website], 'errors': []}
    async with TestClient(TestServer(create_app(token='a'*32, crawler=crawler))) as client:
        r = await client.post('/api/enrich', json={'website': 'https://example.org'})
        assert r.status == 401
        auth = {'Authorization': 'Bearer ' + 'a'*32, 'Origin': 'https://techdigital.site'}
        r = await client.post('/api/enrich', headers=auth, json={'website': 'http://127.0.0.1'})
        assert r.status == 400
        r = await client.post('/api/enrich', headers={**auth, 'Origin': 'https://evil.example'}, json={'website': 'https://example.org'})
        assert r.status == 403
        r = await client.post('/api/enrich', headers=auth, json={'website': 'https://example.org'})
        assert r.status == 200
        assert (await r.json())['fields']['email'] == 'info@example.org'
        assert r.headers['Access-Control-Allow-Origin'] == 'https://techdigital.site'
        assert calls == ['https://example.org']


class Response:
    def __init__(self, text, status=200):
        self.status = status
        self.headers = {'Content-Type': 'text/html'}
        self.charset = 'utf-8'
        self.content = self
        self.text = text.encode()
    async def iter_chunked(self, size):
        yield self.text
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass


@pytest.mark.asyncio
async def test_robots_denies_scrape_and_never_follows_redirect():
    calls = []
    class Session:
        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            return Response('User-agent: *\nDisallow: /')
    result = await crawl_site(Session(), 'https://example.org')
    assert not result['fields']
    assert result['errors'] == ['robots_disallowed']
    assert len(calls) == 1
    assert calls[0][1]['allow_redirects'] is False
