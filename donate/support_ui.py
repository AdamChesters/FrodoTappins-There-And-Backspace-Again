"""App-branded support and feedback dialogs using the existing native Qt theme."""
import threading
import webbrowser

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (QDialog, QWidget, QLabel, QPushButton, QVBoxLayout,
                               QHBoxLayout, QLineEdit, QTextEdit, QScrollArea)
from . import support_feedback as feedback
from .content import CONTENT


class FeedbackDialog(QDialog):
    finished_send = Signal(str)

    def __init__(self, app, identity):
        super().__init__(app)
        self.app = app
        self.identity = identity
        self.setWindowTitle(CONTENT['feedback']['title'])
        self.resize(560, 520)
        self.busy = False
        col = QVBoxLayout(self)
        intro = QLabel(CONTENT['feedback']['intro'].replace('{appName}', identity.appName))
        intro.setWordWrap(True); col.addWidget(intro)
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
            label = QLabel(text); label.setWordWrap(True); col.addWidget(label)
        self.status = QLabel(''); self.status.setWordWrap(True); col.addWidget(self.status)
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
        self.setWindowTitle(CONTENT['title'])
        self.resize(620, 660)
        outer = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); outer.addWidget(scroll)
        page = QWidget(); scroll.setWidget(page)
        col = QVBoxLayout(page); col.setSpacing(16)
        logo = QLabel(); logo.setPixmap(identity.appLogo.pixmap(72, 72)); logo.setAlignment(Qt.AlignCenter)
        col.addWidget(logo)
        title = QLabel(identity.appName); title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet('font-size: 22px; font-weight: bold;'); col.addWidget(title)
        version = QLabel('Version ' + identity.appVersion); version.setAlignment(Qt.AlignCenter); col.addWidget(version)
        self.update_status = QLabel(''); self.update_status.setWordWrap(True)
        self.update_status.setAlignment(Qt.AlignCenter); col.addWidget(self.update_status)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.refresh_update_status)
        self.update_timer.start(250)
        actions = QHBoxLayout(); col.addLayout(actions)
        for text, action in [(CONTENT['actions']['discord'], lambda: webbrowser.open(CONTENT['links']['discord'])),
                             (CONTENT['actions']['update'], identity.checkForUpdates), (CONTENT['actions']['feedback'], self.open_feedback)]:
            button = QPushButton(text); button.setMinimumHeight(44); button.clicked.connect(action); actions.addWidget(button)
        def paragraph(text):
            label = QLabel(text); label.setWordWrap(True); col.addWidget(label); return label
        paragraph(CONTENT['intro'].replace('{appName}', identity.appName))
        paragraph(CONTENT['projectsText'])
        projects = QHBoxLayout(); col.addLayout(projects)
        for label, url in [('GitHub', CONTENT['links']['github']), ('AdamCh.com', CONTENT['links']['website'])]:
            button = QPushButton(label); button.setMinimumHeight(44)
            button.clicked.connect(lambda checked=False, url=url: webbrowser.open(url)); projects.addWidget(button)
        heading = paragraph(CONTENT['donationTitle']); heading.setAlignment(Qt.AlignCenter)
        heading.setStyleSheet('font-size: 22px; font-weight: bold;')
        paragraph(CONTENT['donationText'])
        donations = QHBoxLayout(); col.addLayout(donations)
        styles = {'github': 'background: #24292f; color: white;',
                  'buymeacoffee': 'background: #ffdd00; color: #111;',
                  'paypal': 'background: #ffc439; color: #003087;'}
        for platform in CONTENT['platforms']:
            label, url = platform['label'], platform['url']
            note, style = '\n'.join(platform['notes']), styles[platform['id']]
            item = QVBoxLayout(); donations.addLayout(item)
            button = QPushButton(label); button.setMinimumHeight(64); button.setStyleSheet(style)
            button.clicked.connect(lambda checked=False, url=url: webbrowser.open(url)); item.addWidget(button)
            note_label = QLabel(note); note_label.setWordWrap(True); note_label.setAlignment(Qt.AlignCenter); item.addWidget(note_label)
        close = QPushButton('Close'); close.setMinimumHeight(44); close.clicked.connect(self.close); outer.addWidget(close)

    def refresh_update_status(self):
        label = getattr(self.app, 'update_label', None)
        if label is not None:
            self.update_status.setText(label.text())

    def open_feedback(self):
        if self.feedback_dialog is None:
            self.feedback_dialog = FeedbackDialog(self.app, self.identity)
        self.feedback_dialog.show(); self.feedback_dialog.raise_(); self.feedback_dialog.activateWindow()
