import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch

import updater


def executable():
    body = bytearray(256)
    body[:2] = b'MZ'
    struct.pack_into('<I', body, 60, 128)
    body[128:134] = b'PE\0\0\x64\x86'
    return bytes(body)


def release(tag='v0.4.0', body=None):
    body = body or executable()
    return {'tag_name': tag, 'draft': False, 'prerelease': False, 'assets': [{
        'name': 'FrodoTappins.exe', 'state': 'uploaded', 'size': len(body),
        'digest': 'sha256:' + hashlib.sha256(body).hexdigest(),
        'browser_download_url': f'{updater.RELEASES_URL}/download/{tag}/FrodoTappins.exe'}]}


class UpdateTests(unittest.TestCase):
    def test_selects_newest_and_handles_historic_tags(self):
        self.assertEqual(updater.version_key('v0.2'), (0, 2, 0))
        self.assertIsNone(updater.select_release([release('v0.2'), release('v0.3.0')]))
        self.assertEqual(updater.select_release([release('v0.9.0'), release('v0.10.0')])['tag'], 'v0.10.0')

    def test_drafts_prereleases_and_invalid_versions_are_not_installed(self):
        items = [dict(release(), draft=True), dict(release(), prerelease=True),
                 release('v0.4.0-alpha.1'), release('v01.2.3')]
        self.assertIsNone(updater.select_release(items))

    def test_missing_or_untrusted_asset_is_manual_only(self):
        for field, value in [('digest', None), ('size', -1), ('size', True),
                             ('size', updater.MAX_EXE_BYTES + 1),
                             ('browser_download_url', 'https://example.org/FrodoTappins.exe')]:
            item = release()
            item['assets'][0][field] = value
            self.assertIsNone(updater.select_release([item])['asset'])
        self.assertIsNone(updater.select_release([dict(release(), assets=[])])['asset'])

    def test_redirects_cannot_leave_github_https(self):
        for url in ['http://github.com/file', 'https://github.com.evil.test/file',
                    'https://user:password@github.com/file', 'file:///tmp/file',
                    'https://github.com:444/file']:
            with self.assertRaises(ValueError): updater.validate_url(url)
        updater.validate_url('https://release-assets.githubusercontent.com/file?signature=x')

    def test_download_verifies_and_never_changes_tallies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('FrodoTappins.exe', 'data.json', 'config.json'):
                (root / name).write_bytes(b'keep unchanged')
            progress = []
            with patch('updater.open_url', return_value=io.BytesIO(executable())):
                stage = updater.download_release(updater.select_release([release()]),
                    root / 'FrodoTappins.exe', threading.Event(), progress.append)
            self.assertEqual((stage / 'new.exe').read_bytes(), executable())
            self.assertEqual(progress[-1], 100)
            for name in ('FrodoTappins.exe', 'data.json', 'config.json'):
                self.assertEqual((root / name).read_bytes(), b'keep unchanged')

    def test_corrupt_truncated_oversized_and_non_pe_downloads_are_removed(self):
        for body in [b'wrong', executable()[:-1], executable() + b'x', b'x' * 256]:
            with tempfile.TemporaryDirectory() as directory:
                with patch('updater.open_url', return_value=io.BytesIO(body)):
                    with self.assertRaises(ValueError):
                        updater.download_release(updater.select_release([release()]),
                            Path(directory) / 'FrodoTappins.exe', threading.Event(), lambda _: None)
                self.assertEqual(list(Path(directory).iterdir()), [])
        # A matching checksum still cannot authorize a non-PE payload.
        with tempfile.TemporaryDirectory() as directory:
            with patch('updater.open_url', return_value=io.BytesIO(b'x' * 256)):
                with self.assertRaises(ValueError):
                    updater.download_release(updater.select_release([release(body=b'x' * 256)]),
                        Path(directory) / 'FrodoTappins.exe', threading.Event(), lambda _: None)

    def test_cancel_cleans_up(self):
        cancelled = threading.Event()
        cancelled.set()
        with tempfile.TemporaryDirectory() as directory:
            with patch('updater.open_url', return_value=io.BytesIO(executable())):
                with self.assertRaisesRegex(RuntimeError, 'cancelled'):
                    updater.download_release(updater.select_release([release()]),
                        Path(directory) / 'FrodoTappins.exe', cancelled, lambda _: None)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_release_response_is_bounded(self):
        with patch('updater.open_url', return_value=io.BytesIO(b' ' * (4 * 1024 * 1024 + 1))):
            with self.assertRaisesRegex(ValueError, 'too large'): updater.check_release()
        with patch('updater.open_url', return_value=io.BytesIO(json.dumps([release()]).encode())):
            self.assertEqual(updater.check_release()['tag'], 'v0.4.0')


@unittest.skipUnless(__import__('os').name == 'nt', 'Native Windows replacement test')
class WindowsReplacementTests(unittest.TestCase):
    def test_wait_backup_replace_and_preserve_data(self):
        self._exercise('success')

    def test_cancel_before_install_preserves_original(self):
        self._exercise('cancel')

    def test_launch_failure_restores_backup(self):
        self._exercise('launch-failure')

    def _exercise(self, mode):
        import os
        import shutil
        import subprocess
        import time
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'FrodoTappins.exe'
            shutil.copy2(Path(os.environ['SystemRoot']) / 'System32' / 'cmd.exe', target)
            original = target.read_bytes()
            stage = root / '.FrodoTappins-update-test'
            stage.mkdir()
            updated = original + b'update-test'
            (stage / 'new.exe').write_bytes(updated)
            (stage / 'helper.exe').write_bytes(original)
            (root / 'data.json').write_text('{"words":12345}')
            (root / 'config.json').write_text('{"device":"same"}')
            parent = subprocess.Popen([str(target), '/d', '/c', 'set /p wait='],
                                      stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
            asset = {'size': len(updated), 'sha256': hashlib.sha256(updated).hexdigest()}
            (stage / 'manifest.json').write_text(json.dumps({
                'pid': parent.pid, 'target': str(target), 'asset': asset, 'minimized': True}))
            if mode != 'cancel':
                (stage / 'install').touch()
            result = []
            try:
                with patch('updater.sys.executable', str(stage / 'helper.exe')), \
                     patch('updater.subprocess.Popen') as launch, \
                     patch('ctypes.windll.user32.MessageBoxW'):
                    if mode == 'launch-failure':
                        launch.side_effect = [OSError('Fixture launch failure'), None]
                    worker = threading.Thread(target=lambda: result.append(updater.apply_update(stage)))
                    worker.start()
                    deadline = time.monotonic() + 10
                    while not (stage / 'ready').exists() and worker.is_alive() and time.monotonic() < deadline:
                        time.sleep(.05)
                    self.assertTrue((stage / 'ready').exists())
                    self.assertEqual(target.read_bytes(), original)
                    parent.terminate()
                    parent.wait(timeout=5)
                    worker.join(timeout=10)
                    self.assertFalse(worker.is_alive())
                    self.assertEqual(result, [1] if mode == 'launch-failure' else [0])
                    if mode == 'success':
                        self.assertEqual(launch.call_args.args[0], [str(target), '--minimized'])
                    elif mode == 'cancel':
                        launch.assert_not_called()
                    else:
                        self.assertEqual(launch.call_count, 2)
                self.assertEqual(target.read_bytes(), updated if mode == 'success' else original)
                if mode != 'cancel':
                    self.assertEqual((stage / 'previous.exe').read_bytes(), original)
                self.assertEqual((root / 'data.json').read_text(), '{"words":12345}')
                self.assertEqual((root / 'config.json').read_text(), '{"device":"same"}')
            finally:
                if parent.poll() is None:
                    parent.terminate()
                    parent.wait(timeout=5)
                parent.stdin.close()


if __name__ == '__main__':
    unittest.main()
