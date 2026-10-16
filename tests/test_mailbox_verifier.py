import asyncio
import socket
import smtplib
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import dns.resolver
import dns.rrset


class FakeSMTP:
    def __init__(self, responses, mail_code=250, tls=True):
        self.responses = iter(responses)
        self.mail_code = mail_code
        self.tls = tls
        self.sock = SimpleNamespace(settimeout=lambda _: None)
        self.recipients = []
        self.closed = False

    def ehlo(self): return 250, b'ok'
    def has_extn(self, name): return self.tls
    def starttls(self, context): return 220, b'ok'
    def mail(self, sender): return self.mail_code, b'ok'
    def rset(self): return 250, b'ok'
    def rcpt(self, email):
        self.recipients.append(email)
        return next(self.responses)
    def close(self): self.closed = True
    def data(self, *_): raise AssertionError('Verifier must never send DATA')


class SMTPTests(unittest.TestCase):
    def test_unbounded_multiline_reply_is_rejected(self):
        from mailbox_verifier import PinnedSMTP
        smtp = PinnedSMTP.__new__(PinnedSMTP)
        smtp._deadline = time.monotonic() + 10
        smtp._timer = None
        smtp.sock = SimpleNamespace(settimeout=lambda _: None, close=lambda: None)
        lines = iter([b'250-still going\r\n'] * 65 + [b'250 done\r\n'])
        smtp.file = SimpleNamespace(readline=lambda _: next(lines), close=lambda: None)
        with self.assertRaises((smtplib.SMTPException, OSError)):
            smtp.getreply()

    def probe(self, responses, **kwargs):
        from mailbox_verifier import probe_smtp
        server = FakeSMTP(responses, **kwargs)
        with patch('mailbox_verifier.PinnedSMTP', return_value=server):
            result = probe_smtp('jane@acme.com', 'mx.acme.com', '1.1.1.1')
        self.assertTrue(server.closed)
        return result, server

    def test_accepted_only_after_control_recipient_rejected(self):
        result, server = self.probe([(250, b'ok'), (550, b'5.1.1 No such user')])
        self.assertEqual(result.status, 'smtp_accepted')
        self.assertFalse(result.catch_all)
        self.assertEqual(len(server.recipients), 2)
        self.assertNotEqual(server.recipients[1], 'jane@acme.com')

    def test_catch_all_is_not_valid_mailbox(self):
        result, _ = self.probe([(250, b'ok'), (250, b'ok')])
        self.assertEqual(result.status, 'catch_all')
        self.assertTrue(result.catch_all)

    def test_mailbox_rejected_requires_explicit_user_code(self):
        result, server = self.probe([(550, b'5.1.1 No such user')])
        self.assertEqual(result.status, 'mailbox_rejected')
        self.assertEqual(len(server.recipients), 1)

    def test_policy_rejection_is_unknown(self):
        result, _ = self.probe([(550, b'5.7.1 Access denied')])
        self.assertEqual(result.status, 'unknown')

    def test_ambiguous_rejection_is_unknown(self):
        result, _ = self.probe([(550, b'Rejected')])
        self.assertEqual(result.status, 'unknown')

    def test_temporary_rejection_is_unknown(self):
        result, _ = self.probe([(451, b'4.7.1 Greylisted')])
        self.assertEqual(result.status, 'unknown')

    def test_252_is_not_verified(self):
        result, _ = self.probe([(252, b'Cannot verify')])
        self.assertEqual(result.status, 'unknown')

    def test_ambiguous_control_is_unknown(self):
        result, _ = self.probe([(250, b'ok'), (550, b'5.7.1 Blocked')])
        self.assertEqual(result.status, 'unknown')

    def test_rejected_sender_does_not_check_recipient(self):
        result, server = self.probe([], mail_code=550)
        self.assertEqual(result.status, 'unknown')
        self.assertEqual(server.recipients, [])

    def test_connection_timeout_is_unknown(self):
        from mailbox_verifier import probe_smtp
        with patch('mailbox_verifier.PinnedSMTP', side_effect=socket.timeout):
            result = probe_smtp('jane@acme.com', 'mx.acme.com', '1.1.1.1')
        self.assertEqual(result.status, 'unknown')

    def test_private_ip_never_connected(self):
        from mailbox_verifier import probe_smtp
        with patch('mailbox_verifier.PinnedSMTP') as smtp:
            result = probe_smtp('jane@acme.com', 'mx.acme.com', '127.0.0.1')
        self.assertEqual(result.status, 'unknown')
        smtp.assert_not_called()


class DNSTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_is_rechecked_after_domain_lock(self):
        from mailbox_verifier import verify_mailboxes, Verification
        stopped = False
        def probe(*args):
            nonlocal stopped
            time.sleep(.02)  # Let other tasks queue behind the domain lock.
            stopped = True
            return Verification(args[0], 'unknown', 'test')
        with patch('mailbox_verifier.MailboxVerifier._destinations', AsyncMock(
                return_value=('mx_found', 'public_mail_route', [('mx.acme.com', '1.1.1.1')]))), \
             patch('mailbox_verifier.probe_smtp', side_effect=probe) as smtp:
            results = await verify_mailboxes(['one@acme.com', 'two@acme.com', 'three@acme.com'],
                                             stop_flag=lambda: stopped)
        self.assertEqual(smtp.call_count, 1)
        self.assertEqual([row.reason for row in results[1:]], ['cancelled', 'cancelled'])

    async def test_dns_mx_pointing_to_private_network_is_blocked(self):
        from mailbox_verifier import MailboxVerifier
        mapping = {('acme.com', 'MX'): ['10 mx.acme.com.'],
                   ('mx.acme.com', 'A'): ['10.0.0.1'],
                   ('mx.acme.com', 'AAAA'): dns.resolver.NoAnswer()}
        with patch('mailbox_verifier.probe_smtp') as probe:
            result = await MailboxVerifier(resolver=self.resolver(mapping)).verify('jane@acme.com')
        self.assertEqual(result.reason, 'non_public_mx')
        probe.assert_not_called()

    async def test_dns_and_smtp_pipeline(self):
        from mailbox_verifier import MailboxVerifier
        mapping = {('acme.com', 'MX'): ['10 mx.acme.com.'],
                   ('mx.acme.com', 'A'): ['1.1.1.1'],
                   ('mx.acme.com', 'AAAA'): dns.resolver.NoAnswer()}
        server = FakeSMTP([(250, b'ok'), (550, b'5.1.1 No such user')])
        with patch('mailbox_verifier.PinnedSMTP', return_value=server):
            result = await MailboxVerifier(resolver=self.resolver(mapping)).verify('jane@acme.com')
        self.assertEqual(result.status, 'smtp_accepted')
        self.assertTrue(server.closed)

    async def test_cancelled_batch_has_no_network_queries(self):
        from mailbox_verifier import verify_mailboxes
        with patch('mailbox_verifier.MailboxVerifier.verify', AsyncMock()) as verify:
            result = await verify_mailboxes(['jane@acme.com'], stop_flag=lambda: True)
        self.assertEqual(result[0].status, 'not_checked')
        verify.assert_not_awaited()

    async def test_mx_results_are_cached_only_for_current_run(self):
        from mailbox_verifier import MailboxVerifier
        resolver = self.resolver({('acme.com', 'MX'): ['0 .']})
        verifier = MailboxVerifier(resolver=resolver)
        await verifier.verify('jane@acme.com')
        await verifier.verify('john@acme.com')
        self.assertEqual(resolver.resolve.await_count, 1)

    def resolver(self, mapping):
        async def resolve(host, rdtype, **kwargs):
            answer = mapping[(host, rdtype)]
            if isinstance(answer, Exception): raise answer
            return dns.rrset.from_text(host + '.', 60, 'IN', rdtype, *answer)
        return SimpleNamespace(resolve=AsyncMock(side_effect=resolve))

    async def test_null_mx_means_domain_does_not_accept_mail(self):
        from mailbox_verifier import MailboxVerifier
        verifier = MailboxVerifier(resolver=self.resolver({('acme.com', 'MX'): ['0 .']}))
        result = await verifier.verify('jane@acme.com')
        self.assertEqual(result.status, 'domain_no_mail')

    async def test_nxdomain(self):
        from mailbox_verifier import MailboxVerifier
        verifier = MailboxVerifier(resolver=self.resolver({('acme.com', 'MX'): dns.resolver.NXDOMAIN()}))
        self.assertEqual((await verifier.verify('jane@acme.com')).status, 'domain_not_found')

    async def test_dns_timeout_is_unknown(self):
        from mailbox_verifier import MailboxVerifier
        verifier = MailboxVerifier(resolver=self.resolver({('acme.com', 'MX'): dns.resolver.LifetimeTimeout()}))
        self.assertEqual((await verifier.verify('jane@acme.com')).status, 'unknown')

    async def test_mx_only_does_not_verify_mailbox(self):
        from mailbox_verifier import MailboxVerifier
        mapping = {('acme.com', 'MX'): ['10 mx.acme.com.'],
                   ('mx.acme.com', 'A'): ['1.1.1.1'],
                   ('mx.acme.com', 'AAAA'): dns.resolver.NoAnswer()}
        result = await MailboxVerifier(resolver=self.resolver(mapping), smtp=False).verify('jane@acme.com')
        self.assertEqual(result.status, 'mx_found')

    async def test_implicit_mx_fallback(self):
        from mailbox_verifier import MailboxVerifier
        mapping = {('acme.com', 'MX'): dns.resolver.NoAnswer(),
                   ('acme.com', 'A'): ['1.1.1.1'], ('acme.com', 'AAAA'): dns.resolver.NoAnswer()}
        result = await MailboxVerifier(resolver=self.resolver(mapping), smtp=False).verify('jane@acme.com')
        self.assertEqual(result.status, 'mx_found')
        self.assertEqual(result.mx_host, 'acme.com')

    async def test_invalid_syntax_never_queries_dns(self):
        from mailbox_verifier import MailboxVerifier
        resolver = SimpleNamespace(resolve=AsyncMock())
        result = await MailboxVerifier(resolver=resolver).verify('bad\r\nRCPT TO:<a@b.com>')
        self.assertEqual(result.status, 'invalid_syntax')
        resolver.resolve.assert_not_called()

    async def test_batch_reuses_exact_duplicate_results(self):
        from mailbox_verifier import verify_mailboxes
        with patch('mailbox_verifier.MailboxVerifier.verify', AsyncMock(return_value=SimpleNamespace(status='unknown'))) as verify:
            results = await verify_mailboxes(['jane@acme.com', 'jane@acme.com'])
        self.assertEqual(len(results), 2)
        self.assertEqual(verify.await_count, 1)
