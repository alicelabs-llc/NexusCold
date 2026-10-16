"""Offline quality checks. A syntax check does not verify mailbox existence."""
import re


def spreadsheet_safe(value):
    """Prevent scraped or imported text from becoming an Excel formula."""
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def spreadsheet_headers(headers):
    """Escape formula headers and preserve each column when escaping collides."""
    used, result = set(), []
    for header in headers:
        base = spreadsheet_safe(str(header))
        candidate, suffix = base, 2
        while candidate in used:
            candidate = f'{base}_{suffix}'
            suffix += 1
        used.add(candidate)
        result.append(candidate)
    return result


def email_quality(email, domain=''):
    email = email.strip().lower()
    if not email:
        return 'not_found'
    if (len(email) > 254 or not re.fullmatch(
            r"[a-z0-9][a-z0-9._%+\-]*@[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?)+", email)
            or '..' in email or email.split('@')[0].endswith('.')):
        return 'invalid_syntax'
    email_domain = email.split('@')[1]
    domain = domain.lower().removeprefix('www.')
    if domain and email_domain != domain and not email_domain.endswith('.' + domain):
        return 'domain_mismatch'
    return 'syntax_only'
