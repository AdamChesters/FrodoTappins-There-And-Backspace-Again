"""App-branded About / Support and feedback dialogs.

The host app may supply its own window chrome through ``SupportIdentity.frame``
and style the named widgets below from its own stylesheet.
"""
import html
import threading
import webbrowser

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QDialog, QWidget, QLabel, QPushButton, QVBoxLayout,
                               QHBoxLayout, QLineEdit, QTextEdit, QScrollArea)
from . import support_feedback as feedback
from .content import CONTENT

# Used when the host supplies no frame of its own.
_SUPPORT_STYLE = """
QDialog, QScrollArea, QScrollArea QWidget { background-color: #241b16; }
QLabel { color: #f1e5ce; }
QLabel#supportTitle { font-size: 22px; font-weight: bold; }
QLabel#supportHeading { font-size: 20px; font-weight: bold; margin-top: 6px; }
QLineEdit, QTextEdit { background-color: #1a120d; color: #f1e5ce;
    border: 1px solid #806644; padding: 6px; }
"""

# Brand colours for the support platforms: (button style, icon tint).
_PLATFORM_STYLES = {'github': ('background: #24292f; color: white;', None),
                    'buymeacoffee': ('background: #ffdd00; color: #111;', None),
                    'paypal': ('background: #ffc439; color: #003087;', '#003087')}


def _frame(dialog, identity, title):
    """Title the dialog and return the layout its content goes into."""
    dialog.setWindowTitle(title)
    if identity.frame is not None:
        return identity.frame(dialog, title)
    dialog.setStyleSheet(dialog.parent().styleSheet() + _SUPPORT_STYLE)
    return QVBoxLayout(dialog)


def _icon(name, tint=None):
    pixmap = QIcon(str(Path(__file__).parent / name)).pixmap(64, 64)
    if tint:
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(tint))
        painter.end()
    return QIcon(pixmap)


class FeedbackDialog(QDialog):
    finished_send = Signal(str)

    def __init__(self, app, identity):
        super().__init__(app)
        self.app = app
        self.identity = identity
        self.resize(560, 520)
        self.busy = False
        col = _frame(self, identity, CONTENT['feedback']['title'])
        intro = QLabel(CONTENT['feedback']['intro'].replace('{appName}', identity.appName))
        intro.setObjectName('supportText'); intro.setWordWrap(True); col.addWidget(intro)
        contact = app.cfg.data.get('feedback_contact', {})
        self.name = QLineEdit(str(contact.get('name', ''))); self.name.setMaxLength(CONTENT['feedback']['fields'][0]['maxLength'])
        self.email = QLineEdit(str(contact.get('email', ''))); self.email.setMaxLength(CONTENT['feedback']['fields'][1]['maxLength'])
        self.message = QTextEdit(); self.message.setAcceptRichText(False)
        self.message.setPlaceholderText(CONTENT['feedback']['placeholder'])
        for field, widget in zip(CONTENT['feedback']['fields'], [self.name, self.email, self.message]):
            title = field['label']
            label = QLabel(title); label.setBuddy(widget); col.addWidget(label); col.addWidget(widget)
        for text in ['Your name and email are remembered in this portable copy.',
                     CONTENT['feedback']['privacy']]:
            label = QLabel(text); label.setObjectName('supportNote'); label.setWordWrap(True); col.addWidget(label)
        self.status = QLabel(''); self.status.setObjectName('supportText'); self.status.setWordWrap(True); col.addWidget(self.status)
        row = QHBoxLayout(); col.addLayout(row)
        close = QPushButton('Close'); close.setMinimumHeight(44); close.clicked.connect(self.close)
        self.submit = QPushButton(CONTENT['feedback']['submit']); self.submit.setMinimumHeight(44)
        self.submit.clicked.connect(self.send)
        row.addWidget(close); row.addWidget(self.submit)
        self.finished_send.connect(self.complete)
        self.name.setFocus()

    def send(self):
        if self.busy:
            return
        try:
            data = feedback.payload(self.name.text(), self.email.text(), self.message.toPlainText(), self.identity.appId, self.identity.appVersion)
            self.app.cfg.data['feedback_contact'] = dict(name=data['name'], email=data['email'])
            self.app.cfg.save()
        except Exception as error:
            self.status.setText(str(error)); return
        self.busy = True
        for widget in [self.name, self.email, self.message, self.submit]:
            widget.setEnabled(False)
        self.status.setText('Sending...')
        def work():
            try:
                feedback.send(data)
                result = ''
            except Exception:
                result = CONTENT['feedback']['failure']
            self.finished_send.emit(result)
        threading.Thread(target=work, daemon=True).start()

    def complete(self, error):
        self.busy = False
        for widget in [self.name, self.email, self.message, self.submit]:
            widget.setEnabled(True)
        if not error:
            self.message.clear()
        self.status.setText(error or CONTENT['feedback']['success'])


class SupportDialog(QDialog):
    def __init__(self, app, identity):
        super().__init__(app)
        self.app = app
        self.identity = identity
        self.feedback_dialog = None
        self.resize(620, 600)
        outer = _frame(self, identity, f'About {identity.appName} / Support')
        scroll = QScrollArea(); scroll.setWidgetResizable(True); outer.addWidget(scroll)
        page = QWidget(); scroll.setWidget(page)
        col = QVBoxLayout(page); col.setSpacing(8)
        logo = QLabel(); logo.setPixmap(identity.appLogo.pixmap(72, 72)); logo.setAlignment(Qt.AlignCenter)
        col.addWidget(logo)
        title = QLabel(identity.appName); title.setObjectName('supportTitle'); title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True); col.addWidget(title)
        self.version = QLabel(); self.version.setObjectName('supportText'); self.version.setWordWrap(True)
        self.version.setAlignment(Qt.AlignCenter); col.addWidget(self.version)
        actions = QHBoxLayout(); col.addLayout(actions)
        actions.addStretch()
        self.update_button = QPushButton(); self.update_button.setMinimumHeight(44)
        self.update_button.clicked.connect(self.update_clicked); actions.addWidget(self.update_button)
        feedback_button = QPushButton(CONTENT['actions']['feedback']); feedback_button.setMinimumHeight(44)
        feedback_button.clicked.connect(self.open_feedback); actions.addWidget(feedback_button)
        actions.addStretch()
        self.set_update()
        socials = QHBoxLayout(); socials.setSpacing(8); col.addLayout(socials)
        socials.addStretch()
        for social in CONTENT['socials']:
            button = QPushButton(); button.setFixedSize(38, 38)
            button.setIcon(_icon(social['icon'])); button.setIconSize(QSize(19, 19))
            button.setToolTip(social['label']); button.setAccessibleName(social['label'])
            button.setStyleSheet(f"QPushButton {{ background: {social['color']}; border: 1px solid {social['color']}; border-radius: 8px; padding: 0; }}")
            button.clicked.connect(lambda checked=False, url=social['url']: webbrowser.open(url)); socials.addWidget(button)
        socials.addStretch()
        def paragraph(text, name='supportText'):
            label = QLabel(text); label.setObjectName(name); label.setWordWrap(True); col.addWidget(label); return label
        paragraph(CONTENT['intro'].replace('{appName}', identity.appName))
        paragraph(CONTENT['donationTitle'], 'supportHeading').setAlignment(Qt.AlignCenter)
        paragraph(CONTENT['donationText'])
        donations = QHBoxLayout(); col.addLayout(donations)
        for platform in CONTENT['platforms']:
            style, tint = _PLATFORM_STYLES[platform['id']]
            item = QVBoxLayout(); item.setSpacing(4); donations.addLayout(item, 1)
            button = QPushButton(platform['label']); button.setMinimumHeight(44); button.setStyleSheet(style)
            button.setIcon(_icon(platform['icon'], tint)); button.setIconSize(QSize(18, 18))
            button.clicked.connect(lambda checked=False, url=platform['url']: webbrowser.open(url)); item.addWidget(button)
            note_label = QLabel('\n'.join(platform['notes'])); note_label.setObjectName('supportNote')
            note_label.setWordWrap(True); note_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop); item.addWidget(note_label, 1)
        col.addStretch(1)
        close = QPushButton('Close'); close.setMinimumHeight(44); close.clicked.connect(self.close); outer.addWidget(close)

    def set_update(self, status='', busy=False, available='', cancellable=False):
        """Show the host's update state: status text beside the version, and the
        update button as check, download (``available`` names it) or cancel."""
        self.cancellable = cancellable
        text = '<b>Version ' + html.escape(self.identity.appVersion) + '</b>'
        if status:
            text += '&nbsp;&nbsp; ' + html.escape(status)
        self.version.setText(text)
        if cancellable:
            label = 'Cancel'
        else:
            label = f'Download {available}' if available else CONTENT['actions']['update']
        self.update_button.setText(label)
        self.update_button.setEnabled(cancellable or not busy)

    def update_clicked(self):
        if self.cancellable and self.identity.cancelUpdate is not None:
            self.identity.cancelUpdate()
        else:
            self.identity.checkForUpdates()

    def open_feedback(self):
        if self.feedback_dialog is None:
            self.feedback_dialog = FeedbackDialog(self.app, self.identity)
        self.feedback_dialog.show(); self.feedback_dialog.raise_(); self.feedback_dialog.activateWindow()
