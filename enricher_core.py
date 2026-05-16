"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  AliceLabs Nexus PRO v6.0 — WORLD EDITION Enrichment Engine                ║
║  Multi-source parallel enrichment with 20+ workers                         ║
║  Global coverage: USA, UK, EU, LATAM, AU, IN, SG, HK + more               ║
║  Sources: DDG, Bing, Google, Clearbit, SAM.gov, OpenCorporates,           ║
║           UK Companies House, BR CNPJ, EU VAT, Website Scraping            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import aiohttp
import re
import json
import time
import random
import hashlib
import os
from urllib.parse import quote_plus, urlparse, unquote
from dataclasses import dataclass, asdict
from typing import Optional, Callable, List
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / ".nexus_cache"
CACHE_DIR.mkdir(exist_ok=True)
CACHE_FILE = CACHE_DIR / "enrichment_cache.json"
RATE_FILE = CACHE_DIR / "rate_limits.json"

# User Agents rotativos
UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
]

CACHE_TTL = 86400  # 24h
RATE_WINDOW = 60   # segundos
RATE_MAX = 10      # calls por ventana

# Proxies (rellenar si se usan)
PROXY_LIST = []  # ["http://user:pass@host:port", "socks5://host:port"]
PROXY_ROTATE = bool(PROXY_LIST)

# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASS — EnrichedCompany WORLD EDITION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class EnrichedCompany:
    # Input
    company_name: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    region: str = ""

    # Identity
    website: str = ""
    domain: str = ""
    description: str = "Analyzing..."
    industry: str = "B2B / Professional Services"
    business_type: str = ""

    # Contact
    email: str = ""
    emails_all: str = ""
    phone: str = ""
    address: str = ""

    # Digital
    linkedin: str = ""
    facebook: str = ""
    twitter: str = ""
    instagram: str = ""
    youtube: str = ""

    # Global Tax/Registration IDs
    duns: str = ""
    ein: str = ""
    ruc: str = ""
    vat: str = ""
    cnpj: str = ""
    rfc: str = ""
    rut: str = ""
    nif: str = ""
    abn: str = ""
    cin: str = ""
    company_number: str = ""
    sic_code: str = ""

    # Business Data
    employees: str = ""
    revenue: str = ""
    founded: str = ""

    # Control
    status: str = "pending"
    sources_used: str = ""
    confidence: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL REGEX PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

EMAIL_RE = re.compile(
    r'[a-zA-Z0-9][a-zA-Z0-9._%+\-]*@[a-zA-Z0-9][a-zA-Z0-9.\-]*\.[a-zA-Z]{2,}',
    re.IGNORECASE
)

PHONE_RE = re.compile(
    r'(?:\+?\d{1,3}[\s.\-]?)?\(?\d{2,4}\)?[\s.\-]?\d{3,4}[\s.\-]?\d{3,4}'
)

DUNS_RE = re.compile(r'\bDUNS[:\s#]*(\d{2}-\d{3}-\d{4}|\d{9})\b', re.I)
RUC_RE = re.compile(r'\b(?:10|20)\d{9}\b')

# EU VAT: GB123456789, DE123456789, FR12345678901, IT12345678901, etc.
VAT_RE = re.compile(
    r'\b(?:ATU\d{8}|BE0\d{9}|BG\d{9,10}|CY\d{8}[A-Z]|CZ\d{8,10}|DE\d{9}|'
    r'DK\d{8}|EE\d{9}|EL\d{9}|ES\d{9}|FI\d{8}|FR[A-HJ-NP-Z0-9]{11}|'
    r'GB\d{9}|GBGD\d{3}|GBHA\d{3}|GR\d{9}|HR\d{11}|HU\d{8}|'
    r'Ie\w{8}\w|IT\d{11}|LT\d{9,12}|LU\d{8}|LV\d{11}|MT\d{8}|'
    r'NL\d{9}B\d{2}|PL\d{10}|PT\d{9}|RO\d{2,10}|SE\d{12}|'
    r'SI\d{8}|SK\d{10})\b',
    re.I
)

# Brazil CNPJ: XX.XXX.XXX/XXXX-XX or XXXXXXXXXXXXXX
CNPJ_RE = re.compile(r'\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b|\b\d{14}\b')

# Mexico RFC: XXXX123456XXX
RFC_RE = re.compile(r'\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{2,3}\b')

# Chile RUT: 12345678-9 or 12.345.678-9
RUT_RE = re.compile(r'\b\d{1,2}\.?\d{3}\.?\d{3}[-][0-9Kk]\b')

# Spain/Portugal NIF: 12345678X
NIF_RE = re.compile(r'\b\d{8}[A-Z]\b')

# Australia ABN: XX XXX XXX XXX
ABN_RE = re.compile(r'\b\d{2}\s?\d{3}\s?\d{3}\s?\d{3}\b')

# India CIN: L12345XX1234XXX123456
CIN_RE = re.compile(r'\b[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b')

# UK Company Number: 01234567, SC123456, NI123456, OC123456
UK_COMPANY_RE = re.compile(r'\b(?:SC|NI|OC|RC|LP|NL|SO|IP)\d{5,8}\b|\b\d{8}\b')

# Emails genéricos a ignorar
SKIP_EMAILS = {
    'example@', 'test@', 'noreply@', 'no-reply@', 'support@', 'privacy@',
    'legal@', 'abuse@', 'postmaster@', 'admin@', 'webmaster@', 'info@',
    'hello@', 'contact@', 'mail@', 'email@', 'hostmaster@', 'noreply',
    'donotreply@', 'do-not-reply@'
}

# Dominios a ignorar como website de empresa
BLACKLIST_DOMAINS = {
    'facebook.com', 'linkedin.com', 'twitter.com', 'x.com', 'yelp.com',
    'yellowpages.com', 'manta.com', 'bbb.org', 'google.com',
    'bing.com', 'wikipedia.org', 'bloomberg.com', 'zoominfo.com',
    'dnb.com', 'hoovers.com', 'crunchbase.com', 'glassdoor.com',
    'indeed.com', 'sec.gov', 'sam.gov', 'opencorporates.com',
    'instagram.com', 'youtube.com', 'tiktok.com', 'pinterest.com',
    'github.com', 'gitlab.com', 'bitbucket.org', 'myspace.com',
    'angel.co', 'wellfound.com', 'producthunt.com', 'g2.com',
    'capterra.com', 'trustpilot.com', 'yelp.ca', 'yelp.com.au',
    'tripadvisor.com', 'yelp.co.uk', 'hotfrog.com', 'superpages.com',
    'whitepages.com', 'merchantcircle.com', 'citysearch.com',
    'kudzu.com', 'showmelocal.com', 'brownbook.net', 'mondo.com',
    'allbusiness.com'
}

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def random_headers():
    return {
        "User-Agent": random.choice(UA_POOL),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }

def clean_email(e: str) -> Optional[str]:
    e = e.lower().strip().rstrip('.')
    if not e or '@' not in e:
        return None
    if any(s in e for s in SKIP_EMAILS):
        return None
    if len(e) > 80:
        return None
    local, domain = e.split('@', 1)
    if len(local) < 2 or len(domain) < 4:
        return None
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._%+\-]*@[a-zA-Z0-9][a-zA-Z0-9.\-]*\.[a-zA-Z]{2,}$', e):
        return None
    return e

def clean_phone(raw: str) -> Optional[str]:
    digits = re.sub(r'\D', '', raw.strip())
    if len(digits) == 10:
        digits = '1' + digits
    if len(digits) == 11 and digits[0] == '1':
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    elif 7 <= len(digits) <= 15:
        return f"+{digits}"
    return None

def extract_domain(url: str) -> Optional[str]:
    if not url:
        return None
    try:
        url = url.split(' ')[0].split('?')[0].split('#')[0].rstrip('/')
        if not url.startswith('http'):
            url = 'http://' + url
        p = urlparse(url)
        d = p.netloc.lower().replace('www.', '')
        return d if '.' in d else None
    except:
        return None

def is_valid_website(url: str) -> bool:
    if not url:
        return False
    url = url.split(' ')[0]
    domain = extract_domain(url)
    if not domain:
        return False
    return domain not in BLACKLIST_DOMAINS

def get_cache_key(company: EnrichedCompany) -> str:
    raw = f"{company.company_name}|{company.city}|{company.state}|{company.country}"
    return hashlib.md5(raw.encode()).hexdigest()

def load_cache() -> dict:
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_cache(cache: dict):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, default=str)
    except:
        pass

def load_rate_limits() -> dict:
    try:
        if RATE_FILE.exists():
            with open(RATE_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_rate_limits(rates: dict):
    try:
        with open(RATE_FILE, 'w') as f:
            json.dump(rates, f)
    except:
        pass

def check_rate_limit(domain: str) -> bool:
    """Returns True if request is allowed, False if rate limited"""
    rates = load_rate_limits()
    now = time.time()
    entry = rates.get(domain, {"calls": 0, "window_start": now})
    if now - entry["window_start"] > RATE_WINDOW:
        entry = {"calls": 0, "window_start": now}
    if entry["calls"] >= RATE_MAX:
        return False
    entry["calls"] += 1
    rates[domain] = entry
    save_rate_limits(rates)
    return True

def get_proxy() -> Optional[str]:
    if PROXY_LIST:
        return random.choice(PROXY_LIST)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# FUENTE 1: DuckDuckGo
# ═══════════════════════════════════════════════════════════════════════════════

async def source_ddg(session: aiohttp.ClientSession, company: str, city: str = "", state: str = "") -> dict:
    try:
        q = f'"{company}" {city} {state} official website'.strip()
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(q)}"
        async with session.get(url, headers=random_headers(), timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status != 200:
                return {}
            text = await r.text(errors='ignore')

            # Try to extract from href uddg parameter first (more reliable)
            uddg_urls = re.findall(r'uddg=([^&"]+)', text)
            for u in uddg_urls:
                u = unquote(u)
                if is_valid_website(u):
                    return {'website': u, 'domain': extract_domain(u), 'source': 'ddg'}

            # Fallback to text extraction
            urls = re.findall(r'class="result__url"[^>]*>(.*?)<', text, re.S)
            for raw_url in urls:
                raw_url = re.sub(r'<[^>]+>', '', raw_url).strip()
                if not raw_url: continue
                if not raw_url.startswith('http'):
                    raw_url = 'https://' + raw_url
                if is_valid_website(raw_url):
                    return {'website': raw_url, 'domain': extract_domain(raw_url), 'source': 'ddg'}

    except:
        pass
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# FUENTE 2: Bing
# ═══════════════════════════════════════════════════════════════════════════════

async def source_bing(session: aiohttp.ClientSession, company: str, city: str = "", state: str = "") -> dict:
    try:
        q = f'"{company}" {city} {state} contact email'.strip()
        url = f"https://www.bing.com/search?q={quote_plus(q)}&count=10"
        async with session.get(url, headers=random_headers(), timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status != 200:
                return {}
            text = await r.text(errors='ignore')
            emails = [clean_email(e) for e in EMAIL_RE.findall(text) if clean_email(e)]

            # Expanded patterns for Bing
            patterns = [
                r'<cite[^>]*>([^<]+)</cite>',
                r'<h2><a[^>]+href="([^"]+)"',
                r'class="b_algo">.*?href="([^"]+)"'
            ]

            website = ""
            for pat in patterns:
                urls = re.findall(pat, text, re.S)
                for u in urls:
                    u = re.sub(r'<[^>]+>', '', u).strip()
                    if not u.startswith('http'):
                        u = 'https://' + u
                    if is_valid_website(u):
                        website = u
                        break
                if website: break

            result = {'source': 'bing'}
            if emails:
                result['email'] = emails[0]
                result['emails_all'] = ','.join(emails[:5])
            if website:
                result['website'] = website
                result['domain'] = extract_domain(website)
            return result
    except:
        pass
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# FUENTE 3: Google
# ═══════════════════════════════════════════════════════════════════════════════

async def source_google(session: aiohttp.ClientSession, company: str, city: str = "", state: str = "") -> dict:
    try:
        q = f'"{company}" {city} {state} website'.strip()
        url = f"https://www.google.com/search?q={quote_plus(q)}"
        async with session.get(url, headers=random_headers(), timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status != 200:
                return {}
            text = await r.text(errors='ignore')

            # Expanded patterns for Google
            patterns = [
                r'href="/url\?q=([^&]+)',
                r'<(?:div|span) [^>]*data-ved=[^>]*><a [^>]*href="([^"]+)"',
                r'href="(https?://[^"]+)"[^>]*><h3'
            ]

            found = False
            for pat in patterns:
                links = re.findall(pat, text)
                for l in links:
                    l = unquote(l)
                    if is_valid_website(l):
                        return {'website': l, 'domain': extract_domain(l), 'source': 'google'}

    except:
        pass
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# FUENTE 4: Clearbit Autocomplete
# ═══════════════════════════════════════════════════════════════════════════════

async def source_clearbit(session: aiohttp.ClientSession, company: str) -> dict:
    try:
        url = f"https://autocomplete.clearbit.com/v1/companies/suggest?query={quote_plus(company)}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status != 200:
                return {}
            data = await r.json()
            if not data:
                return {}
            c = data[0]
            result = {'source': 'clearbit'}
            if c.get('domain'):
                result['domain'] = c['domain']
                result['website'] = 'https://' + c['domain']
            if c.get('name'):
                result['company_name'] = c['name']
            return result
    except:
        pass
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# FUENTE 5: Website Scraping (Directo + Contact + About)
# ═══════════════════════════════════════════════════════════════════════════════

async def source_website(session: aiohttp.ClientSession, website: str) -> dict:
    if not website:
        return {}
    result = {'source': 'website'}
    pages_to_check = [
        website,
        website.rstrip('/') + '/contact',
        website.rstrip('/') + '/about',
        website.rstrip('/') + '/contact-us',
        website.rstrip('/') + '/about-us',
    ]
    all_emails, all_phones, all_vat, all_cnpj, all_rfc, all_rut = [], [], [], [], [], []
    domain = extract_domain(website)

    for page_url in pages_to_check:
        try:
            async with session.get(
                page_url, headers=random_headers(),
                timeout=aiohttp.ClientTimeout(total=6),
                allow_redirects=True, max_redirects=3
            ) as r:
                if r.status not in (200, 201, 202):
                    continue
                ct = r.headers.get('Content-Type', '')
                if 'html' not in ct and 'text' not in ct:
                    continue
                text = await r.text(errors='ignore')

                # Emails
                emails = [clean_email(e) for e in EMAIL_RE.findall(text) if clean_email(e)]
                all_emails.extend(emails)

                # Phones
                for m in PHONE_RE.finditer(text):
                    cleaned = clean_phone(m.group(0))
                    if cleaned:
                        all_phones.append(cleaned)

                # Global Tax IDs
                vats = VAT_RE.findall(text)
                all_vat.extend(vats)
                all_cnpj.extend(CNPJ_RE.findall(text))
                all_rfc.extend(RFC_RE.findall(text))
                all_rut.extend(RUT_RE.findall(text))

                # RUC (Peru)
                if not result.get('ruc'):
                    ruc = RUC_RE.search(text)
                    if ruc:
                        result['ruc'] = ruc.group(0)

                # DUNS
                if not result.get('duns'):
                    duns = DUNS_RE.search(text)
                    if duns:
                        result['duns'] = duns.group(1)

                # NIF (Spain)
                if not result.get('nif'):
                    nif = NIF_RE.search(text)
                    if nif:
                        result['nif'] = nif.group(0)

                # ABN (Australia)
                if not result.get('abn'):
                    abn = ABN_RE.search(text)
                    if abn:
                        result['abn'] = abn.group(0)

                # CIN (India)
                if not result.get('cin'):
                    cin = CIN_RE.search(text)
                    if cin:
                        result['cin'] = cin.group(0)

                # UK Company Number
                if not result.get('company_number'):
                    uk = UK_COMPANY_RE.search(text)
                    if uk:
                        result['company_number'] = uk.group(0)

                # LinkedIn
                if not result.get('linkedin'):
                    li = re.search(r'linkedin\.com/company/([^"\'<>\s/?#]+)', text)
                    if li and li.group(1) not in ('login', 'signup'):
                        result['linkedin'] = f"https://linkedin.com/company/{li.group(1)}"

                # Facebook
                if not result.get('facebook'):
                    fb = re.search(r'facebook\.com/([^"\'<>\s/?#]+)', text)
                    if fb and fb.group(1) not in ('sharer', 'share', 'login', 'home', 'plugins', 'groups', 'pages', 'events', 'help'):
                        result['facebook'] = f"https://facebook.com/{fb.group(1)}"

                # Twitter/X
                if not result.get('twitter'):
                    tw = re.search(r'(?:twitter|x)\.com/([^"\'<>\s/?#]+)', text)
                    if tw and tw.group(1) not in ('home', 'share', 'intent', 'search', 'notifications', 'explore'):
                        result['twitter'] = f"https://twitter.com/{tw.group(1)}"

                # Instagram
                if not result.get('instagram'):
                    ig = re.search(r'instagram\.com/([^"\'<>\s/?#]+)', text)
                    if ig and ig.group(1) not in ('p', 'explore', 'accounts', 'about', 'login'):
                        result['instagram'] = f"https://instagram.com/{ig.group(1)}"

                # YouTube
                if not result.get('youtube'):
                    yt = re.search(r'youtube\.com/(?:channel/|@|c/|user/)([^"\'<>\s/?#]+)', text)
                    if yt:
                        result['youtube'] = f"https://youtube.com/@{yt.group(1)}"

                # Meta description
                if not result.get('description') or result.get('description') == '':
                    meta = re.search(
                        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']{15,300})',
                        text, re.I
                    )
                    if meta:
                        result['description'] = meta.group(1).strip()

                # Address (heuristic)
                if not result.get('address'):
                    addr_patterns = [
                        r'(?:address|dirección|endereço)[:\s]*([^<]{10,200})',
                        r'itemprop=["\']address["\'][^>]*>([^<]+)',
                        r'class=["\'][^"\']*address[^"\']*["\'][^>]*>([^<]+)',
                        r'<p[^>]*>([^<]{20,200}(?:street|avenue|road|drive|suite|calle|carrera|av|blvd)[^<]{10,200})</p>',
                    ]
                    for pat in addr_patterns:
                        addr = re.search(pat, text, re.I)
                        if addr:
                            result['address'] = addr.group(1).strip()
                            break

                # Business type from copyright/title
                if not result.get('business_type'):
                    bt = re.search(r'(?:All Rights Reserved|Inc\.|LLC|Ltd\.|LTD|GmbH|SAS|SpA|B\.V\.|S\.L\.|S\.A\.|Pty\s+Ltd|Corporation|Corp\.)', text, re.I)
                    if bt:
                        result['business_type'] = bt.group(0)

                # Employee count
                if not result.get('employees'):
                    emp = re.search(r'(\d[,\d]*)\+?\s*(?:employees?|team members?|staff)', text, re.I)
                    if emp:
                        result['employees'] = emp.group(1).replace(',', '')

        except:
            continue

    # Dedup
    seen = set()
    unique_emails = [e for e in all_emails if e and not (e in seen or seen.add(e))]
    seen_phones = set()
    unique_phones = [p for p in all_phones if p and not (p in seen_phones or seen_phones.add(p))]

    if unique_emails:
        result['email'] = unique_emails[0]
        result['emails_all'] = ','.join(unique_emails[:5])
    if unique_phones:
        result['phone'] = unique_phones[0]
    if all_vat:
        result['vat'] = all_vat[0]
    if all_cnpj:
        # Limpiar CNPJ
        cnpj_clean = re.sub(r'\D', '', all_cnpj[0]) if all_cnpj else ''
        if len(cnpj_clean) == 14:
            result['cnpj'] = f"{cnpj_clean[:2]}.{cnpj_clean[2:5]}.{cnpj_clean[5:8]}/{cnpj_clean[8:12]}-{cnpj_clean[12:]}"
    if all_rfc:
        result['rfc'] = all_rfc[0]
    if all_rut:
        result['rut'] = all_rut[0].replace('.', '').upper() if all_rut else ''

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# FUENTE 6: SAM.gov (US Contractors — DUNS/EIN)
# ═══════════════════════════════════════════════════════════════════════════════

async def source_samgov(session: aiohttp.ClientSession, company: str) -> dict:
    try:
        if not check_rate_limit("api.sam.gov"):
            return {}
        url = f"https://api.sam.gov/entity-information/v3/entities?api_key=DEMO_KEY&legalBusinessName={quote_plus(company)}&samRegistered=Yes&includeSections=entityRegistration,coreData&pageSize=3"
        async with session.get(url, headers=random_headers(), timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status != 200:
                return {}
            data = await r.json()
            entities = data.get('entityData', [])
            if not entities:
                return {}
            e = entities[0]
            reg = e.get('entityRegistration', {})
            core = e.get('coreData', {})
            addr = core.get('physicalAddress', {})
            result = {'source': 'samgov'}
            if reg.get('ueiDUNS'):
                result['duns'] = reg['ueiDUNS']
            if reg.get('cageCode'):
                result['ein'] = reg['cageCode']
            if addr:
                parts = [addr.get('addressLine1',''), addr.get('city',''), addr.get('stateOrProvinceCode',''), addr.get('zipCode','')]
                result['address'] = ', '.join(p for p in parts if p)
            naics = core.get('generalInformation', {}).get('primaryNaics', '')
            if naics:
                result['sic_code'] = naics
            bus_types = core.get('businessTypes', [])
            if bus_types:
                result['business_type'] = ', '.join(bus_types)
            if core.get('entityStartDate'):
                result['founded'] = core['entityStartDate'][:4]
            return result
    except:
        pass
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# FUENTE 7: OpenCorporates (Corporate Data Global)
# ═══════════════════════════════════════════════════════════════════════════════

async def source_opencorp(session: aiohttp.ClientSession, company: str, state: str = "", country: str = "") -> dict:
    try:
        if not check_rate_limit("api.opencorporates.com"):
            return {}
        q = quote_plus(company)
        jd = ""
        if country:
            jd = f"&jurisdiction_code={country.lower()}"
            if state:
                jd = f"&jurisdiction_code={country.lower()}_{state.lower()}"
        url = f"https://api.opencorporates.com/v0.4/companies/search?q={q}{jd}&current_status=Active&per_page=3"
        async with session.get(url, headers=random_headers(), timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status != 200:
                return {}
            data = await r.json()
            companies = data.get('results', {}).get('companies', [])
            if not companies:
                return {}
            c = companies[0].get('company', {})
            result = {'source': 'opencorp'}
            if c.get('registered_address'):
                addr = c['registered_address']
                parts = [addr.get('street_address',''), addr.get('locality',''), addr.get('region',''), addr.get('postal_code',''), addr.get('country','')]
                result['address'] = ', '.join(p for p in parts if p)
            if c.get('incorporation_date'):
                result['founded'] = c['incorporation_date'][:4]
            if c.get('company_number'):
                result['company_number'] = c['company_number']
            if c.get('company_type'):
                result['business_type'] = c['company_type']
            if c.get('name'):
                result['company_name'] = c['name']
            if c.get('jurisdiction_code'):
                result['region'] = c['jurisdiction_code']
            return result
    except:
        pass
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# FUENTE 8: UK Companies House (búsqueda por nombre)
# ═══════════════════════════════════════════════════════════════════════════════

async def source_uk_companies(session: aiohttp.ClientSession, company: str) -> dict:
    try:
        if not check_rate_limit("find-and-update.company-information.service.gov.uk"):
            return {}
        q = quote_plus(company)
        url = f"https://find-and-update.company-information.service.gov.uk/search?q={q}"
        async with session.get(url, headers={
            "User-Agent": random.choice(UA_POOL),
            "Accept": "text/html",
        }, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status != 200:
                return {}
            text = await r.text(errors='ignore')
            result = {'source': 'uk_companies'}
            # Extraer company number
            cn = re.search(r'class="heading-xlarge"[^>]*>([^<]+)', text)
            if cn:
                result['company_number'] = cn.group(1).strip()
            # Extraer status
            status = re.search(r'class="status-tag"[^>]*>\s*([^<]+)', text, re.I)
            if status:
                result['business_type'] = status.group(1).strip()
            # Extraer registration address
            addr = re.search(r'Registered office address[^<]*<[^>]*>([^<]+)', text, re.I)
            if addr:
                result['address'] = addr.group(1).strip()
            return result
    except:
        pass
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# FUENTE 9: Brazil CNPJ (ReceitaWS API pública)
# ═══════════════════════════════════════════════════════════════════════════════

async def source_brazil_cnpj(session: aiohttp.ClientSession, cnpj: str) -> dict:
    if not cnpj:
        return {}
    try:
        if not check_rate_limit("www.receitaws.com.br"):
            return {}
        cnpj_clean = re.sub(r'\D', '', cnpj)
        if len(cnpj_clean) != 14:
            return {}
        url = f"https://www.receitaws.com.br/v1/cnpj/{cnpj_clean}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status != 200:
                return {}
            data = await r.json()
            if data.get('status') == 'ERROR':
                return {}
            result = {'source': 'brazil_cnpj'}
            result['cnpj'] = cnpj
            if data.get('nome'):
                result['company_name'] = data['nome']
            if data.get('fantasia'):
                if not result.get('company_name'):
                    result['company_name'] = data['fantasia']
            if data.get('logradouro'):
                parts = [data.get('logradouro',''), data.get('numero',''), data.get('complemento',''), data.get('bairro',''), data.get('municipio',''), data.get('uf',''), data.get('cep','')]
                result['address'] = ', '.join(p for p in parts if p)
            if data.get('telefone'):
                result['phone'] = data['telefone']
            if data.get('email'):
                result['email'] = data['email']
            if data.get('atividade_principal'):
                act = data['atividade_principal']
                if act:
                    result['sic_code'] = act[0].get('text', '')
                    result['description'] = act[0].get('text', 'Analyzing...')
            if data.get('data_situacao'):
                result['founded'] = data['data_situacao'][:4]
            if data.get('porte'):
                result['business_type'] = data['porte']
            if data.get('natureza_juridica'):
                if not result.get('business_type'):
                    result['business_type'] = data['natureza_juridica']
            return result
    except:
        pass
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# FUENTE 10: EU VAT (VATSense API gratuita)
# ═══════════════════════════════════════════════════════════════════════════════

async def source_eu_vat(session: aiohttp.ClientSession, vat: str) -> dict:
    if not vat:
        return {}
    try:
        vat_clean = vat.replace(' ', '').upper()
        url = f"https://api.vatsense.com/1/validate/{vat_clean}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status != 200:
                return {}
            data = await r.json()
            result = {'source': 'eu_vat'}
            if data.get('valid'):
                result['vat'] = vat_clean
                if data.get('name'):
                    result['company_name'] = data['name']
                if data.get('address'):
                    result['address'] = data['address']
                if data.get('country'):
                    result['country'] = data['country']
                return result
    except:
        pass
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# FUENTE 11: AI Agent Heuristic (Industry Profiling)
# ═══════════════════════════════════════════════════════════════════════════════

AI_KEYWORDS = {
    # Transportation
    'taxi': ('Transportation', 'Private transport and taxi services provider.'),
    'cab': ('Transportation', 'On-demand vehicle transportation and cab services.'),
    'logistics': ('Logistics & Supply Chain', 'Freight, shipping, and logistics coordination services.'),
    'freight': ('Logistics & Supply Chain', 'Freight forwarding and cargo transportation solutions.'),
    'shipping': ('Logistics & Supply Chain', 'Maritime or ground shipping and parcel delivery.'),
    'delivery': ('Logistics & Supply Chain', 'Package and goods delivery services.'),
    'transport': ('Transportation', 'Transportation and fleet management services.'),
    'airline': ('Transportation', 'Commercial airline and air travel services.'),
    'trucking': ('Transportation', 'Trucking and heavy cargo transportation.'),
    'moving': ('Transportation', 'Residential and commercial moving services.'),
    # Healthcare
    'hospital': ('Healthcare', 'Healthcare and medical center providing patient care.'),
    'healthcare': ('Healthcare', 'Comprehensive healthcare and medical services provider.'),
    'clinic': ('Healthcare', 'Medical clinic providing outpatient healthcare services.'),
    'pharma': ('Healthcare', 'Pharmaceutical research and drug development.'),
    'medic': ('Healthcare', 'Medical services, supplies, and healthcare solutions.'),
    'dental': ('Healthcare', 'Dental care and oral health services.'),
    'wellness': ('Healthcare', 'Preventive care, wellness programs, and health optimization.'),
    # Legal
    'law': ('Legal', 'Legal representation and professional law services.'),
    'attorney': ('Legal', 'Legal counsel and attorney services.'),
    'legal': ('Legal', 'Comprehensive legal advisory and litigation services.'),
    'abogados': ('Legal', 'Servicios legales profesionales y asesoría jurídica.'),
    # Technology
    'tech': ('Technology', 'Technology solutions, software, and digital innovation.'),
    'software': ('Technology', 'Software development and technology solutions provider.'),
    'digital': ('Technology', 'Digital transformation and technology consulting.'),
    'cyber': ('Technology', 'Cybersecurity solutions and threat protection.'),
    'cloud': ('Technology', 'Cloud computing infrastructure and services.'),
    'ai ': ('Technology', 'Artificial intelligence and machine learning solutions.'),
    'data': ('Technology', 'Data analytics, big data, and business intelligence.'),
    'dev': ('Technology', 'Software development and engineering services.'),
    'solutions': ('Technology', 'Technology solutions and business process optimization.'),
    'app': ('Technology', 'Mobile and web application development.'),
    # Real Estate
    'real estate': ('Real Estate', 'Real estate investment, brokerage, and property management.'),
    'property': ('Real Estate', 'Property management, sales, and real estate services.'),
    'housing': ('Real Estate', 'Housing development and residential property solutions.'),
    'construction': ('Construction', 'General construction, contracting, and building services.'),
    'builder': ('Construction', 'Residential and commercial building construction.'),
    'contractor': ('Construction', 'Construction contracting and project management.'),
    # Education
    'school': ('Education', 'Educational institution and academic training services.'),
    'education': ('Education', 'Educational programs, training, and academic services.'),
    'academy': ('Education', 'Professional training and skills development academy.'),
    'university': ('Education', 'Higher education and university-level academic programs.'),
    'learning': ('Education', 'Online and in-person learning and training solutions.'),
    # Finance
    'financial': ('Financial Services', 'Financial planning, investment, and advisory services.'),
    'bank': ('Financial Services', 'Banking, credit, and financial services.'),
    'insurance': ('Insurance', 'Insurance brokerage, risk management, and coverage solutions.'),
    'invest': ('Financial Services', 'Investment management and portfolio advisory.'),
    'capital': ('Financial Services', 'Capital management, private equity, and venture funding.'),
    'accounting': ('Financial Services', 'Accounting, bookkeeping, and tax preparation services.'),
    'accountant': ('Financial Services', 'Professional accounting and financial reporting.'),
    'tax': ('Financial Services', 'Tax preparation, planning, and compliance services.'),
    'audit': ('Financial Services', 'Auditing, assurance, and financial compliance.'),
    # Hospitality
    'hotel': ('Hospitality', 'Hotel and accommodation services.'),
    'restaurant': ('Food & Beverage', 'Restaurant and food service operations.'),
    'food': ('Food & Beverage', 'Food production, distribution, or service.'),
    'cafe': ('Food & Beverage', 'Coffee shop and casual dining.'),
    'bar': ('Food & Beverage', 'Bar, pub, or nightlife establishment.'),
    'travel': ('Hospitality & Travel', 'Travel agency and tourism services.'),
    'tourism': ('Hospitality & Travel', 'Tourism services and travel experiences.'),
    # Retail
    'retail': ('Retail', 'Retail sales, merchandising, and consumer goods.'),
    'shop': ('Retail', 'Retail store and consumer goods sales.'),
    'store': ('Retail', 'Physical or online retail store operations.'),
    'ecommerce': ('Retail', 'E-commerce and online retail operations.'),
    'wholesale': ('Wholesale & Distribution', 'Wholesale distribution and bulk supply.'),
    'distributor': ('Wholesale & Distribution', 'Product distribution and supply chain management.'),
    # Manufacturing
    'manufacturing': ('Manufacturing', 'Industrial manufacturing and production.'),
    'factory': ('Manufacturing', 'Manufacturing facility and industrial production.'),
    'industrial': ('Manufacturing', 'Industrial equipment and manufacturing solutions.'),
    'producer': ('Manufacturing', 'Product manufacturing and goods production.'),
    # Energy
    'energy': ('Energy & Utilities', 'Energy production, distribution, and utilities.'),
    'solar': ('Energy & Utilities', 'Solar energy installation and renewable power.'),
    'renewable': ('Energy & Utilities', 'Renewable energy and sustainable power solutions.'),
    'oil': ('Energy & Utilities', 'Oil and gas exploration and production.'),
    'gas': ('Energy & Utilities', 'Natural gas distribution and energy services.'),
    'electric': ('Energy & Utilities', 'Electrical services, power distribution, and utilities.'),
    # Media
    'media': ('Media & Entertainment', 'Media production, publishing, and content creation.'),
    'film': ('Media & Entertainment', 'Film production, video, and cinematography.'),
    'studio': ('Media & Entertainment', 'Creative studio for design, media, or production.'),
    'agency': ('Marketing & Advertising', 'Marketing, advertising, and creative agency.'),
    'marketing': ('Marketing & Advertising', 'Marketing strategy, campaigns, and brand management.'),
    'advertising': ('Marketing & Advertising', 'Advertising and promotional services.'),
    'production': ('Media & Entertainment', 'Content and media production services.'),
    # Nonprofit
    'foundation': ('Nonprofit', 'Charitable foundation and philanthropic organization.'),
    'nonprofit': ('Nonprofit', 'Non-profit organization serving community needs.'),
    'charity': ('Nonprofit', 'Charitable organization and humanitarian services.'),
    'association': ('Nonprofit', 'Professional or trade association.'),
    # Government
    'government': ('Government', 'Government agency and public sector services.'),
    'municipal': ('Government', 'Municipal government and public administration.'),
    'public': ('Government', 'Public sector organization and government services.'),
    # General Business
    'llc': ('General Business', 'Privately held business entity (LLC).'),
    'corp': ('General Business', 'Corporate entity providing multi-sector services.'),
    'inc ': ('General Business', 'Incorporated business entity.'),
    'enterprise': ('General Business', 'Enterprise-level business operations.'),
    'group': ('General Business', 'Business group with diversified operations.'),
    'company': ('General Business', 'Business entity providing professional services.'),
    'consulting': ('Professional Services', 'Expert business advisory and consulting services.'),
    'services': ('Professional Services', 'Professional services and business support.'),
    'global': ('Professional Services', 'Global business services and international operations.'),
    'international': ('Professional Services', 'International trade and cross-border business services.'),
    'partner': ('Professional Services', 'Strategic partnership and channel services.'),
}

# Default pairs in Spanish for LATAM detection
AI_KEYWORDS_ES = {
    'transporte': ('Transportation', 'Servicios de transporte y logística.'),
    'envios': ('Logistics & Supply Chain', 'Servicios de envío y mensajería.'),
    'salud': ('Healthcare', 'Servicios de salud y bienestar médico.'),
    'clinica': ('Healthcare', 'Centro médico y servicios clínicos.'),
    'dental': ('Healthcare', 'Servicios de odontología y cuidado dental.'),
    'medico': ('Healthcare', 'Servicios médicos profesionales.'),
    'abogado': ('Legal', 'Bufete de abogados y servicios legales.'),
    'consultora': ('Professional Services', 'Consultoría empresarial y servicios profesionales.'),
    'tecnologia': ('Technology', 'Soluciones tecnológicas e innovación digital.'),
    'software': ('Technology', 'Desarrollo de software y soluciones digitales.'),
    'construccion': ('Construction', 'Construcción, obras y servicios de edificación.'),
    'inmobiliaria': ('Real Estate', 'Servicios inmobiliarios y gestión de propiedades.'),
    'educacion': ('Education', 'Servicios educativos y formación académica.'),
    'escuela': ('Education', 'Institución educativa y formación.'),
    'capacitacion': ('Education', 'Capacitación profesional y desarrollo de habilidades.'),
    'financiero': ('Financial Services', 'Servicios financieros y asesoría de inversiones.'),
    'seguros': ('Insurance', 'Corretaje de seguros y gestión de riesgos.'),
    'contable': ('Financial Services', 'Servicios contables y preparación de impuestos.'),
    'hotel': ('Hospitality', 'Servicios hoteleros y alojamiento.'),
    'restaurante': ('Food & Beverage', 'Restaurante y servicios de alimentación.'),
    'comida': ('Food & Beverage', 'Servicios de comida y procesamiento de alimentos.'),
    'tienda': ('Retail', 'Tienda comercial y venta al por menor.'),
    'comercio': ('Retail', 'Comercio y venta de productos.'),
    'fabrica': ('Manufacturing', 'Fábrica y producción industrial.'),
    'industria': ('Manufacturing', 'Industria manufacturera y producción.'),
    'energia': ('Energy & Utilities', 'Energía y servicios públicos.'),
    'mineria': ('Energy & Utilities', 'Minería y extracción de recursos.'),
    'agencia': ('Marketing & Advertising', 'Agencia de publicidad y marketing.'),
    'publicidad': ('Marketing & Advertising', 'Servicios de publicidad y promoción.'),
    'medios': ('Media & Entertainment', 'Medios de comunicación y contenido.'),
    'comunicacion': ('Media & Entertainment', 'Servicios de comunicación y relaciones públicas.'),
}

def ai_agent_heuristic(company: EnrichedCompany):
    """Deduce industria y descripción por palabras clave (50+ keywords EN/ES)"""
    name = company.company_name.lower()
    desc = company.description.lower() if company.description else ""

    # Check English keywords
    for kw, (ind, dsc) in AI_KEYWORDS.items():
        if kw in name:
            if company.industry == "B2B / Professional Services":
                company.industry = ind
            if company.description == "Analyzing...":
                company.description = dsc
            company.confidence = max(company.confidence, 20)
            break

    # Check Spanish keywords if still default
    if company.industry == "B2B / Professional Services":
        for kw, (ind, dsc) in AI_KEYWORDS_ES.items():
            if kw in name:
                company.industry = ind
                if company.description == "Analyzing...":
                    company.description = dsc
                company.confidence = max(company.confidence, 20)
                break

    # Check description for keywords (secondary)
    if company.industry == "B2B / Professional Services":
        for kw, (ind, dsc) in {**AI_KEYWORDS, **AI_KEYWORDS_ES}.items():
            if kw in desc:
                company.industry = ind
                break

    # Detect business_type from company name suffixes
    name_upper = company.company_name.upper()
    if any(s in name_upper for s in [' LLC', 'L.L.C.', 'LIMITED LIABILITY']):
        company.business_type = 'LLC'
    elif any(s in name_upper for s in [' INC.', ' INCORPORATED', 'CORP.', ' CORPORATION']):
        company.business_type = 'Corporation'
    elif any(s in name_upper for s in [' LTD', 'LIMITED']):
        company.business_type = 'Ltd'
    elif ' GMBH' in name_upper:
        company.business_type = 'GmbH'
    elif ' SAS' in name_upper:
        company.business_type = 'SAS'
    elif ' SPA' in name_upper:
        company.business_type = 'SpA'
    elif ' PTY' in name_upper:
        company.business_type = 'Pty Ltd'
    elif ' LLC' in name_upper:
        company.business_type = 'LLC'
    elif ' BV' in name_upper:
        company.business_type = 'B.V.'
    elif ' SL' in name_upper:
        company.business_type = 'S.L.'
    elif ' SA' in name_upper:
        company.business_type = 'S.A.'

    # Detect region from country/name
    if not company.region:
        name_lower = company.company_name.lower()
        if company.country:
            eu_countries = {'GB', 'DE', 'FR', 'IT', 'ES', 'PT', 'NL', 'BE', 'AT', 'CH', 'SE', 'NO', 'DK', 'FI', 'IE', 'PL', 'CZ', 'SK', 'HU', 'RO', 'BG', 'GR', 'HR', 'SI', 'LT', 'LV', 'EE', 'LU', 'MT', 'CY'}
            latam_countries = {'MX', 'BR', 'AR', 'CO', 'CL', 'PE', 'EC', 'VE', 'UY', 'PY', 'BO', 'CR', 'PA', 'GT', 'SV', 'HN', 'NI', 'DO', 'CU'}
            apac_countries = {'AU', 'NZ', 'SG', 'HK', 'JP', 'KR', 'CN', 'IN', 'MY', 'TH', 'VN', 'ID', 'PH', 'TW'}
            if company.country.upper() in eu_countries:
                company.region = 'EU'
            elif company.country.upper() in latam_countries:
                company.region = 'LATAM'
            elif company.country.upper() in apac_countries:
                company.region = 'APAC'
            elif company.country.upper() == 'US':
                company.region = 'NORTH AMERICA'
            elif company.country.upper() == 'CA':
                company.region = 'NORTH AMERICA'
        elif any(kw in name_lower for kw in ['gmbh', 'g.m.b.h', 'gesellschaft']):
            company.region = 'EU'
        elif any(kw in name_lower for kw in ['pty', 'australia']):
            company.region = 'APAC'
        elif any(kw in name_lower for kw in ['s.a.s', 'sas', 'sarl']):
            company.region = 'LATAM' if any(c in name_lower for c in ['colombia', 'mexico', 'brasil', 'chile', 'peru', 'argentina']) else 'EU'
        elif any(kw in name_lower for kw in ['ltda', 'limitada']):
            company.region = 'LATAM'

    # Final defaults
    if company.description == '' or company.description == 'Analyzing...':
        company.description = f"Professional {company.industry.lower()} entity providing B2B services and solutions."

    if company.confidence < 20:
        company.confidence = 20
        if company.status == "pending":
            company.status = "enriched (AI Agent)"


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENRICHMENT ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

async def enrich_company(
    session: aiohttp.ClientSession,
    company: EnrichedCompany
) -> EnrichedCompany:
    name = company.company_name
    city = company.city
    state = company.state
    country = company.country
    sources_used = []

    # ── Check cache ──
    cache_key = get_cache_key(company)
    cache = load_cache()
    if cache_key in cache:
        cached = cache[cache_key]
        if time.time() - cached.get("ts", 0) < CACHE_TTL and cached.get("confidence", 0) >= 30:
            for k, v in cached.items():
                if k != "ts" and hasattr(company, k) and v and not getattr(company, k, ''):
                    setattr(company, k, v)
            if cached.get("confidence", 0) > company.confidence:
                company.confidence = cached["confidence"]
                company.status = cached.get("status", company.status)
                company.sources_used = cached.get("sources_used", "")
    else:
        # ── Step 1: Find domain/website (parallel: DDG, Bing, Google, Clearbit) ──
        if not company.website:
            await asyncio.sleep(random.uniform(0.1, 1.5))  # jitter
            tasks = [
                source_clearbit(session, name),
                source_ddg(session, name, city, state),
                source_bing(session, name, city, state),
                source_google(session, name, city, state),
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, dict) and r.get('website') and is_valid_website(r['website']):
                    company.website = r['website']
                    company.domain = r.get('domain', extract_domain(r['website'])) or company.domain
                    sources_used.append(r.get('source', '?'))
                    break

        # ── Step 2: Apply AI Heuristic ──
        ai_agent_heuristic(company)

        # ── Step 3: Website scraping + corporate data (parallel) ──
        tasks2 = [source_website(session, company.website)]

        if not company.duns and not company.ein:
            tasks2.append(source_samgov(session, name))

        if not company.address and not company.company_number:
            tasks2.append(source_opencorp(session, name, state, country))

        if not company.company_number and not company.address:
            tasks2.append(source_uk_companies(session, name))

        if not company.cnpj:
            # Try to find CNPJ from name in Brazil
            if country.upper() == 'BR' or 'brasil' in name.lower() or 'brazil' in name.lower() or 'ltda' in name.lower():
                tasks2.append(source_brazil_cnpj(session, ''))

        if not company.vat:
            tasks2.append(source_eu_vat(session, company.vat))

        results2 = await asyncio.gather(*tasks2, return_exceptions=True)

        for r in results2:
            if not isinstance(r, dict):
                continue
            src = r.get('source', '?')
            if src not in ['website']:
                sources_used.append(src)
            elif company.website:
                sources_used.append(src)

            for field_name in [
                'email', 'emails_all', 'phone', 'address', 'linkedin',
                'facebook', 'twitter', 'instagram', 'youtube',
                'duns', 'ein', 'ruc', 'vat', 'cnpj', 'rfc', 'rut', 'nif',
                'abn', 'cin', 'company_number', 'sic_code',
                'description', 'industry', 'founded',
                'website', 'domain', 'country', 'region',
                'employees', 'revenue', 'business_type', 'company_name'
            ]:
                val = r.get(field_name, '')
                if val and not getattr(company, field_name, ''):
                    try:
                        setattr(company, field_name, val)
                    except:
                        pass

        # ── Step 4: Calculate confidence ──
        score = 0
        if company.website: score += 30
        if company.email: score += 25
        if company.phone: score += 15
        if company.address: score += 10
        if company.linkedin: score += 10
        if company.duns or company.ein or company.ruc or company.vat or company.cnpj:
            score += min(15, 5 * sum(1 for x in [company.duns, company.ein, company.ruc, company.vat, company.cnpj] if x))
        if company.industry and company.industry != "B2B / Professional Services": score += 5
        if company.description and company.description not in ("Analyzing...", ""): score += 5
        social_count = sum(1 for x in [company.facebook, company.twitter, company.instagram, company.youtube] if x)
        score += min(9, social_count * 3)
        if company.founded: score += 3
        if company.employees: score += 3
        if company.revenue: score += 3
        if company.business_type: score += 2

        company.confidence = score
        company.sources_used = ','.join(set(s for s in sources_used if s and s != '?'))

        # Status
        if score >= 70:
            company.status = "enriched (Complete)"
        elif score >= 50:
            company.status = "enriched (Full Data)"
        elif score >= 30:
            company.status = "enriched (Domain Found)"
        elif score >= 10:
            company.status = "partial"
        else:
            company.status = "failed"

        # ── Save to cache ──
        if company.confidence >= 10:
            cache[cache_key] = {**asdict(company), "ts": time.time()}
            save_cache(cache)

    return company


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH PROCESSOR — N workers paralelos
# ═══════════════════════════════════════════════════════════════════════════════

async def enrich_batch(
    companies: List[EnrichedCompany],
    workers: int = 20,
    progress_callback: Optional[Callable] = None,
    stop_flag: Optional[Callable] = None
) -> List[EnrichedCompany]:
    """
    Procesa la lista de empresas con `workers` conexiones simultáneas.
    progress_callback(i, total, company) se llama tras cada empresa.
    stop_flag: función que devuelve True para detener.
    """
    connector = aiohttp.TCPConnector(
        limit=workers,
        limit_per_host=3,
        ssl=False,
        keepalive_timeout=30
    )
    timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=10)

    semaphore = asyncio.Semaphore(workers)

    async def process_one(i: int, company: EnrichedCompany) -> EnrichedCompany:
        if stop_flag and stop_flag():
            return company
        async with semaphore:
            try:
                enriched = await enrich_company(session, company)
            except Exception as e:
                company.status = 'failed'
                enriched = company
            if progress_callback:
                progress_callback(i + 1, len(companies), enriched)
            return enriched

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [process_one(i, c) for i, c in enumerate(companies)]
        results = await asyncio.gather(*tasks, return_exceptions=False)

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# SYNC ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def run_enrichment(
    companies: List[EnrichedCompany],
    workers: int = 20,
    progress_callback: Optional[Callable] = None,
    stop_flag: Optional[Callable] = None
) -> List[EnrichedCompany]:
    """Entry point síncrono para GUI y scripts. Llama al motor asíncrono."""
    return asyncio.run(enrich_batch(companies, workers, progress_callback, stop_flag))
