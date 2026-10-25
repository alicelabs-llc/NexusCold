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

@pytest.mark.asyncio
async def test_web_index_discovery_requires_auth_and_configured_key(monkeypatch):
    monkeypatch.delenv('BRAVE_SEARCH_API_KEY', raising=False)
    async with TestClient(TestServer(create_app(token='a'*32))) as client:
        r = await client.post('/api/discover', json={'company': 'Example', 'city': ''})
        assert r.status == 401
        r = await client.post('/api/discover', headers={'Authorization': 'Bearer '+'a'*32}, json={'company':'Example','city':''})
        assert r.status == 503
        assert await r.text() == 'web_search_not_configured'

@pytest.mark.asyncio
async def test_npi_returns_corporate_phone_without_officer_details():
    import json
    from enrichment_service import SESSION
    class RegistrySession:
        def get(self, url, **kwargs):
            assert url == 'https://npiregistry.cms.hhs.gov/api/'
            assert kwargs['params']['enumeration_type'] == 'NPI-2'
            return Response(json.dumps({'results':[{'number':1234567890,'enumeration_type':'NPI-2',
                'basic':{'organization_name':'Example Clinic','status':'A','authorized_official_first_name':'PRIVATE'},
                'addresses':[{'address_purpose':'LOCATION','telephone_number':'5551234567','city':'Boston','country_code':'US'}],
                'taxonomies':[{'primary':True,'desc':'Clinic'}]}]}))
    async with TestClient(TestServer(create_app(token='a'*32))) as client:
        client.app[SESSION] = RegistrySession()
        r = await client.post('/api/registry/npi', headers={'Authorization':'Bearer '+'a'*32}, json={'company':'Example Clinic','city':''})
        assert r.status == 200
        data = await r.json()
        assert data['candidates'][0]['fields']['phone'] == '5551234567'
        assert 'PRIVATE' not in json.dumps(data)


@pytest.mark.asyncio
async def test_sec_dataset_is_cached_without_guessing_websites_or_active_status():
    import json
    from enrichment_service import SESSION
    calls = []
    class RegistrySession:
        def get(self, url, **kwargs):
            calls.append(url)
            assert url == 'https://www.sec.gov/files/company_tickers.json'
            return Response(json.dumps({'0':{'cik_str':789019,'title':'MICROSOFT CORP','ticker':'MSFT'}}))
    async with TestClient(TestServer(create_app(token='a'*32))) as client:
        client.app[SESSION] = RegistrySession()
        for _ in range(2):
            r = await client.post('/api/registry/sec', headers={'Authorization':'Bearer '+'a'*32}, json={'company':'Microsoft','city':''})
            assert r.status == 200
            fields = (await r.json())['candidates'][0]['fields']
            assert json.loads(fields['identifiers'])['sec_cik'] == '0000789019'
            assert 'website' not in fields and 'registry_status' not in fields
        assert len(calls) == 1


@pytest.mark.asyncio
async def test_registry_routes_require_auth_and_fixed_provider_allowlist():
    async with TestClient(TestServer(create_app(token='a'*32))) as client:
        r = await client.post('/api/registry/npi',json={'company':'Example','city':''})
        assert r.status == 401
        r = await client.post('/api/registry/arbitrary',headers={'Authorization':'Bearer '+'a'*32},json={'company':'Example','city':''})
        assert r.status == 404
