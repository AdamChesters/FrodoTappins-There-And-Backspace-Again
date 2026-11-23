import os
import unittest
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout
    from donate import support_ui
    from donate.content import CONTENT, SupportIdentity
except ImportError:
    QApplication = None


@unittest.skipUnless(QApplication, 'PySide6 is not available')
class SupportDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QApplication.instance() or QApplication([])

    def setUp(self):
        self.host = QMainWindow()
        self.host.cfg = SimpleNamespace(data={}, save=lambda: None)
        self.calls = []

    def identity(self, **extra):
        return SupportIdentity('Example App', QIcon(), '1.2.3', 'example-app',
                               lambda: self.calls.append('update'), **extra)

    def test_update_button_follows_host_state(self):
        dialog = support_ui.SupportDialog(self.host, self.identity(
            cancelUpdate=lambda: self.calls.append('cancel')))
        button = dialog.update_button
        self.assertEqual(dialog.windowTitle(), 'About Example App / Support')
        self.assertEqual((button.text(), button.isEnabled()), (CONTENT['actions']['update'], True))
        self.assertEqual(dialog.version.text(), '<b>Version 1.2.3</b>')
        dialog.set_update('Checking <GitHub>...', busy=True)
        self.assertFalse(button.isEnabled())
        self.assertIn('Checking &lt;GitHub&gt;...', dialog.version.text())
        dialog.set_update('v1.3.0 is ready to download.', available='v1.3.0')
        self.assertEqual((button.text(), button.isEnabled()), ('Download v1.3.0', True))
        button.click()
        dialog.set_update('Downloading update: 40%', busy=True, cancellable=True)
        self.assertEqual((button.text(), button.isEnabled()), ('Cancel', True))
        button.click()
        self.assertEqual(self.calls, ['update', 'cancel'])

    def test_host_frame_takes_both_dialogs(self):
        framed = []

        def frame(dialog, title):
            framed.append(title)
            return QVBoxLayout(dialog)

        dialog = support_ui.SupportDialog(self.host, self.identity(frame=frame))
        dialog.open_feedback()
        self.assertEqual(framed, ['About Example App / Support', CONTENT['feedback']['title']])
        self.assertEqual(dialog.styleSheet(), '')
        self.assertIs(dialog.update_button.window(), dialog)
