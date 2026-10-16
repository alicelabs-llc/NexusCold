import csv
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


class QualityTests(unittest.TestCase):
    def test_mailbox_verification_is_exported_separately_from_quality(self):
        from mailbox_verifier import Verification
        from nexus_cli import main
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / 'in.csv', Path(tmp) / 'out.csv'
            source.write_text('company_name,email\nAcme,jane@acme.com\n')
            with patch('mailbox_verifier.run_verification', return_value=[
                    Verification('jane@acme.com', 'catch_all', 'random_recipient_accepted', catch_all=True)]):
                main([str(source), '--output', str(target), '--verify-mailboxes'])
            with target.open(encoding='utf-8-sig') as output:
                row = next(csv.DictReader(output))
            self.assertEqual(row['MAILBOX_STATUS'], 'catch_all')
            self.assertEqual(row['EMAIL_STATUS'], 'syntax_only')
            self.assertEqual(row['MAILBOX_CATCH_ALL'], 'true')

    def test_cli_exposes_verification_and_mx_only_modes(self):
        result = subprocess.run([sys.executable, 'nexus_cli.py', '--help'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--verify-mailboxes', result.stdout)
        self.assertIn('--mx-only', result.stdout)

    def test_headers_are_safe_and_do_not_collide(self):
        from data_quality import spreadsheet_headers
        headers = spreadsheet_headers(['company_name', '=1+1', "'=1+1", '=1+1_2'])
        self.assertEqual(len(set(headers)), 4)
        self.assertTrue(all(not text.startswith(('=', '+', '-', '@')) for text in headers))

    def test_spreadsheet_formulas_are_escaped(self):
        from data_quality import spreadsheet_safe
        for text in ('=1+1', '+cmd', '-cmd', '@SUM(A1)', ' \t=1+1', '\r=1'):
            self.assertTrue(spreadsheet_safe(text).startswith("'"))
        self.assertEqual(spreadsheet_safe('Acme LLC'), 'Acme LLC')
        self.assertEqual(spreadsheet_safe(42), 42)

    def test_email_is_not_claimed_as_verified(self):
        from data_quality import email_quality
        self.assertEqual(email_quality('jane@acme.com', 'acme.com'), 'syntax_only')
        self.assertEqual(email_quality('jane@other.com', 'acme.com'), 'domain_mismatch')
        self.assertEqual(email_quality('not an email', 'acme.com'), 'invalid_syntax')
        self.assertEqual(email_quality('', 'acme.com'), 'not_found')

    def test_offline_csv_preserves_rows_and_flags_quality(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'input.csv'
            target = Path(tmp) / 'output.csv'
            source.write_text('company_name,website,email,customer_id\nAcme,https://acme.com,jane@other.com,001\nAcme,https://acme.com,,002\n,,bad,003\n=1+1,,,004\n', encoding='utf-8')
            result = subprocess.run([sys.executable, 'nexus_cli.py', str(source), '--output', str(target)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            with target.open(encoding='utf-8-sig') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 4)
            self.assertEqual(rows[0]['EMAIL_STATUS'], 'domain_mismatch')
            self.assertEqual(rows[0]['customer_id'], '001')
            self.assertEqual(rows[1]['DUPLICATE_OF'], '2')
            self.assertEqual(rows[2]['STATUS'], 'invalid_input')
            self.assertEqual(rows[3]['company_name'], "'=1+1")
            summary = json.loads(result.stdout)
            self.assertEqual(summary['network_enabled'], False)
            self.assertEqual(summary['duplicates'], 1)

    def test_cli_refuses_to_overwrite_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'input.csv'
            source.write_text('company_name\nAcme\n')
            original = source.read_text()
            result = subprocess.run([sys.executable, 'nexus_cli.py', str(source), '--output', str(source)],
                                    capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(source.read_text(), original)
