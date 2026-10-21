import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import build as site_build

class ReleaseTests(unittest.TestCase):
 def test_untracked_private_files_are_never_published(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);public=root/'output';public.mkdir()
   subprocess.run(['git','init','-q',str(root)],check=True)
   (root/'product_identity.py').write_text('PRODUCT_NAME="Public product"\n')
   subprocess.run(['git','-C',str(root),'add','product_identity.py'],check=True)
   subprocess.run(['git','-C',str(root),'-c','user.name=Release Test','-c','user.email=release@example.invalid','commit','-qm','public file'],check=True)
   for name in ('deploy/.env.production','deploy/server.pem','docs/customer-notes.md'):
    target=root/name;target.parent.mkdir(exist_ok=True);target.write_text('PRIVATE_SENTINEL_NEVER_PUBLISH')
   with patch.object(site_build,'REPO',root),patch.object(site_build,'PUBLIC',public):site_build.source_archive()
   with zipfile.ZipFile(public/'downloads/TechDigital-Prospect-6.4-source.zip') as archive:
    self.assertTrue(any(n.endswith('/product_identity.py') for n in archive.namelist()))
    for name in archive.namelist():self.assertNotIn(b'PRIVATE_SENTINEL_NEVER_PUBLISH',archive.read(name))
 def test_archive_fails_closed_without_git_commit(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'product_identity.py').write_text('public')
   with patch.object(site_build,'REPO',root),patch.object(site_build,'PUBLIC',root/'output'):
    with self.assertRaises(RuntimeError):site_build.source_archive()
