import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from german_jobs import run_job, read_csv, load_checkpoint


class JobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.src, self.out = self.root/'in.csv', self.root/'out.csv'
        self.cp = self.root/'work.german'
        self.src.write_text('Empresa,Correo,Ciudad\n=ACME,a@example.com,Quito\nBeta,b@example.com,Quito\n', encoding='utf-8')

    def run_job(self, **kwargs):
        return run_job(self.src, self.out, checkpoint=self.cp, **kwargs)

    def test_offline_job_escapes_formulas_and_preserves_rows(self):
        result = self.run_job()
        self.assertEqual(result['completed'], 2)
        self.assertEqual(read_csv(self.out)[0]['Empresa'], "'=ACME")
        self.assertNotIn(b'a@example.com', self.cp.read_bytes())
        self.assertEqual(load_checkpoint(self.cp)['completed'], 2)
        self.assertEqual(self.cp.stat().st_mode & 0o077, 0)

    def test_network_requires_explicit_opt_in(self):
        with self.assertRaises(ValueError):
            self.run_job(mode='smtp')
        self.assertFalse(self.cp.exists())

    def test_stopped_job_resumes_without_repeating_completed_rows(self):
        stopped = False
        def progress(done, total):
            nonlocal stopped
            stopped = True
        first = self.run_job(stop_flag=lambda: stopped, progress_callback=progress)
        self.assertEqual(first['completed'], 1)
        self.assertFalse(first['finished'])
        second = self.run_job(resume=True)
        self.assertEqual(second['completed'], 2)
        self.assertTrue(second['finished'])
        self.assertEqual(len(read_csv(self.out)), 2)

    def test_changed_file_or_config_rejected_on_resume(self):
        self.run_job()
        with self.assertRaises(ValueError):
            self.run_job(resume=True, mode='mx', allow_network=True)
        self.src.write_text(self.src.read_text() + 'Another,x@example.com,Paris\n')
        with self.assertRaises(ValueError):
            self.run_job(resume=True)

    def test_missing_or_wrong_key_fails_without_overwriting(self):
        self.run_job()
        original = self.cp.read_bytes()
        self.cp.with_suffix('.german.key').unlink()
        with self.assertRaises(ValueError):
            self.run_job(resume=True)
        self.assertEqual(self.cp.read_bytes(), original)

    def test_checkpoint_and_output_cannot_replace_input(self):
        for output, checkpoint in [(self.src, self.cp), (self.out, self.src), (self.out, self.out)]:
            with self.assertRaises(ValueError):
                run_job(self.src, output, checkpoint=checkpoint)

    def test_existing_checkpoint_requires_resume(self):
        self.run_job()
        with self.assertRaises(ValueError):
            self.run_job()

    def test_failure_preserves_completed_rows_and_does_not_fake_success(self):
        from mailbox_verifier import Verification
        with patch('mailbox_verifier.run_verification', side_effect=[
                [Verification('a@example.com', 'unknown', 'blocked')], OSError('offline')]):
            with self.assertRaises(OSError):
                self.run_job(mode='mx', allow_network=True)
        self.assertEqual(load_checkpoint(self.cp)['completed'], 1)
        with patch('mailbox_verifier.run_verification', return_value=[Verification('b@example.com', 'mx_found', 'test')]) as verify:
            result = self.run_job(mode='mx', allow_network=True, resume=True)
        self.assertTrue(result['finished'])
        verify.assert_called_once()

    def test_duplicate_headers_and_no_company_mapping_rejected(self):
        self.src.write_text('name,name\nA,B\n')
        with self.assertRaises(ValueError):
            read_csv(self.src)
        self.src.write_text('misterio,correo\nA,a@example.com\n')
        with self.assertRaises(ValueError):
            self.run_job()

    def test_custom_mapping_is_used_in_summary_and_domain_mismatch(self):
        self.src.write_text('Cliente,Contacto,Sitio\nAlice,other@example.net,https://example.com\n')
        result = self.run_job(mapping={'company_name': 'Cliente', 'email': 'Contacto', 'website': 'Sitio'})
        self.assertEqual(result['summary']['metrics']['missing_company'], 0)
        self.assertEqual(read_csv(self.out)[0]['EMAIL_STATUS'], 'domain_mismatch')
        self.assertEqual(result['summary']['metrics']['email_status'], {'domain_mismatch': 1})

    def test_checkpoint_is_append_only_and_recovers_uncommitted_tail(self):
        stopped = False
        def progress(done, total):
            nonlocal stopped
            stopped = True
        self.run_job(stop_flag=lambda: stopped, progress_callback=progress)
        prefix = self.cp.read_bytes()
        # Simulate a process dying in the middle of its final checkpoint append.
        with self.cp.open('ab') as stream:
            stream.write(b'gAAAA-uncommitted')
        result = self.run_job(resume=True)
        self.assertTrue(result['finished'])
        self.assertTrue(self.cp.read_bytes().startswith(prefix))
        self.assertEqual(load_checkpoint(self.cp)['completed'], 2)

    def test_authenticated_checkpoint_corruption_is_rejected(self):
        self.run_job()
        contents = bytearray(self.cp.read_bytes())
        contents[len(contents)//2] = ord('!')
        self.cp.write_bytes(contents)
        with self.assertRaises(ValueError):
            load_checkpoint(self.cp)

    def test_reimported_enriched_email_and_explicit_selection_are_consistent(self):
        from mailbox_verifier import Verification
        self.src.write_text('Empresa,Correo,ENRICHED_EMAIL\nAcme,,found@example.com\n')
        def verify(emails, **kwargs):
            return [Verification(emails[0], 'mx_found' if emails[0] else 'not_found', 'test')]
        with patch('mailbox_verifier.run_verification', side_effect=verify):
            result = self.run_job(mode='mx', allow_network=True)
        self.assertEqual(read_csv(self.out)[0]['MAILBOX_STATUS'], 'mx_found')
        self.assertEqual(result['summary']['metrics']['email_status'], {'syntax_only': 1})
        self.cp.unlink()
        with patch('mailbox_verifier.run_verification', side_effect=verify):
            result = self.run_job(mode='mx', allow_network=True, mapping={'company_name': 'Empresa', 'email': 'Correo'})
        self.assertEqual(read_csv(self.out)[0]['MAILBOX_STATUS'], 'not_found')
        self.assertEqual(result['summary']['metrics']['email_status'], {'not_found': 1})
