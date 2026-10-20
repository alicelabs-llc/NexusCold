"""Exact-domain DNS publication diagnostics, not SPF evaluation or DMARC discovery."""
import asyncio
import re
from datetime import datetime, timezone
import dns.asyncresolver
import dns.exception
import dns.resolver


def validated_domain(domain):
    if not isinstance(domain, str) or any(c.isspace() for c in domain):
        raise ValueError('Dominio inválido.')
    try:
        domain = domain.rstrip('.').encode('idna').decode('ascii').lower()
    except UnicodeError:
        raise ValueError('Dominio inválido.') from None
    if (len(domain) > 253 or '.' not in domain or domain.endswith(('.local', '.localhost', '.internal'))
            or not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}', domain)):
        raise ValueError('Usa un dominio público, sin URL, puerto ni dirección IP.')
    return domain


async def _policy(resolver, name, kind):
    try:
        answers = await resolver.resolve(name, 'TXT', lifetime=4, search=False)
        texts = [b''.join(r.strings).decode('ascii', errors='replace') for r in answers]
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        return {'status': 'missing', 'record': '', 'policy': ''}
    except dns.exception.DNSException:
        return {'status': 'unknown', 'record': '', 'policy': ''}
    prefix = r'^v=spf1(?:\s|$)' if kind == 'spf' else r'^v=DMARC1(?:\s*;|$)'
    records = [text for text in texts if re.match(prefix, text, flags=re.I)]
    if not records:
        return {'status': 'missing', 'record': '', 'policy': ''}
    if len(records) != 1:
        return {'status': 'invalid', 'record': '', 'policy': '', 'reason': 'multiple_records'}
    record = records[0]
    result = {'status': 'published', 'record': record[:4096], 'policy': ''}
    if kind == 'dmarc':
        tags = {}
        for item in record.split(';'):
            if not item.strip():
                continue
            if '=' not in item:
                return {**result, 'status': 'invalid'}
            key, value = (s.strip() for s in item.split('=', 1))
            if key in tags:
                return {**result, 'status': 'invalid', 'reason': 'duplicate_tag'}
            tags[key] = value
        policy = tags.get('p', '')
        if policy not in ('none', 'quarantine', 'reject'):
            return {**result, 'status': 'invalid', 'reason': 'invalid_policy'}
        result.update(policy=policy, status='monitoring' if policy == 'none' else 'published')
    return result


async def check_domain(domain, resolver=None):
    domain = validated_domain(domain)
    resolver = resolver or dns.asyncresolver.Resolver()
    spf, dmarc = await asyncio.gather(_policy(resolver, domain, 'spf'), _policy(resolver, '_dmarc.' + domain, 'dmarc'))
    return {'domain': domain, 'spf': spf, 'dmarc': dmarc, 'dkim': 'selector_required',
            'scope': 'exact_domain_publication_only', 'checked_at': datetime.now(timezone.utc).isoformat(),
            'limitations': 'Sin evaluación de IP SPF, alineamiento, DKIM ni herencia DMARC del dominio organizacional.'}
