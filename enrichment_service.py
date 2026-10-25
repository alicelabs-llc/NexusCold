"""Authenticated, bounded public-website contact extraction for TechDigital.
Run behind HTTPS. No search-engine evasion, proxying or private-network access.
"""
import asyncio
import hmac
import json
import os
import re
import time
from collections import deque
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import aiohttp
from aiohttp import web
from network_safety import PublicResolver, public_http_url, public_trace_config

USER_AGENT = 'TechDigitalProspect/6.4 (+https://techdigital.site/legal/about/)'
SESSION = web.AppKey('session', aiohttp.ClientSession)
MAX_BYTES = 512_000


class ContactParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fields = {}
        self.links = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        href = a.get('href', '')
        if tag == 'a':
            if href.lower().startswith('mailto:'):
                email = href[7:].split('?')[0].strip()
                if re.fullmatch(r'[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}', email, flags=re.ASCII):
                    self.fields.setdefault('email', email[:254])
            elif href.lower().startswith('tel:'):
                phone = href[4:].split('?')[0].strip()
                if re.fullmatch(r'[+\d ().-]{7,32}', phone):
                    self.fields.setdefault('phone', phone)
            elif re.search(r'(?:contact|contacto|about|nosotros)', href, re.I):
                self.links.append(href)
        if tag == 'meta' and (a.get('name', '').lower() == 'description'
                              or a.get('property', '').lower() == 'og:description'):
            self.fields.setdefault('description', a.get('content', '')[:1000])


async def read_bounded(response, limit=MAX_BYTES):
    body = bytearray()
    async for chunk in response.content.iter_chunked(8192):
        body.extend(chunk)
        if len(body) > limit:
            raise ValueError('response_limit')
    return body.decode(response.charset or 'utf-8', errors='replace')


async def crawl_site(session, website):
    """Only the supplied site's origin; redirects are not followed."""
    if not isinstance(website, str) or len(website) > 2048 or not public_http_url(website):
        raise ValueError('public_http_website_required')
    u = urlsplit(website)
    if u.query or u.fragment:
        raise ValueError('website_without_query_required')
    origin = f'{u.scheme}://{u.netloc}'
    robots_url = origin + '/robots.txt'
    parser = RobotFileParser()
    try:
        async with session.get(robots_url, allow_redirects=False) as r:
            if r.status == 404:
                parser.parse([])
            elif r.status == 200:
                parser.parse((await read_bounded(r)).splitlines())
            else:
                return {'fields': {}, 'sources': [], 'errors': ['robots_unavailable_' + str(r.status)]}
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, OSError):
        return {'fields': {}, 'sources': [], 'errors': ['robots_unavailable']}
    delay = parser.crawl_delay('TechDigitalProspect') or parser.crawl_delay('*') or 1
    if delay > 5:
        return {'fields': {}, 'sources': [], 'errors': ['crawl_delay_requires_offline_job']}
    queue = [website]
    visited = set()
    fields, sources, errors = {}, [], []
    page_limit=max(1,min(10,int(os.environ.get('PROSPECT_CRAWL_PAGES','5'))))
    while queue and len(visited) < page_limit:
        url = queue.pop(0)
        if url in visited:
            continue
        target = urlsplit(url)
        if f'{target.scheme}://{target.netloc}' != origin or target.query or target.fragment:
            continue
        visited.add(url)
        if not parser.can_fetch('TechDigitalProspect', url):
            errors.append('robots_disallowed')
            continue
        if len(visited) > 1:
            await asyncio.sleep(max(1, delay))
        try:
            async with session.get(url, allow_redirects=False) as r:
                if r.status != 200:
                    errors.append('site_http_' + str(r.status))
                    continue
                if 'text/html' not in r.headers.get('Content-Type', '').lower():
                    errors.append('html_required')
                    continue
                text = await read_bounded(r)
            page = ContactParser()
            page.feed(text)
            if page.fields:
                sources.append(url)
                for key, value in page.fields.items():
                    fields.setdefault(key, value)
            queue.extend(urljoin(url, link) for link in page.links[:10])
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, OSError):
            errors.append('site_unavailable')
    return {'fields': fields, 'sources': sources, 'errors': list(dict.fromkeys(errors)),
            'pages_checked': len(visited), 'email_status': 'published_not_verified'}


def create_app(*, token=None, allowed_origin=None, crawler=crawl_site):
    token = token if token is not None else os.environ.get('PROSPECT_SERVICE_TOKEN', '')
    origin = allowed_origin or os.environ.get('PROSPECT_ALLOWED_ORIGIN', 'https://techdigital.site')
    if not 32 <= len(token) <= 256 or any(c.isspace() for c in token):
        raise ValueError('PROSPECT_SERVICE_TOKEN requires 32–256 non-whitespace characters')
    parsed = urlsplit(origin)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError('One HTTPS allowed origin is required')
    arrivals = deque()
    active = 0
    sec_cache = []
    sec_cache_at = 0
    sec_lock = asyncio.Lock()

    @web.middleware
    async def cors(request, handler):
        supplied = request.headers.get('Origin')
        if supplied and supplied != origin:
            raise web.HTTPForbidden(text='origin_not_allowed')
        if request.method == 'OPTIONS':
            response = web.Response(status=204)
        else:
            try:
                response = await handler(request)
            except web.HTTPException as exc:
                response = web.Response(status=exc.status, text=exc.text, headers=exc.headers)
        response.headers.update({'Access-Control-Allow-Origin': origin, 'Vary': 'Origin',
                                 'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
                                 'Access-Control-Allow-Headers': 'Authorization, Content-Type',
                                 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
        return response

    app = web.Application(client_max_size=4096, middlewares=[cors])

    async def lifecycle(app):
        connector = aiohttp.TCPConnector(resolver=PublicResolver(), limit=4)
        async with aiohttp.ClientSession(connector=connector, trust_env=False,
                timeout=aiohttp.ClientTimeout(total=8), headers={'User-Agent': USER_AGENT},
                trace_configs=[public_trace_config()]) as session:
            app[SESSION] = session
            yield
    app.cleanup_ctx.append(lifecycle)

    async def health(request):
        return web.json_response({'status': 'ready', 'capabilities': ['published_website_contacts'],
                                  'pages_per_request': max(1,min(10,int(os.environ.get('PROSPECT_CRAWL_PAGES','5')))), 'web_search': 'brave' if os.environ.get('BRAVE_SEARCH_API_KEY') else 'not_configured', 'registry_sources': ['npi', 'sec'], 'authentication': 'bearer_required'})

    async def enrich(request):
        nonlocal active
        if not hmac.compare_digest(request.headers.get('Authorization', '').encode(), ('Bearer ' + token).encode()):
            raise web.HTTPUnauthorized(text='authentication_required')
        try:
            data = await request.json()
            if not isinstance(data, dict) or set(data) != {'website'} or not isinstance(data['website'], str) or not public_http_url(data['website']):
                raise ValueError()
        except (ValueError, TypeError, UnicodeError):
            raise web.HTTPBadRequest(text='one_public_website_required') from None
        now = time.monotonic()
        while arrivals and arrivals[0] < now - 60:
            arrivals.popleft()
        if active >= 2 or len(arrivals) >= 20:
            raise web.HTTPTooManyRequests(headers={'Retry-After': '60'})
        arrivals.append(now)
        active += 1
        try:
            result = await asyncio.wait_for(crawler(app[SESSION], data['website']), timeout=35)
            return web.json_response(result)
        except ValueError:
            raise web.HTTPBadRequest(text='invalid_website') from None
        except (asyncio.TimeoutError, aiohttp.ClientError, OSError):
            raise web.HTTPBadGateway(text='source_unavailable') from None
        finally:
            active -= 1

    async def discover(request):
        nonlocal active
        if not hmac.compare_digest(request.headers.get('Authorization', '').encode(), ('Bearer ' + token).encode()):
            raise web.HTTPUnauthorized(text='authentication_required')
        key = os.environ.get('BRAVE_SEARCH_API_KEY', '')
        if not key:
            raise web.HTTPServiceUnavailable(text='web_search_not_configured')
        try:
            data = await request.json()
            if not isinstance(data, dict) or set(data) != {'company', 'city'}:
                raise ValueError()
            if not all(isinstance(data[k], str) and len(data[k]) <= 150 for k in data) or not data['company'].strip():
                raise ValueError()
        except (ValueError, TypeError, UnicodeError):
            raise web.HTTPBadRequest(text='bounded_company_city_required') from None
        now = time.monotonic()
        while arrivals and arrivals[0] < now - 60:
            arrivals.popleft()
        if active >= 2 or len(arrivals) >= 20:
            raise web.HTTPTooManyRequests(headers={'Retry-After': '60'})
        arrivals.append(now)
        active += 1
        try:
            async with app[SESSION].get('https://api.search.brave.com/res/v1/web/search',
                    params={'q': data['company'] + ' ' + data['city'] + ' official contact', 'count': '10'},
                    headers={'X-Subscription-Token': key, 'Accept': 'application/json'}, allow_redirects=False) as response:
                if response.status != 200:
                    raise web.HTTPBadGateway(text='search_provider_http_' + str(response.status))
                payload = json.loads(await read_bounded(response))
            candidates = []
            for item in payload.get('web', {}).get('results', [])[:10]:
                url = item.get('url', '')
                if not public_http_url(url):
                    continue
                target = urlsplit(url)
                candidates.append({'id': url, 'provider': 'Web', 'label': str(item.get('title', ''))[:200],
                    'description': str(item.get('description', ''))[:500], 'fields': {'website': target.scheme + '://' + target.netloc},
                    'source': url})
            return web.json_response({'candidates': candidates, 'provider': 'Brave Search',
                                      'scope': 'web_index_top_results_not_entire_internet'})
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError):
            raise web.HTTPBadGateway(text='search_provider_unavailable') from None
        finally:
            active -= 1

    async def registry(request):
        nonlocal active, sec_cache, sec_cache_at
        if not hmac.compare_digest(request.headers.get('Authorization', '').encode(), ('Bearer ' + token).encode()):
            raise web.HTTPUnauthorized(text='authentication_required')
        provider = request.match_info['provider']
        if provider not in ('npi', 'sec'):
            raise web.HTTPNotFound(text='registry_not_supported')
        try:
            data = await request.json()
            if (not isinstance(data, dict) or set(data) != {'company', 'city'}
                    or not all(isinstance(data[k], str) and len(data[k]) <= 150 for k in data)
                    or len(data['company'].strip()) < 2):
                raise ValueError()
        except (ValueError, TypeError, UnicodeError):
            raise web.HTTPBadRequest(text='bounded_company_city_required') from None
        now = time.monotonic()
        while arrivals and arrivals[0] < now - 60:
            arrivals.popleft()
        if active >= 2 or len(arrivals) >= 20:
            raise web.HTTPTooManyRequests(headers={'Retry-After': '60'})
        arrivals.append(now)
        active += 1
        try:
            candidates = []
            if provider == 'npi':
                params = {'version':'2.1', 'organization_name':data['company'],
                          'enumeration_type':'NPI-2', 'limit':'5'}
                if data['city'].strip():
                    params['city'] = data['city']
                async with app[SESSION].get('https://npiregistry.cms.hhs.gov/api/', params=params,
                                           allow_redirects=False) as response:
                    if response.status != 200:
                        raise web.HTTPBadGateway(text='NPI_http_' + str(response.status))
                    payload = json.loads(await read_bounded(response))
                if payload.get('Errors'):
                    raise web.HTTPBadGateway(text='NPI_query_rejected')
                for item in payload.get('results', [])[:5]:
                    if item.get('enumeration_type') != 'NPI-2':
                        continue
                    number = str(item.get('number', ''))
                    basic = item.get('basic', {})
                    location = next((a for a in item.get('addresses', []) if a.get('address_purpose') == 'LOCATION'), {})
                    if not re.fullmatch(r'\d{10}', number) or not basic.get('organization_name'):
                        continue
                    specialty = next((t.get('desc', '') for t in item.get('taxonomies', []) if t.get('primary')), '')
                    candidates.append({'provider':'npi', 'id':number, 'label':basic['organization_name'],
                        'description':location.get('city', ''), 'source':'https://npiregistry.cms.hhs.gov/api/?version=2.1&number='+number,
                        'fields': {'legal_name':basic['organization_name'], 'phone':location.get('telephone_number', ''),
                            'headquarters':', '.join(str(location[k]) for k in ['address_1','address_2','city','state','postal_code'] if location.get(k)),
                            'country':location.get('country_code', ''), 'industry':specialty,
                            'registry_status':basic.get('status', ''), 'identifiers':json.dumps({'npi':number})}})
            else:
                async with sec_lock:
                    if not sec_cache or time.monotonic() - sec_cache_at > 86400:
                        async with app[SESSION].get('https://www.sec.gov/files/company_tickers.json',
                            headers={'User-Agent':'TechDigitalProspect support@alicelabs.site'}, allow_redirects=False) as response:
                            if response.status != 200:
                                raise web.HTTPBadGateway(text='SEC_http_' + str(response.status))
                            payload = json.loads(await read_bounded(response, limit=2_000_000))
                        if not isinstance(payload, dict):
                            raise ValueError('SEC_schema')
                        sec_cache = [r for r in payload.values() if isinstance(r, dict) and r.get('title') and r.get('cik_str')]
                        sec_cache_at = time.monotonic()
                words = re.findall(r'[a-z0-9]+', data['company'].lower())
                for item in sec_cache:
                    if not words or not all(w in item['title'].lower() for w in words):
                        continue
                    cik = str(item['cik_str']).zfill(10)
                    if not re.fullmatch(r'\d{10}', cik):
                        continue
                    candidates.append({'provider':'sec', 'id':cik, 'label':item['title'],
                        'description':str(item.get('ticker', '')), 'source':'https://data.sec.gov/submissions/CIK'+cik+'.json',
                        'fields': {'legal_name':item['title'],
                            'identifiers':json.dumps({'sec_cik':cik, 'ticker':str(item.get('ticker', ''))})}})
                    if len(candidates) >= 5:
                        break
            return web.json_response({'provider':provider, 'candidates':candidates})
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError):
            raise web.HTTPBadGateway(text='registry_unavailable') from None
        finally:
            active -= 1

    app.router.add_get('/health', health)
    app.router.add_post('/api/enrich', enrich)
    app.router.add_post('/api/discover', discover)
    app.router.add_post('/api/registry/{provider}', registry)
    async def options(request):
        return web.Response(status=204)
    app.router.add_options('/api/enrich', options)
    app.router.add_options('/api/discover', options)
    app.router.add_options('/api/registry/{provider}', options)
    return app


if __name__ == '__main__':
    web.run_app(create_app(), host=os.environ.get('PROSPECT_BIND', '127.0.0.1'),
                port=int(os.environ.get('PORT', '8081')), access_log=None)
