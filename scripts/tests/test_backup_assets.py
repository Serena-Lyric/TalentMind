import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / 'backup_assets.py'


class BackupAssetsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.backup = self.base / 'backup'
        self.backup.mkdir()
        self.payload = '历史交接内容\n'.encode()
        self.digest = hashlib.sha256(self.payload).hexdigest()
        with zipfile.ZipFile(self.backup / 'private-assets.zip', 'w') as z:
            z.writestr('objects/' + self.digest, self.payload)
        self.entries = [
            {'path': 'input/handover.txt', 'sha256': self.digest, 'bytes': len(self.payload)},
            {'path': 'output/handover-copy.txt', 'sha256': self.digest, 'bytes': len(self.payload)},
        ]
        self.write_manifest()

    def write_manifest(self):
        (self.backup / 'private-files.json').write_text(json.dumps(self.entries), encoding='utf-8')
        artifacts = []
        for name in ['private-assets.zip', 'private-files.json']:
            p = self.backup / name
            artifacts.append({'path': name, 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
        (self.backup / 'backup-manifest.json').write_text(json.dumps({'schema_version': 1, 'artifacts': artifacts}), encoding='utf-8')

    def run_tool(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), '--backup', str(self.backup), *args], capture_output=True, text=True)

    def test_verifies_one_object_shared_by_two_original_paths(self):
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['private_files'], 2)

    def test_restores_original_paths_and_contents(self):
        target = self.base / 'restored'
        result = self.run_tool('--restore-to', str(target))
        self.assertEqual(result.returncode, 0, result.stderr)
        for entry in self.entries:
            self.assertEqual((target / entry['path']).read_bytes(), self.payload)

    def test_corrupted_archive_is_rejected_before_creating_target(self):
        with (self.backup / 'private-assets.zip').open('ab') as f:
            f.write(b'corruption')
        target = self.base / 'restored'
        self.assertNotEqual(self.run_tool('--restore-to', str(target)).returncode, 0)
        self.assertFalse(target.exists())

    def test_parent_escape_is_rejected_before_creating_target(self):
        self.entries[0]['path'] = '../outside.txt'
        self.write_manifest()
        target = self.base / 'restored'
        self.assertNotEqual(self.run_tool('--restore-to', str(target)).returncode, 0)
        self.assertFalse(target.exists())
        self.assertFalse((self.base / 'outside.txt').exists())

    def test_existing_target_remains_untouched(self):
        target = self.base / 'restored'
        target.mkdir()
        (target / 'sentinel.txt').write_text('keep', encoding='utf-8')
        self.assertNotEqual(self.run_tool('--restore-to', str(target)).returncode, 0)
        self.assertEqual((target / 'sentinel.txt').read_text(), 'keep')
        self.assertEqual(len(list(target.iterdir())), 1)

    def test_case_colliding_paths_are_rejected(self):
        self.entries[1]['path'] = 'INPUT/HANDOVER.TXT'
        self.write_manifest()
        target = self.base / 'restored'
        self.assertNotEqual(self.run_tool('--restore-to', str(target)).returncode, 0)
        self.assertFalse(target.exists())

    def test_artifact_path_cannot_escape_backup(self):
        p = self.backup / 'backup-manifest.json'
        manifest = json.loads(p.read_text())
        manifest['artifacts'][0]['path'] = '../outside.zip'
        p.write_text(json.dumps(manifest), encoding='utf-8')
        self.assertNotEqual(self.run_tool().returncode, 0)


if __name__ == '__main__':
    unittest.main()
