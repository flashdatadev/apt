import hashlib
import io
import json
import pathlib
import re
import sys
import subprocess
import tarfile
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_packages import manifest, sha
from build_repository import read_ar


class PackageTests(unittest.TestCase):
    def test_payload_and_control(self):
        for release in manifest()['releases']:
            for arch in ('amd64', 'arm64'):
                data = (ROOT / 'packages' / f"flashdata_{release['debian_version']}_{arch}.deb").read_bytes()
                self.assertEqual(sha(data), release['packages'][arch])
                members = read_ar(data)
                self.assertEqual(set(members), {'debian-binary', 'control.tar.xz', 'data.tar.xz'})
                self.assertEqual(members['debian-binary'], b'2.0\n')
                with tarfile.open(fileobj=io.BytesIO(members['control.tar.xz']), mode='r:xz') as controls:
                    self.assertEqual(set(controls.getnames()), {'control', 'md5sums'})
                    control = controls.extractfile('control').read().decode()
                    self.assertIn(f"Version: {release['debian_version']}\n", control)
                    self.assertIn(f'Architecture: {arch}\n', control)
                    self.assertIn('Maintainer: FlashData <support@flashdata.dev>\n', control)
                with tarfile.open(fileobj=io.BytesIO(members['data.tar.xz']), mode='r:xz') as payload:
                    for member in payload.getmembers():
                        self.assertEqual((member.uid, member.gid), (0, 0))
                        self.assertFalse(member.mode & 0o7022)
                        self.assertFalse(pathlib.PurePosixPath(member.name).is_absolute())
                        self.assertNotIn('..', pathlib.PurePosixPath(member.name).parts)
                    executable = payload.extractfile('usr/bin/flashdata').read()
                    self.assertEqual(hashlib.sha256(executable).hexdigest(), release['executables'][arch])
                    provenance = json.load(payload.extractfile('usr/share/doc/flashdata/build-info.json'))
                    self.assertEqual(provenance['source_commit'], release['source_commit'])

    def test_translated_install_commands(self):
        blocks = lambda name: re.findall(r'(?s)```[^\n]*\n.*?```', (ROOT / name).read_text(encoding='utf-8'))
        self.assertEqual(blocks('README.md'), blocks('README.zh-CN.md'))
        fingerprint = (ROOT / 'keys/fingerprint.txt').read_text().strip()
        self.assertRegex(fingerprint, r'^[0-9A-F]{40}$')
        for name in ('README.md', 'README.zh-CN.md', 'tests/install_repo.sh', 'web/index.html'):
            self.assertIn(fingerprint, (ROOT / name).read_text(encoding='utf-8'))

    def test_every_advertised_hash_has_an_immutable_index(self):
        with tempfile.TemporaryDirectory(prefix='fd-apt-check-') as folder:
            subprocess.run([sys.executable, str(ROOT / 'scripts/build_repository.py'), '--output', folder], check=True, capture_output=True)
            suite = pathlib.Path(folder) / 'dists/stable'
            for path in suite.glob('main/binary-*/Packages*'):
                payload = path.read_bytes()
                for algorithm in ('sha256', 'sha512'):
                    digest = hashlib.new(algorithm, payload).hexdigest()
                    immutable = path.parent / 'by-hash' / algorithm.upper() / digest
                    self.assertEqual(immutable.read_bytes(), payload)


if __name__ == '__main__':
    unittest.main()
