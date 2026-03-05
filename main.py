import sys
import os
import time
import sqlite3

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit, QTableWidget,
    QTableWidgetItem, QSystemTrayIcon, QMenu, QMessageBox, QLabel
)
from PyQt6.QtGui import QClipboard, QIcon, QAction, QImage, QPixmap
from PyQt6.QtCore import QTimer, Qt


DB = "clipboard_history.db"
IMAGES_DIR = "images"


class ClipboardDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB)
        self.create_table()

    def create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                pinned INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                type TEXT DEFAULT 'text',
                path TEXT
            )
        """)
        self.conn.commit()

    def add_text_item(self, text):
        self.conn.execute(
            "INSERT INTO history (content, type, path) VALUES (?, 'text', NULL)",
            (text,)
        )
        self.conn.commit()

    def add_image_item(self, path):
        self.conn.execute(
            "INSERT INTO history (content, type, path) VALUES (?, 'image', ?)",
            ("", path)
        )
        self.conn.commit()

    def search(self, query=""):
        cur = self.conn.cursor()
        if query:
            cur.execute(
                "SELECT id, content, pinned, type, path FROM history "
                "WHERE content LIKE ? ORDER BY pinned DESC, id DESC",
                (f"%{query}%",)
            )
        else:
            cur.execute(
                "SELECT id, content, pinned, type, path FROM history "
                "ORDER BY pinned DESC, id DESC"
            )
        return cur.fetchall()

    def set_pinned(self, item_id, pinned):
        self.conn.execute("UPDATE history SET pinned=? WHERE id=?", (pinned, item_id))
        self.conn.commit()

    def delete_item(self, item_id):
        self.conn.execute("DELETE FROM history WHERE id=?", (item_id,))
        self.conn.commit()


class ClipboardManager(QWidget):
    def __init__(self):
        super().__init__()
        self.db = ClipboardDB()
        self.clipboard = QApplication.clipboard()

        os.makedirs(IMAGES_DIR, exist_ok=True)

        self.last_text = ""
        self.last_image_hash = None

        self.setWindowTitle("Clipboard Manager")
        self.resize(900, 450)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search history…")
        self.search_bar.textChanged.connect(self.refresh_table)

        # Table with 5 columns: Pinned, Copy, Type, Content, Delete
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Pinned", "Copy", "Type", "Content", "Delete"])
        self.table.cellDoubleClicked.connect(self.copy_item)
        self.table.cellClicked.connect(self.handle_table_click)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, header.ResizeMode.Stretch)
        header.setSectionResizeMode(4, header.ResizeMode.ResizeToContents)

        layout = QVBoxLayout()
        layout.addWidget(self.search_bar)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.setup_tray()
        self.setup_clipboard_watcher()
        self.refresh_table()

    def hash_qimage(self, qimage):
        try:
            buffer = qimage.bits().asstring(qimage.width() * qimage.height() * qimage.depth() // 8)
            return hash(buffer)
        except Exception:
            return None

    def setup_clipboard_watcher(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_clipboard)
        self.timer.start(300)

    def check_clipboard(self):
        mime = self.clipboard.mimeData()

        # IMAGE HANDLING
        if mime.hasImage():
            qimage = self.clipboard.image()
            if not qimage.isNull():
                img_hash = self.hash_qimage(qimage)

                if img_hash == self.last_image_hash:
                    return

                self.last_image_hash = img_hash
                self.last_text = ""

                filename = os.path.join(
                    IMAGES_DIR,
                    f"img_{int(time.time() * 1000)}.png"
                )
                qimage.save(filename, "PNG")
                self.db.add_image_item(filename)
                self.refresh_table()
            return

        # TEXT HANDLING
        text = self.clipboard.text()
        if text and text != self.last_text:
            self.last_text = text
            self.last_image_hash = None
            self.db.add_text_item(text)
            self.refresh_table()

    def refresh_table(self):
        query = self.search_bar.text()
        rows = self.db.search(query)

        self.table.setRowCount(len(rows))
        self.table.clearContents()

        for row_idx, (item_id, content, pinned, item_type, path) in enumerate(rows):

            # PIN COLUMN
            pin_item = QTableWidgetItem("⭐" if pinned else "")
            pin_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            pin_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 0, pin_item)

            # COPY COLUMN
            copy_item = QTableWidgetItem("📋")
            copy_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            copy_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 1, copy_item)

            # TYPE COLUMN
            type_item = QTableWidgetItem("Image" if item_type == "image" else "Text")
            type_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 2, type_item)

            # CONTENT COLUMN (metadata item)
            meta_item = QTableWidgetItem("" if item_type == "image" else content)
            meta_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            meta_item.setData(Qt.ItemDataRole.UserRole, item_id)
            meta_item.setData(Qt.ItemDataRole.UserRole + 1, item_type)
            meta_item.setData(Qt.ItemDataRole.UserRole + 2, path if path else "")
            self.table.setItem(row_idx, 3, meta_item)

            # IMAGE THUMBNAIL
            if item_type == "image" and path and os.path.exists(path):
                label = QLabel()
                pixmap = QPixmap(path)

                if not pixmap.isNull():
                    THUMB_SIZE = 128
                    pixmap = pixmap.scaled(
                        THUMB_SIZE, THUMB_SIZE,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    label.setPixmap(pixmap)

                    # Auto-scale row height
                    self.table.setRowHeight(row_idx, pixmap.height() + 10)

                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setCellWidget(row_idx, 3, label)

            # DELETE COLUMN
            delete_item = QTableWidgetItem("❌")
            delete_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            delete_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 4, delete_item)

    def copy_item(self, row, col):
        item = self.table.item(row, 3)
        if not item:
            return

        item_type = item.data(Qt.ItemDataRole.UserRole + 1)
        path = item.data(Qt.ItemDataRole.UserRole + 2)

        if item_type == "image":
            if path and os.path.exists(path):
                qimage = QImage(path)
                if not qimage.isNull():
                    self.clipboard.setImage(qimage)
        else:
            self.clipboard.setText(item.text())

    def handle_table_click(self, row, col):
        item = self.table.item(row, 3)
        if not item:
            return

        item_id = item.data(Qt.ItemDataRole.UserRole)
        item_type = item.data(Qt.ItemDataRole.UserRole + 1)
        path = item.data(Qt.ItemDataRole.UserRole + 2)

        # PIN
        if col == 0:
            pinned = self.table.item(row, 0).text() == "⭐"
            self.db.set_pinned(item_id, 0 if pinned else 1)
            self.refresh_table()
            return

        # COPY
        if col == 1:
            if item_type == "image":
                if path and os.path.exists(path):
                    qimage = QImage(path)
                    if not qimage.isNull():
                        self.clipboard.setImage(qimage)
            else:
                self.clipboard.setText(item.text())
            return

        # DELETE
        if col == 4:
            pinned = self.table.item(row, 0).text() == "⭐"

            if pinned:
                reply = QMessageBox.question(
                    self,
                    "Pinned Item",
                    "This item is pinned. Unpin and delete it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return
                self.db.set_pinned(item_id, 0)

            if item_type == "image" and path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

            self.db.delete_item(item_id)
            self.refresh_table()

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