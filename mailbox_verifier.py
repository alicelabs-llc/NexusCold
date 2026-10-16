"""DNS/MX + RCPT checks. Never sends DATA or claims guaranteed deliverability."""
import asyncio
import ipaddress
import re
import secrets
import smtplib
import socket
import ssl
import time
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

import dns.asyncresolver
import dns.exception
import dns.resolver

from data_quality import email_quality


@dataclass(frozen=True)
class Verification:
    email: str
    status: str
    reason: str
    mx_host: str = ''
    smtp_code: int = 0
    catch_all: bool | None = None
    checked_at: str = ''

    def __post_init__(self):
        if not self.checked_at:
            object.__setattr__(self, 'checked_at', datetime.now(timezone.utc).isoformat())


class PinnedSMTP(smtplib.SMTP):
    """Pin the socket to a vetted address while retaining MX hostname for TLS SNI."""
    def __init__(self, hostname, address, timeout):
        self._verified_address = address
        self._deadline = time.monotonic() + timeout
        self._timer = threading.Timer(timeout, self._abort)
        self._timer.daemon = True
        self._timer.start()
        try:
            super().__init__(host=hostname, port=25, local_hostname='nexuscold.local', timeout=timeout)
        except Exception:
            self.close()
            raise

    def _abort(self):
        connection = getattr(self, 'sock', None)
        if connection is not None:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()

    def close(self):
        if getattr(self, '_timer', None) is not None:
            self._timer.cancel()
        super().close()

    def getreply(self):
        """Bound multiline replies as well as slow streams of individual bytes."""
        if self.file is None:
            self.file = self.sock.makefile('rb')
        lines = []
        for _ in range(64):
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('SMTP probe deadline')
            self.sock.settimeout(remaining)
            line = self.file.readline(8193)
            if not line:
                raise smtplib.SMTPServerDisconnected('SMTP connection closed')
            if len(line) > 8192:
                raise smtplib.SMTPResponseException(500, b'SMTP line too long')
            if len(line) < 4 or not line[:3].isdigit():
                raise smtplib.SMTPResponseException(500, b'Malformed SMTP response')
            lines.append(line[4:].strip())
            if line[3:4] != b'-':
                return int(line[:3]), b'\n'.join(lines)
        raise smtplib.SMTPResponseException(500, b'Too many SMTP response lines')

    def _get_socket(self, host, port, timeout):
        if not ipaddress.ip_address(self._verified_address).is_global:
            raise OSError('Non-public SMTP address blocked')
        return socket.create_connection((self._verified_address, 25), timeout, self.source_address)


def _user_missing(code, message):
    # A bare 550 can be a policy block. Require an explicit enhanced user code.
    return code in (550, 553) and bool(re.search(rb'\b5\.1\.1\b', message))


def probe_smtp(email, mx_host, address, timeout=12):
    """At most one target and one random control RCPT; close without DATA."""
    if email_quality(email) != 'syntax_only':
        return Verification(email, 'invalid_syntax', 'invalid_email')
    if not ipaddress.ip_address(address).is_global:
        return Verification(email, 'unknown', 'non_public_mx', mx_host)
    server = None
    deadline = time.monotonic() + timeout

    def command(method, *args, **kwargs):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('SMTP probe deadline')
        server.sock.settimeout(remaining)
        return method(*args, **kwargs)

    try:
        server = PinnedSMTP(mx_host, address, timeout)
        code, _ = command(server.ehlo)
        if code != 250:
            return Verification(email, 'unknown', 'greeting_rejected', mx_host, code)
        if server.has_extn('starttls'):
            command(server.starttls, context=ssl.create_default_context())
            code, _ = command(server.ehlo)
            if code != 250:
                return Verification(email, 'unknown', 'tls_greeting_rejected', mx_host, code)
        code, _ = command(server.mail, '')
        if code != 250:
            return Verification(email, 'unknown', 'sender_rejected', mx_host, code)
        code, message = command(server.rcpt, email)
        if _user_missing(code, message):
            return Verification(email, 'mailbox_rejected', 'explicit_user_unknown', mx_host, code)
        if code != 250:
            return Verification(email, 'unknown', 'recipient_not_confirmed', mx_host, code)
        code, _ = command(server.rset)
        if code != 250:
            return Verification(email, 'unknown', 'control_reset_rejected', mx_host, code)
        code, _ = command(server.mail, '')
        if code != 250:
            return Verification(email, 'unknown', 'control_sender_rejected', mx_host, code)
        control = 'nexus-check-' + secrets.token_hex(16) + '@' + email.rsplit('@', 1)[1]
        code, message = command(server.rcpt, control)
        if code == 250:
            return Verification(email, 'catch_all', 'random_recipient_accepted', mx_host, code, True)
        if _user_missing(code, message):
            return Verification(email, 'smtp_accepted', 'target_accepted_control_rejected', mx_host, 250, False)
        return Verification(email, 'unknown', 'catch_all_not_determined', mx_host, code)
    except (OSError, smtplib.SMTPException) as error:
        return Verification(email, 'unknown', type(error).__name__, mx_host)
    finally:
        if server is not None:
            server.close()


class MailboxVerifier:
    def __init__(self, resolver=None, smtp=True, timeout=12, stop_flag=None):
        self.resolver = resolver or dns.asyncresolver.Resolver()
        self.smtp = smtp
        self.timeout = timeout
        self.stop_flag = stop_flag
        self._domains = {}
        self._locks = {}

    async def _resolve(self, host, kind):
        return await self.resolver.resolve(host, kind, lifetime=4, search=False)

    async def _destinations(self, domain):
        try:
            answers = await self._resolve(domain, 'MX')
            records = sorted((int(record.preference), str(record.exchange).rstrip('.')) for record in answers)
            if any(not host for _, host in records):
                return 'domain_no_mail', 'null_mx', []
        except dns.resolver.NXDOMAIN:
            return 'domain_not_found', 'nxdomain', []
        except dns.resolver.NoAnswer:
            # RFC 5321 implicit MX: use the domain address if MX is absent.
            records = [(0, domain)]
        except dns.exception.DNSException:
            return 'unknown', 'dns_unavailable', []
        destinations = []
        transient = False
        for _, host in records[:2]:
            answers = await asyncio.gather(self._resolve(host, 'A'), self._resolve(host, 'AAAA'),
                                           return_exceptions=True)
            addresses = []
            for answer in answers:
                if isinstance(answer, (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN)):
                    continue
                if isinstance(answer, BaseException):
                    transient = True
                    continue
                addresses.extend(str(record) for record in answer)
            if any(not ipaddress.ip_address(address).is_global for address in addresses):
                return 'unknown', 'non_public_mx', []
            if addresses:
                destinations.append((host, addresses[0]))
        if destinations:
            return 'mx_found', 'public_mail_route', destinations
        return 'unknown', 'dns_unavailable' if transient else 'no_public_mail_route', []

    async def verify(self, email):
        email = email.strip().lower()
        quality = email_quality(email)
        if quality != 'syntax_only':
            return Verification(email, quality, 'invalid_email' if email else 'empty_email')
        domain = email.rsplit('@', 1)[1]
        async with self._locks.setdefault(domain, asyncio.Lock()):
            if self.stop_flag and self.stop_flag():
                return Verification(email, 'not_checked', 'cancelled')
            if domain not in self._domains:
                self._domains[domain] = await self._destinations(domain)
            status, reason, destinations = self._domains[domain]
            if not destinations:
                return Verification(email, status, reason)
            if not self.smtp:
                return Verification(email, 'mx_found', reason, destinations[0][0])
            # No retry on a policy or recipient response; only fail over on transport failure.
            for host, address in destinations:
                if self.stop_flag and self.stop_flag():
                    return Verification(email, 'not_checked', 'cancelled')
                result = await asyncio.to_thread(probe_smtp, email, host, address, self.timeout)
                if result.reason not in ('TimeoutError', 'ConnectionRefusedError', 'SMTPServerDisconnected', 'OSError'):
                    return result
            return result


async def verify_mailboxes(emails, workers=4, smtp=True, stop_flag=None, progress_callback=None):
    if not isinstance(workers, int) or isinstance(workers, bool) or not 1 <= workers <= 20:
        raise ValueError('verification workers must be between 1 and 20')
    verifier = MailboxVerifier(smtp=smtp, stop_flag=stop_flag)
    semaphore = asyncio.Semaphore(workers)
    tasks = {}
    completed = 0

    async def one(email):
        nonlocal completed
        async with semaphore:
            if stop_flag and stop_flag():
                return Verification(email, 'not_checked', 'cancelled')
            result = await verifier.verify(email)
            completed += 1
            if progress_callback:
                progress_callback(completed, len(tasks), result)
            return result

    for email in emails:
        key = email.strip().lower()
        if key not in tasks:
            tasks[key] = asyncio.create_task(one(key))
    await asyncio.gather(*tasks.values())
    return [tasks[email.strip().lower()].result() for email in emails]


def run_verification(emails, **kwargs):
    return asyncio.run(verify_mailboxes(emails, **kwargs))
