"""App-branded support and feedback dialogs using the existing native Qt theme."""
import threading
import webbrowser

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (QDialog, QWidget, QLabel, QPushButton, QVBoxLayout,
                               QHBoxLayout, QLineEdit, QTextEdit, QScrollArea)
import support_feedback as feedback
import updater


class FeedbackDialog(QDialog):
    finished_send = Signal(str)

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.setWindowTitle('Feedback / feature request')
        self.resize(560, 520)
        self.busy = False
        col = QVBoxLayout(self)
        intro = QLabel('Have an idea or found a problem? Send it to the FrodoTappins team.')
        intro.setWordWrap(True); col.addWidget(intro)
        contact = app.cfg.data.get('feedback_contact', {})
        self.name = QLineEdit(str(contact.get('name', ''))); self.name.setMaxLength(100)
        self.email = QLineEdit(str(contact.get('email', ''))); self.email.setMaxLength(254)
        self.message = QTextEdit(); self.message.setAcceptRichText(False)
        self.message.setPlaceholderText('What would you like to improve?')
        for title, widget in [('Name', self.name), ('Email', self.email), ('Message', self.message)]:
            label = QLabel(title); label.setBuddy(widget); col.addWidget(label); col.addWidget(widget)
        for text in ['Your name and email are remembered in this portable copy.',
                     'Only these fields, the app name and version are sent. No counts or logs are attached.']:
            label = QLabel(text); label.setWordWrap(True); col.addWidget(label)
        self.status = QLabel(''); self.status.setWordWrap(True); col.addWidget(self.status)
        row = QHBoxLayout(); col.addLayout(row)
        close = QPushButton('Close'); close.setMinimumHeight(44); close.clicked.connect(self.close)
        self.submit = QPushButton('Send feedback'); self.submit.setMinimumHeight(44)
        self.submit.clicked.connect(self.send)
        row.addWidget(close); row.addWidget(self.submit)
        self.finished_send.connect(self.complete)
        self.name.setFocus()

    def send(self):
        if self.busy:
            return
        try:
            data = feedback.payload(self.name.text(), self.email.text(), self.message.toPlainText())
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
                result = 'Could not send feedback. Check your connection and try again. Your message is still here.'
            self.finished_send.emit(result)
        threading.Thread(target=work, daemon=True).start()

    def complete(self, error):
        self.busy = False
        for widget in [self.name, self.email, self.message, self.submit]:
            widget.setEnabled(True)
        if not error:
            self.message.clear()
        self.status.setText(error or 'Feedback sent. Thank you!')


class SupportDialog(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.feedback_dialog = None
        self.setWindowTitle('Feedback / Donate')
        self.resize(620, 660)
        outer = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); outer.addWidget(scroll)
        page = QWidget(); scroll.setWidget(page)
        col = QVBoxLayout(page); col.setSpacing(16)
        logo = QLabel(); logo.setPixmap(app.windowIcon().pixmap(72, 72)); logo.setAlignment(Qt.AlignCenter)
        col.addWidget(logo)
        title = QLabel('FrodoTappins\nThere and Backspace Again'); title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet('font-size: 22px; font-weight: bold;'); col.addWidget(title)
        version = QLabel('Version ' + updater.VERSION); version.setAlignment(Qt.AlignCenter); col.addWidget(version)
        self.update_status = QLabel(''); self.update_status.setWordWrap(True)
        self.update_status.setAlignment(Qt.AlignCenter); col.addWidget(self.update_status)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.refresh_update_status)
        self.update_timer.start(250)
        actions = QHBoxLayout(); col.addLayout(actions)
        for text, action in [('Join the Discord', lambda: webbrowser.open('https://discord.gg/fs4WyaQPA')),
                             ('Check for updates', app.check_updates), ('Feedback', self.open_feedback)]:
            button = QPushButton(text); button.setMinimumHeight(44); button.clicked.connect(action); actions.addWidget(button)
        def paragraph(text):
            label = QLabel(text); label.setWordWrap(True); col.addWidget(label); return label
        paragraph('Thanks for using FrodoTappins. Feedback is always welcome. The quickest way to get my attention is the Feedback button above. You can also open an issue on GitHub or join the Discord.')
        paragraph('In the meantime, I have a variety of other fun software projects. Check out:')
        projects = QHBoxLayout(); col.addLayout(projects)
        for label, url in [('GitHub', 'https://github.com/AdamChesters'), ('AdamCh.com', 'https://adamch.com')]:
            button = QPushButton(label); button.setMinimumHeight(44)
            button.clicked.connect(lambda checked=False, url=url: webbrowser.open(url)); projects.addWidget(button)
        heading = paragraph('Donate'); heading.setAlignment(Qt.AlignCenter)
        heading.setStyleSheet('font-size: 22px; font-weight: bold;')
        paragraph("I love making things. Anything I've ever built has been to have fun, share fun, and make life a bit easier. If you got value from one of these things, and you'd like to chuck us a coffee, a bottle, or a god damned Ferrari, go your hardest. Then hustle over to discord to claim your supporter role!")
        donations = QHBoxLayout(); col.addLayout(donations)
        for label, url, note, style in [
            ('GitHub Sponsors', 'https://github.com/sponsors/AdamChesters', 'Account required\n0% fees to creator', 'background: #24292f; color: white;'),
            ('Buy Me a Coffee', 'https://buymeacoffee.com/adamch', 'Guest checkout available', 'background: #ffdd00; color: #111;'),
            ('Donate with PayPal', feedback.PAYPAL_URL, 'Guest checkout available\nLeast preferred option', 'background: #ffc439; color: #003087;')]:
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
            self.feedback_dialog = FeedbackDialog(self.app)
        self.feedback_dialog.show(); self.feedback_dialog.raise_(); self.feedback_dialog.activateWindow()
