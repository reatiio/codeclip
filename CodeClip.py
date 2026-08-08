import sys
import os
import re
import json
import base64
import time
from email.utils import parsedate_to_datetime

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QSpinBox,
    QCheckBox,
    QTabWidget,
    QFrame,
    QMessageBox,
    QListWidget,
    QListWidgetItem,
    QDialog,
    QFormLayout,
    QDialogButtonBox,
    QScrollArea,
)

import pyperclip

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# ============================================================
# CONFIG
# ============================================================

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]

SETTINGS_FILE = "settings.json"

DEFAULT_MINUTES = 5


# ============================================================
# DEFAULT SERVICES
# ============================================================

DEFAULT_SERVICES = [
    {
        "name": "Microsoft",
        "sender": "account-security-noreply@accountprotection.microsoft.com",
        "subject": "",
        "pattern": r"Your\s+single-use\s+code\s+is:\s*(\d{6})",
        "enabled": True
    },

    {
        "name": "Steam",
        "sender": "noreply@steampowered.com",
        "subject": "",
        "pattern": "",
        "enabled": True
    }
]


# ============================================================
# SETTINGS
# ============================================================

def default_settings():
    return {
        "services": DEFAULT_SERVICES,
        "minutes": DEFAULT_MINUTES,
        "auto_copy": True,
        "quick_mode": False
    }


def load_settings():

    defaults = default_settings()

    if not os.path.exists(SETTINGS_FILE):
        return defaults

    try:

        with open(
            SETTINGS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            saved = json.load(f)

        defaults.update(saved)

        for service in defaults["services"]:

            service.setdefault(
                "subject",
                ""
            )

            service.setdefault(
                "pattern",
                ""
            )

            service.setdefault(
                "enabled",
                True
            )

        return defaults

    except Exception:

        return defaults


def save_settings(settings):

    with open(
        SETTINGS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            settings,
            f,
            indent=4
        )


# ============================================================
# GMAIL AUTHENTICATION
# ============================================================

def authenticate():

    creds = None

    if os.path.exists("token.json"):

        creds = Credentials.from_authorized_user_file(
            "token.json",
            SCOPES
        )

    if creds and creds.expired and creds.refresh_token:

        creds.refresh(
            Request()
        )

    if not creds or not creds.valid:

        if not os.path.exists(
            "credentials.json"
        ):

            raise FileNotFoundError(
                "credentials.json was not found.\n\n"
                "Put credentials.json next to CodeClip."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json",
            SCOPES
        )

        creds = flow.run_local_server(
            port=0
        )

        with open(
            "token.json",
            "w",
            encoding="utf-8"
        ) as token:

            token.write(
                creds.to_json()
            )

    return build(
        "gmail",
        "v1",
        credentials=creds,
        cache_discovery=False
    )


# ============================================================
# EMAIL HELPERS
# ============================================================

def decode_body(data):

    if not data:
        return ""

    try:

        return base64.urlsafe_b64decode(
            data
        ).decode(
            "utf-8",
            errors="ignore"
        )

    except Exception:

        return ""


def extract_text(payload):

    text = ""

    body = payload.get(
        "body",
        {}
    )

    if body:

        data = body.get(
            "data"
        )

        if data:

            text += decode_body(
                data
            )

    for part in payload.get(
        "parts",
        []
    ):

        text += "\n"

        text += extract_text(
            part
        )

    return text


def get_headers(payload):

    headers = {}

    for header in payload.get(
        "headers",
        []
    ):

        name = header.get(
            "name",
            ""
        ).lower()

        value = header.get(
            "value",
            ""
        )

        headers[name] = value

    return headers


def get_timestamp(headers):

    date_string = headers.get(
        "date",
        ""
    )

    if not date_string:
        return 0

    try:

        return parsedate_to_datetime(
            date_string
        ).timestamp()

    except Exception:

        return 0


# ============================================================
# STEAM CODE
# ============================================================

def extract_steam_code(body):

    pattern = (
        r"Steam\s+Guard\s+code"
        r".*?"
        r"access\s+your\s+account\s*:"
        r".*?"
        r"\b([A-Z0-9]{5})\b"
        r"\s*If\s+this\s+wasn't\s+you"
    )

    match = re.search(
        pattern,
        body,
        re.IGNORECASE | re.DOTALL
    )

    if not match:
        return None

    code = match.group(1).upper()

    if not re.fullmatch(
        r"[A-Z0-9]{5}",
        code
    ):
        return None

    return code


# ============================================================
# MICROSOFT CODE
# ============================================================

def extract_microsoft_code(body):

    pattern = (
        r"Your\s+single-use\s+code"
        r"\s+is\s*:\s*(\d{6})"
    )

    match = re.search(
        pattern,
        body,
        re.IGNORECASE
    )

    if not match:
        return None

    return match.group(1)


# ============================================================
# GENERIC CODE
# ============================================================

def extract_generic_code(
    body,
    pattern
):

    if not pattern:
        return None

    try:

        match = re.search(
            pattern,
            body,
            re.IGNORECASE | re.DOTALL
        )

    except re.error:

        return None

    if not match:
        return None

    if match.lastindex is None:
        return None

    return match.group(1)


# ============================================================
# SERVICE CODE
# ============================================================

def extract_service_code(
    service,
    body
):

    name = service.get(
        "name",
        ""
    ).lower()

    if name == "steam":

        return extract_steam_code(
            body
        )

    if name == "microsoft":

        return extract_microsoft_code(
            body
        )

    return extract_generic_code(
        body,
        service.get(
            "pattern",
            ""
        )
    )


# ============================================================
# SEARCH ONE SERVICE
# ============================================================

def search_service(
    gmail,
    service,
    minutes
):

    sender = service.get(
        "sender",
        ""
    ).strip()

    subject = service.get(
        "subject",
        ""
    ).strip()

    if not sender:
        return []

    cutoff = int(
        time.time() - (
            minutes * 60
        )
    )

    query_parts = [
        f"from:{sender}",
        f"after:{cutoff}"
    ]

    if subject:

        query_parts.append(
            f"subject:({subject})"
        )

    query = " ".join(
        query_parts
    )

    try:

        response = gmail.users().messages().list(
            userId="me",
            q=query,
            maxResults=10
        ).execute()

    except Exception:

        return []

    messages = response.get(
        "messages",
        []
    )

    matches = []

    for message in messages:

        try:

            email = gmail.users().messages().get(
                userId="me",
                id=message["id"],
                format="full"
            ).execute()

            payload = email.get(
                "payload",
                {}
            )

            headers = get_headers(
                payload
            )

            timestamp = get_timestamp(
                headers
            )

            if timestamp and timestamp < cutoff:
                continue

            body = extract_text(
                payload
            )

            code = extract_service_code(
                service,
                body
            )

            if not code:
                continue

            matches.append({
                "service": service["name"],
                "code": code,
                "timestamp": timestamp,
                "message_id": message["id"]
            })

        except Exception:

            continue

    return matches


# ============================================================
# SEARCH ALL SERVICES
# ============================================================

def find_codes(
    gmail,
    services,
    minutes
):

    all_results = []

    for service in services:

        if not service.get(
            "enabled",
            True
        ):
            continue

        results = search_service(
            gmail,
            service,
            minutes
        )

        all_results.extend(
            results
        )

    all_results.sort(
        key=lambda x: x["timestamp"],
        reverse=True
    )

    unique = []

    seen = set()

    for result in all_results:

        key = (
            result["message_id"],
            result["code"]
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        unique.append(
            result
        )

    return unique


# ============================================================
# GMAIL WORKER
# ============================================================

class GmailWorker(QThread):

    finished = Signal(object)

    error = Signal(str)

    def __init__(
        self,
        services,
        minutes
    ):

        super().__init__()

        self.services = services
        self.minutes = minutes

    def run(self):

        try:

            gmail = authenticate()

            results = find_codes(
                gmail,
                self.services,
                self.minutes
            )

            self.finished.emit(
                results
            )

        except Exception as e:

            self.error.emit(
                str(e)
            )


# ============================================================
# CODE CARD
# ============================================================

class CodeCard(QFrame):

    def __init__(
        self,
        service,
        code,
        parent=None
    ):

        super().__init__(
            parent
        )

        self.code = code

        self.setObjectName(
            "codeCard"
        )

        layout = QHBoxLayout(
            self
        )

        layout.setContentsMargins(
            18,
            12,
            12,
            12
        )

        info = QVBoxLayout()

        service_label = QLabel(
            service
        )

        service_label.setObjectName(
            "service"
        )

        code_label = QLabel(
            code
        )

        code_label.setObjectName(
            "code"
        )

        info.addWidget(
            service_label
        )

        info.addWidget(
            code_label
        )

        layout.addLayout(
            info
        )

        layout.addStretch()

        # Fixed width prevents "Copied!" from getting cut off.
        self.copy_button = QPushButton(
            "Copy"
        )

        self.copy_button.setObjectName(
            "secondary"
        )

        self.copy_button.setFixedSize(
            88,
            38
        )

        self.copy_button.clicked.connect(
            self.copy_code
        )

        layout.addWidget(
            self.copy_button
        )


    def copy_code(self):

        pyperclip.copy(
            self.code
        )

        self.copy_button.setText(
            "Copied!"
        )

        # Return to Copy after a moment.
        QTimer.singleShot(
            1200,
            lambda: self.copy_button.setText(
                "Copy"
            )
        )


# ============================================================
# SERVICE DIALOG
# ============================================================

class ServiceDialog(QDialog):

    def __init__(
        self,
        parent=None,
        service=None
    ):

        super().__init__(
            parent
        )

        self.setWindowTitle(
            "Add Service"
            if service is None
            else "Edit Service"
        )

        self.setMinimumWidth(
            500
        )

        self.setStyleSheet("""
            QDialog {
                background: #202124;
            }

            QLabel {
                color: #e8eaed;
            }

            QLabel#help {
                color: #9aa0a6;
            }

            QLineEdit {
                background: #303134;
                color: #ffffff;
                border: 1px solid #5f6368;
                border-radius: 7px;
                padding: 9px;
            }

            QCheckBox {
                color: #e8eaed;
            }

            QPushButton {
                background: #8ab4f8;
                color: #202124;
                border: none;
                border-radius: 7px;
                padding: 9px 16px;
                font-weight: 600;
            }
        """)

        layout = QFormLayout(
            self
        )

        self.name_input = QLineEdit()

        self.sender_input = QLineEdit()

        self.subject_input = QLineEdit()

        self.pattern_input = QLineEdit()

        self.enabled_input = QCheckBox(
            "Enable this service"
        )

        self.enabled_input.setChecked(
            True
        )

        if service:

            self.name_input.setText(
                service.get(
                    "name",
                    ""
                )
            )

            self.sender_input.setText(
                service.get(
                    "sender",
                    ""
                )
            )

            self.subject_input.setText(
                service.get(
                    "subject",
                    ""
                )
            )

            self.pattern_input.setText(
                service.get(
                    "pattern",
                    ""
                )
            )

            self.enabled_input.setChecked(
                service.get(
                    "enabled",
                    True
                )
            )

        layout.addRow(
            "Service name:",
            self.name_input
        )

        layout.addRow(
            "Sender email:",
            self.sender_input
        )

        layout.addRow(
            "Subject contains:",
            self.subject_input
        )

        layout.addRow(
            "Code pattern:",
            self.pattern_input
        )

        layout.addRow(
            "",
            self.enabled_input
        )

        help_label = QLabel(
            "Microsoft and Steam use built-in "
            "recognition, so their pattern can be blank.\n\n"
            "For other services, use a regex with "
            "one capture group around the code."
        )

        help_label.setObjectName(
            "help"
        )

        help_label.setWordWrap(
            True
        )

        layout.addRow(
            "",
            help_label
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save
            | QDialogButtonBox.Cancel
        )

        buttons.accepted.connect(
            self.validate
        )

        buttons.rejected.connect(
            self.reject
        )

        layout.addRow(
            buttons
        )


    def validate(self):

        name = self.name_input.text().strip()

        sender = self.sender_input.text().strip()

        pattern = self.pattern_input.text().strip()

        if not name:

            QMessageBox.warning(
                self,
                "Missing Name",
                "Enter a service name."
            )

            return

        if not sender:

            QMessageBox.warning(
                self,
                "Missing Sender",
                "Enter a sender email."
            )

            return

        builtin = name.lower() in (
            "microsoft",
            "steam"
        )

        if not pattern and not builtin:

            QMessageBox.warning(
                self,
                "Missing Pattern",
                "Enter a code pattern."
            )

            return

        if pattern:

            try:

                compiled = re.compile(
                    pattern
                )

                if compiled.groups < 1:

                    QMessageBox.warning(
                        self,
                        "Invalid Pattern",
                        "The pattern needs one capture group."
                    )

                    return

            except re.error as e:

                QMessageBox.warning(
                    self,
                    "Invalid Pattern",
                    str(e)
                )

                return

        self.accept()


    def get_service(self):

        return {
            "name": self.name_input.text().strip(),
            "sender": self.sender_input.text().strip(),
            "subject": self.subject_input.text().strip(),
            "pattern": self.pattern_input.text().strip(),
            "enabled": self.enabled_input.isChecked()
        }


# ============================================================
# UI STYLE
# ============================================================

STYLE = """

QMainWindow {
    background: #202124;
}

QWidget {
    color: #e8eaed;
    font-family: "Segoe UI";
    font-size: 10pt;
}

QTabWidget::pane {
    border: none;
}

QTabBar::tab {
    background: #202124;
    color: #9aa0a6;
    padding: 12px 24px;
    border: none;
}

QTabBar::tab:selected {
    color: #ffffff;
    border-bottom: 2px solid #8ab4f8;
}

QLabel#title {
    font-size: 23px;
    font-weight: 600;
}

QLabel#subtitle {
    color: #9aa0a6;
}

QLabel#status {
    color: #9aa0a6;
}

QLabel#service {
    color: #8ab4f8;
    font-size: 11px;
    font-weight: 600;
}

QLabel#code {
    font-family: Consolas;
    font-size: 27px;
    font-weight: bold;
}

QFrame#codeCard {
    /* Same background as the app */
    background: #202124;

    /* Subtle black outline */
    border: 1px solid #080808;

    border-radius: 12px;
}

QPushButton {
    background: #8ab4f8;
    color: #202124;
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    font-weight: 600;
}

QPushButton:hover {
    background: #aecbfa;
}

QPushButton#secondary {
    background: #303134;
    color: #e8eaed;
    border: 1px solid #080808;
}

QPushButton#secondary:hover {
    background: #3c4043;
}

QPushButton#danger {
    background: #a50e0e;
    color: #ffffff;
}

QLineEdit,
QSpinBox {
    background: #303134;
    border: 1px solid #5f6368;
    border-radius: 7px;
    padding: 9px;
    color: #ffffff;
}

QListWidget {
    background: #292a2d;
    border: none;
    border-radius: 10px;
}

QListWidget::item {
    padding: 12px;
    border-bottom: 1px solid #3c4043;
}

QListWidget::item:selected {
    background: #3c4043;
}

QCheckBox {
    spacing: 8px;
}

QScrollArea {
    border: none;
    background: #202124;
}

QScrollArea > QWidget {
    background: #202124;
}

QScrollArea QWidget {
    background: #202124;
}

QFrame#codeCard {
    background: #202124;
    border: 1px solid #080808;
    border-radius: 12px;
}

"""


# ============================================================
# MAIN WINDOW
# ============================================================

class CodeClip(QMainWindow):

    def __init__(self):

        super().__init__()

        self.settings = load_settings()

        self.worker = None

        self.quick_window = None

        self.setWindowTitle(
            "CodeClip"
        )

        self.resize(
            700,
            600
        )

        self.setStyleSheet(
            STYLE
        )

        self.build_ui()

        # Automatically scan after the window
        # has finished loading.
        QTimer.singleShot(
            350,
            self.scan_gmail
        )


    # ========================================================
    # BUILD UI
    # ========================================================

    def build_ui(self):

        self.tabs = QTabWidget()

        self.codes_tab = QWidget()

        self.settings_tab = QWidget()

        self.tabs.addTab(
            self.codes_tab,
            "Codes"
        )

        self.tabs.addTab(
            self.settings_tab,
            "Settings"
        )

        self.build_codes()

        self.build_settings()

        self.setCentralWidget(
            self.tabs
        )


    # ========================================================
    # CODES TAB
    # ========================================================

    def build_codes(self):

        layout = QVBoxLayout(
            self.codes_tab
        )

        layout.setContentsMargins(
            35,
            30,
            35,
            25
        )

        layout.setSpacing(
            16
        )

        header = QHBoxLayout()

        title_box = QVBoxLayout()

        title = QLabel(
            "CodeClip"
        )

        title.setObjectName(
            "title"
        )

        subtitle = QLabel(
            "Verification codes"
        )

        subtitle.setObjectName(
            "subtitle"
        )

        title_box.addWidget(
            title
        )

        title_box.addWidget(
            subtitle
        )

        header.addLayout(
            title_box
        )

        header.addStretch()

        quick_button = QPushButton(
            "Quick Mode"
        )

        quick_button.setObjectName(
            "secondary"
        )

        quick_button.clicked.connect(
            self.open_quick_mode
        )

        header.addWidget(
            quick_button
        )

        layout.addLayout(
            header
        )

        self.status_label = QLabel(
            "Ready"
        )

        self.status_label.setObjectName(
            "status"
        )

        layout.addWidget(
            self.status_label
        )

        scroll = QScrollArea()

        scroll.setWidgetResizable(
            True
        )

        container = QWidget()

        self.code_layout = QVBoxLayout(
            container
        )

        self.code_layout.setSpacing(
            10
        )

        self.code_layout.addStretch()

        scroll.setWidget(
            container
        )

        layout.addWidget(
            scroll
        )

        scan_button = QPushButton(
            "Scan Gmail"
        )

        scan_button.clicked.connect(
            self.scan_gmail
        )

        layout.addWidget(
            scan_button
        )


    def clear_codes(self):

        while self.code_layout.count() > 1:

            item = self.code_layout.takeAt(
                0
            )

            widget = item.widget()

            if widget:

                widget.deleteLater()


    def show_codes(
        self,
        results
    ):

        self.clear_codes()

        if not results:

            self.status_label.setText(
                "No recent codes found."
            )

            return

        for result in results:

            card = CodeCard(
                result["service"],
                result["code"]
            )

            self.code_layout.insertWidget(
                self.code_layout.count() - 1,
                card
            )

        count = len(
            results
        )

        self.status_label.setText(
            f"{count} code"
            + (
                "s"
                if count != 1
                else ""
            )
            + " found"
        )


    # ========================================================
    # SETTINGS TAB
    # ========================================================

    def build_settings(self):

        layout = QVBoxLayout(
            self.settings_tab
        )

        layout.setContentsMargins(
            35,
            30,
            35,
            30
        )

        title = QLabel(
            "Settings"
        )

        title.setObjectName(
            "title"
        )

        layout.addWidget(
            title
        )

        subtitle = QLabel(
            "Manage your code sources."
        )

        subtitle.setObjectName(
            "subtitle"
        )

        layout.addWidget(
            subtitle
        )

        layout.addSpacing(
            15
        )

        services_label = QLabel(
            "Services"
        )

        services_label.setStyleSheet(
            "font-size: 15px; font-weight: 600;"
        )

        layout.addWidget(
            services_label
        )

        self.service_list = QListWidget()

        layout.addWidget(
            self.service_list
        )

        self.refresh_service_list()

        buttons = QHBoxLayout()

        add = QPushButton(
            "+ Add Service"
        )

        add.clicked.connect(
            self.add_service
        )

        edit = QPushButton(
            "Edit"
        )

        edit.setObjectName(
            "secondary"
        )

        edit.clicked.connect(
            self.edit_service
        )

        delete = QPushButton(
            "Delete"
        )

        delete.setObjectName(
            "danger"
        )

        delete.clicked.connect(
            self.delete_service
        )

        buttons.addWidget(
            add
        )

        buttons.addWidget(
            edit
        )

        buttons.addWidget(
            delete
        )

        layout.addLayout(
            buttons
        )

        layout.addSpacing(
            15
        )

        time_row = QHBoxLayout()

        label = QLabel(
            "Search the last:"
        )

        self.minutes = QSpinBox()

        self.minutes.setMinimum(
            1
        )

        self.minutes.setMaximum(
            60
        )

        self.minutes.setValue(
            self.settings.get(
                "minutes",
                DEFAULT_MINUTES
            )
        )

        self.minutes.setSuffix(
            " minutes"
        )

        time_row.addWidget(
            label
        )

        time_row.addWidget(
            self.minutes
        )

        time_row.addStretch()

        layout.addLayout(
            time_row
        )

        self.auto_copy = QCheckBox(
            "Automatically copy the newest code"
        )

        self.auto_copy.setChecked(
            self.settings.get(
                "auto_copy",
                True
            )
        )

        layout.addWidget(
            self.auto_copy
        )

        self.quick_mode = QCheckBox(
            "Start in Quick Mode"
        )

        self.quick_mode.setChecked(
            self.settings.get(
                "quick_mode",
                False
            )
        )

        layout.addWidget(
            self.quick_mode
        )

        save = QPushButton(
            "Save Settings"
        )

        save.clicked.connect(
            self.save_settings
        )

        layout.addWidget(
            save
        )

        layout.addStretch()


    # ========================================================
    # SERVICES
    # ========================================================

    def refresh_service_list(self):

        self.service_list.clear()

        for service in self.settings[
            "services"
        ]:

            enabled = service.get(
                "enabled",
                True
            )

            icon = "✓" if enabled else "○"

            item = QListWidgetItem(
                f"{icon}  {service['name']}\n"
                f"     {service['sender']}"
            )

            self.service_list.addItem(
                item
            )


    def add_service(self):

        dialog = ServiceDialog(
            self
        )

        if dialog.exec():

            self.settings[
                "services"
            ].append(
                dialog.get_service()
            )

            self.refresh_service_list()

            save_settings(
                self.settings
            )


    def edit_service(self):

        row = self.service_list.currentRow()

        if row < 0:

            QMessageBox.information(
                self,
                "Select Service",
                "Select a service first."
            )

            return

        service = self.settings[
            "services"
        ][row]

        dialog = ServiceDialog(
            self,
            service
        )

        if dialog.exec():

            self.settings[
                "services"
            ][row] = (
                dialog.get_service()
            )

            self.refresh_service_list()

            save_settings(
                self.settings
            )


    def delete_service(self):

        row = self.service_list.currentRow()

        if row < 0:
            return

        service = self.settings[
            "services"
        ][row]

        answer = QMessageBox.question(
            self,
            "Delete Service",
            f"Delete {service['name']}?"
        )

        if answer == QMessageBox.Yes:

            del self.settings[
                "services"
            ][row]

            self.refresh_service_list()

            save_settings(
                self.settings
            )


    # ========================================================
    # SAVE SETTINGS
    # ========================================================

    def save_settings(self):

        self.settings[
            "minutes"
        ] = self.minutes.value()

        self.settings[
            "auto_copy"
        ] = self.auto_copy.isChecked()

        self.settings[
            "quick_mode"
        ] = self.quick_mode.isChecked()

        save_settings(
            self.settings
        )

        QMessageBox.information(
            self,
            "Saved",
            "Settings saved."
        )


    # ========================================================
    # GMAIL SCAN
    # ========================================================

    def scan_gmail(self):

        if (
            self.worker
            and self.worker.isRunning()
        ):
            return

        services = [
            service
            for service in self.settings[
                "services"
            ]
            if service.get(
                "enabled",
                True
            )
        ]

        if not services:

            self.status_label.setText(
                "No services enabled."
            )

            return

        self.clear_codes()

        self.status_label.setText(
            "Looking for codes..."
        )

        self.worker = GmailWorker(
            services,
            self.settings[
                "minutes"
            ]
        )

        self.worker.finished.connect(
            self.scan_finished
        )

        self.worker.error.connect(
            self.scan_error
        )

        self.worker.start()


    def scan_finished(
        self,
        results
    ):

        self.show_codes(
            results
        )

        if (
            results
            and self.settings.get(
                "auto_copy",
                True
            )
        ):

            pyperclip.copy(
                results[0]["code"]
            )


    def scan_error(
        self,
        error
    ):

        self.status_label.setText(
            "Gmail connection failed."
        )

        QMessageBox.critical(
            self,
            "CodeClip Error",
            error
        )


    # ========================================================
    # QUICK MODE
    # ========================================================

    def open_quick_mode(self):

        self.quick_window = QuickWindow(
            self.settings
        )

        self.quick_window.show()

        self.quick_window.start_search()


# ============================================================
# QUICK MODE
# ============================================================

class QuickWindow(QWidget):

    def __init__(
        self,
        settings
    ):

        super().__init__()

        self.settings = settings

        self.worker = None

        self.setWindowTitle(
            "CodeClip"
        )

        self.setMinimumWidth(
            300
        )

        self.setStyleSheet(
            STYLE
        )

        self.layout = QVBoxLayout(
            self
        )

        self.layout.setContentsMargins(
            25,
            20,
            25,
            20
        )

        title = QLabel(
            "CodeClip"
        )

        title.setObjectName(
            "title"
        )

        title.setAlignment(
            Qt.AlignCenter
        )

        self.layout.addWidget(
            title
        )

        self.status = QLabel(
            "Looking for codes..."
        )

        self.status.setObjectName(
            "status"
        )

        self.status.setAlignment(
            Qt.AlignCenter
        )

        self.layout.addWidget(
            self.status
        )


    def start_search(self):

        services = [
            service
            for service in self.settings[
                "services"
            ]
            if service.get(
                "enabled",
                True
            )
        ]

        self.worker = GmailWorker(
            services,
            self.settings[
                "minutes"
            ]
        )

        self.worker.finished.connect(
            self.show_codes
        )

        self.worker.error.connect(
            self.show_error
        )

        self.worker.start()


    def show_codes(
        self,
        results
    ):

        if not results:

            self.status.setText(
                "No codes found"
            )

            return

        self.status.hide()

        for result in results:

            service = QLabel(
                result["service"]
            )

            service.setObjectName(
                "service"
            )

            service.setAlignment(
                Qt.AlignCenter
            )

            code = QLabel(
                result["code"]
            )

            code.setObjectName(
                "code"
            )

            code.setAlignment(
                Qt.AlignCenter
            )

            self.layout.addWidget(
                service
            )

            self.layout.addWidget(
                code
            )

        if self.settings.get(
            "auto_copy",
            True
        ):

            pyperclip.copy(
                results[0]["code"]
            )


    def show_error(
        self,
        error
    ):

        self.status.setText(
            "Gmail error"
        )

        QMessageBox.critical(
            self,
            "CodeClip Error",
            error
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        "CodeClip"
    )

    window = CodeClip()

    window.show()

    sys.exit(
        app.exec()
    )