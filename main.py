import sys
import sqlite3

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit, QTableWidget,
    QTableWidgetItem, QSystemTrayIcon, QMenu
)
from PyQt6.QtGui import QClipboard, QIcon, QAction
from PyQt6.QtCore import QTimer, Qt


DB = "clipboard_history.db"


class ClipboardDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB)
        self.create_table()

    def create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT UNIQUE,
                pinned INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def add_item(self, text):
        try:
            self.conn.execute("INSERT OR IGNORE INTO history (content) VALUES (?)", (text,))
            self.conn.commit()
        except Exception:
            pass

    def search(self, query=""):
        cur = self.conn.cursor()
        if query:
            cur.execute("SELECT id, content, pinned FROM history WHERE content LIKE ? ORDER BY pinned DESC, id DESC", (f"%{query}%",))
        else:
            cur.execute("SELECT id, content, pinned FROM history ORDER BY pinned DESC, id DESC")
        return cur.fetchall()

    def set_pinned(self, item_id, pinned):
        self.conn.execute("UPDATE history SET pinned=? WHERE id=?", (pinned, item_id))
        self.conn.commit()

class ClipboardManager(QWidget):
    def __init__(self):
        super().__init__()
        self.db = ClipboardDB()
        self.clipboard = QApplication.clipboard()

        self.setWindowTitle("Clipboard Manager")
        self.resize(600, 400)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search history…")
        self.search_bar.textChanged.connect(self.refresh_table)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Content", "Pinned"])
        self.table.cellDoubleClicked.connect(self.copy_item)

        layout = QVBoxLayout()
        layout.addWidget(self.search_bar)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.setup_tray()
        self.setup_clipboard_watcher()
        self.refresh_table()

    def setup_clipboard_watcher(self):
        self.last_text = ""
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_clipboard)
        self.timer.start(300)

    def check_clipboard(self):
        text = self.clipboard.text()
        if text and text != self.last_text:
            self.last_text = text
            self.db.add_item(text)
            self.refresh_table()

    def refresh_table(self):
        query = self.search_bar.text()
        rows = self.db.search(query)

        self.table.setRowCount(len(rows))
        for row_idx, (item_id, content, pinned) in enumerate(rows):
            self.table.setItem(row_idx, 0, QTableWidgetItem(content))
            self.table.setItem(row_idx, 1, QTableWidgetItem("⭐" if pinned else ""))

    def copy_item(self, row, col):
        content = self.table.item(row, 0).text()
        self.clipboard.setText(content)

    def setup_tray(self):
        self.tray = QSystemTrayIcon(QIcon())
        menu = QMenu()

        show_action = QAction("Show")
        show_action.triggered.connect(self.show)
        menu.addAction(show_action)

        quit_action = QAction("Quit")
        quit_action.triggered.connect(sys.exit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ClipboardManager()
    window.show()
    sys.exit(app.exec())
