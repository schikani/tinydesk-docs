import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from fetch_release import verify


class ReleaseValidation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'test.bin').write_bytes(b'firmware fixture')
        self.manifest = self.root/'manifest-desktop-esp32c6.json'
        self.manifest.write_text(json.dumps({'version': 'test', 'builds': [
            {'chipFamily': 'ESP32-C6', 'parts': [{'path': 'firmware/test.bin', 'offset': 0}]}]}))
        self.sums()

    def sums(self):
        files = sorted(p for p in self.root.iterdir() if p.name != 'SHA256SUMS.txt')
        (self.root/'SHA256SUMS.txt').write_text(''.join(
            hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files))

    def test_valid(self):
        verify(str(self.root))

    def test_missing(self):
        (self.root/'test.bin').unlink()
        with self.assertRaises(SystemExit): verify(str(self.root))

    def test_corrupt(self):
        (self.root/'test.bin').write_bytes(b'corrupt')
        with self.assertRaises(SystemExit): verify(str(self.root))

    def test_unchecked(self):
        (self.root/'extra.bin').write_bytes(b'unchecked')
        with self.assertRaises(SystemExit): verify(str(self.root))

    def test_unresolved_manifest(self):
        self.manifest.write_text(self.manifest.read_text().replace('test.bin', 'missing.bin'))
        self.sums()
        with self.assertRaises(SystemExit): verify(str(self.root))

    def test_path_escape(self):
        self.manifest.write_text(self.manifest.read_text().replace('firmware/test.bin', '../test.bin'))
        self.sums()
        with self.assertRaises(SystemExit): verify(str(self.root))

    def test_missing_manifests(self):
        self.manifest.unlink()
        self.sums()
        with self.assertRaises(SystemExit): verify(str(self.root))


if __name__ == '__main__': unittest.main()
