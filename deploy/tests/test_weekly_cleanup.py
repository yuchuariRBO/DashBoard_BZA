import importlib.util
import os
from pathlib import Path
import tempfile
import time
import unittest

script = Path(__file__).resolve().parents[1] / 'scripts/weekly_cleanup.py'
spec = importlib.util.spec_from_file_location('weekly_cleanup', script)
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class CacheCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cache = self.root / 'cache'
        self.cache.mkdir()
        self.now = time.time()

    def old_file(self, path):
        path.write_bytes(b'cached bytes')
        age = self.now - 31 * 86400
        os.utime(path, (age, age))
        return path

    def test_only_old_regular_files_are_deleted_and_links_are_not_followed(self):
        old = self.old_file(self.cache / 'old')
        recent = self.cache / 'recent'
        recent.write_text('keep')
        personal = self.root / 'personal'
        personal.mkdir()
        photo = self.old_file(personal / 'photo.png')
        (self.cache / 'file-link').symlink_to(photo)
        (self.cache / 'directory-link').symlink_to(personal, target_is_directory=True)
        count, _ = cleanup.clean_cache(self.cache, now=self.now)
        self.assertEqual(count, 1)
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())
        self.assertTrue(photo.exists())
        self.assertTrue((self.cache / 'file-link').is_symlink())
        self.assertTrue((self.cache / 'directory-link').is_symlink())

    def test_dry_run_never_deletes_files(self):
        old = self.old_file(self.cache / 'old')
        count, _ = cleanup.clean_cache(self.cache, dry_run=True, now=self.now)
        self.assertEqual(count, 1)
        self.assertTrue(old.exists())

    def test_root_symlink_is_not_followed(self):
        old = self.old_file(self.cache / 'old')
        link = self.root / 'linked-cache'
        link.symlink_to(self.cache, target_is_directory=True)
        self.assertEqual(cleanup.clean_cache(link, now=self.now), (0, 0))
        self.assertTrue(old.exists())

    def test_symlink_ancestor_is_rejected(self):
        nested = self.cache / 'nested'
        nested.mkdir()
        old = self.old_file(nested / 'old')
        link = self.root / 'linked-cache'
        link.symlink_to(self.cache, target_is_directory=True)
        with self.assertRaises(ValueError):
            cleanup.clean_cache(link / 'nested', now=self.now)
        self.assertTrue(old.exists())


if __name__ == '__main__':
    unittest.main()
