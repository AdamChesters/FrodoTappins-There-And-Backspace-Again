import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    import tracker
except Exception:
    tracker = None


@unittest.skipUnless(tracker, 'the app module needs PySide6 and pynput')
class StartupCheckTests(unittest.TestCase):
    def config(self, data):
        cfg = tracker.Config.__new__(tracker.Config)
        cfg.data = data
        return cfg

    def test_startup_update_check_defaults_on_and_keeps_a_saved_choice(self):
        self.assertTrue(self.config({}).check_updates)
        self.assertFalse(self.config({'check_updates': False}).check_updates)
        self.assertTrue(self.config({'check_updates': True}).check_updates)
