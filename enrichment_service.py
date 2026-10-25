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


async def read_bounded(response):
    body = bytearray()
    async for chunk in response.content.iter_chunked(8192):
        body.extend(chunk)
        if len(body) > MAX_BYTES:
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
    while queue and len(visited) < 3:
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
                                  'pages_per_request': 3, 'authentication': 'bearer_required'})

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

    app.router.add_get('/health', health)
    app.router.add_post('/api/enrich', enrich)
    async def options(request):
        return web.Response(status=204)
    app.router.add_options('/api/enrich', options)
    return app


if __name__ == '__main__':
    web.run_app(create_app(), host=os.environ.get('PROSPECT_BIND', '127.0.0.1'),
                port=int(os.environ.get('PORT', '8081')), access_log=None)
