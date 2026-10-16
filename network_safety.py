"""Allow enrichment requests only to public HTTP(S) destinations."""
import ipaddress
import socket
from urllib.parse import urlsplit, urljoin

from aiohttp import TraceConfig
from aiohttp.abc import AbstractResolver
from aiohttp.resolver import DefaultResolver


def public_http_url(url):
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        if (parsed.scheme not in ('http', 'https') or not host or parsed.username
                or parsed.password or parsed.port not in (None, 80, 443)):
            return False
        if host.lower() == 'localhost' or host.lower().endswith(('.localhost', '.local', '.internal')):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return '.' in host and not any(char.isspace() for char in host)
    except ValueError:
        return False


class PublicResolver(AbstractResolver):
    """Validate actual connection addresses, including HTTP redirect destinations."""
    def __init__(self):
        self._resolver = DefaultResolver()

    async def resolve(self, host, port=0, family=socket.AF_INET):
        records = await self._resolver.resolve(host, port, family)
        if not records or any(not ipaddress.ip_address(record['host']).is_global for record in records):
            raise OSError('Non-public enrichment destination blocked')
        return records

    async def close(self):
        await self._resolver.close()


def public_trace_config():
    # aiohttp bypasses DNS resolution for IP literals. Check them before requests
    # and before following each redirect, in addition to validating resolved IPs.
    trace = TraceConfig()

    async def start(session, context, params):
        if not public_http_url(str(params.url)):
            raise OSError('Non-public or unsupported enrichment URL blocked')

    async def redirect(session, context, params):
        location = params.response.headers.get('Location') or params.response.headers.get('URI')
        if location and not public_http_url(urljoin(str(params.response.url), location)):
            raise OSError('Non-public or unsupported enrichment redirect blocked')

    trace.on_request_start.append(start)
    trace.on_request_redirect.append(redirect)
    return trace
