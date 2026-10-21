"""Public metadata must follow the actual static hosting URL."""
import importlib.util
from pathlib import Path
import sys
import unittest

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE))
spec = importlib.util.spec_from_file_location('prospect_website_build', SITE / 'build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class HostingOriginTests(unittest.TestCase):
    def test_supports_custom_domain_and_github_project_path(self):
        for value in ('https://prospect.techdigital.site',
                      'https://alicelabs-llc.github.io/NexusCold',
                      'https://techdigital.site/prospect/'):
            self.assertEqual(build.normalize_origin(value), value.rstrip('/') + '/')

    def test_rejects_non_public_or_ambiguous_origins(self):
        for value in ('http://example.com', 'https://', 'https://user:secret@example.com',
                      'https://example.com/?token=value', 'https://example.com/#section',
                      'https://example.com/../other', 'https://example.com/\nHeader'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build.normalize_origin(value)


if __name__ == '__main__':
    unittest.main()
