import sys
import os
import time
import sqlite3
import hashlib

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit, QTableWidget,
    QTableWidgetItem, QSystemTrayIcon, QMenu, QMessageBox, QLabel,
    QHBoxLayout, QPushButton, QSpinBox, QDialog, QFormLayout, QCheckBox
)
from PyQt6.QtGui import QClipboard, QIcon, QAction, QImage, QPixmap, QFont
from PyQt6.QtCore import QTimer, Qt, QSettings


DB = "clipboard_history.db"
IMAGES_DIR = "images"
MAX_HISTORY_ITEMS = 1000
THUMB_SIZE = 96


class ClipboardDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB)
        self.create_table()
        self.cleanup_old_items()

    def create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                pinned INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                type TEXT DEFAULT 'text',
                path TEXT,
                img_hash TEXT
            )
        """)
        self.conn.commit()

    def cleanup_old_items(self):
        """Remove old unpinned items to maintain history size limit"""
        try:
            # Keep only the most recent MAX_HISTORY_ITEMS unpinned items
            self.conn.execute("""
                DELETE FROM history
                WHERE id NOT IN (
                    SELECT id FROM history
                    WHERE pinned = 1
                    UNION
                    SELECT id FROM history
                    WHERE pinned = 0
                    ORDER BY id DESC
                    LIMIT ?
                )
            """, (MAX_HISTORY_ITEMS,))
            self.conn.commit()
        except Exception as e:
            print(f"Error cleaning up old items: {e}")

    def exists_text(self, text):
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT 1 FROM history WHERE type='text' AND content=?", (text,))
            return cur.fetchone() is not None
        except Exception as e:
            print(f"Error checking text existence: {e}")
            return False

    def exists_image_hash(self, img_hash):
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT 1 FROM history WHERE type='image' AND img_hash=?", (img_hash,))
            return cur.fetchone() is not None
        except Exception as e:
            print(f"Error checking image hash existence: {e}")
            return False

    def add_text_item(self, text):
        try:
            self.conn.execute(
                "INSERT INTO history (content, type, path, img_hash) VALUES (?, 'text', NULL, NULL)",
                (text,)
            )
            self.conn.commit()
            self.cleanup_old_items()
        except Exception as e:
            print(f"Error adding text item: {e}")

    def add_image_item(self, path, img_hash):
        try:
            self.conn.execute(
                "INSERT INTO history (content, type, path, img_hash) VALUES (?, 'image', ?, ?)",
                ("", path, img_hash)
            )
            self.conn.commit()
            self.cleanup_old_items()
        except Exception as e:
            print(f"Error adding image item: {e}")

    def search(self, query=""):
        try:
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
        except Exception as e:
            print(f"Error searching history: {e}")
            return []

    def set_pinned(self, item_id, pinned):
        try:
            self.conn.execute("UPDATE history SET pinned=? WHERE id=?", (pinned, item_id))
            self.conn.commit()
        except Exception as e:
            print(f"Error setting pinned status: {e}")

    def delete_item(self, item_id):
        try:
            self.conn.execute("DELETE FROM history WHERE id=?", (item_id,))
            self.conn.commit()
        except Exception as e:
            print(f"Error deleting item: {e}")


class ClipboardManager(QWidget):
    def __init__(self):
        super().__init__()
        self.db = ClipboardDB()
        self.clipboard = QApplication.clipboard()
        self.settings = QSettings("ClipboardManager", "ClipboardManager")

        os.makedirs(IMAGES_DIR, exist_ok=True)

        self.last_text = ""
        self.last_image_hash = None

        self.setWindowTitle("Clipboard Manager")
        self.resize(600, 500)

        # Load settings
        self.max_history = self.settings.value("max_history", MAX_HISTORY_ITEMS, type=int)
        self.auto_start = self.settings.value("auto_start", False, type=bool)

        self.setup_ui()
        self.setup_tray()
        self.setup_clipboard_watcher()
        self.refresh_table()

    def setup_ui(self):
        """Setup the main user interface"""
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search clipboard history...")
        self.search_bar.textChanged.connect(self.refresh_table)

        # Table with 5 columns: Pinned, Copy, Type, Content, Delete
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["⭐", "📋", "Type", "Content", "🗑️"])
        self.table.cellDoubleClicked.connect(self.copy_item)
        self.table.cellClicked.connect(self.handle_table_click)

        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.ResizeToContents)  # Pinned
        header.setSectionResizeMode(1, header.ResizeMode.ResizeToContents)  # Copy
        header.setSectionResizeMode(2, header.ResizeMode.ResizeToContents)  # Type
        header.setSectionResizeMode(3, header.ResizeMode.Stretch)           # Content expands
        header.setSectionResizeMode(4, header.ResizeMode.ResizeToContents)  # Delete

        # Buttons layout
        buttons_layout = QHBoxLayout()

        self.settings_btn = QPushButton("⚙️ Settings")
        self.settings_btn.clicked.connect(self.show_settings)
        buttons_layout.addWidget(self.settings_btn)

        self.clear_btn = QPushButton("🧹 Clear History")
        self.clear_btn.clicked.connect(self.clear_history)
        buttons_layout.addWidget(self.clear_btn)

        buttons_layout.addStretch()

        # Main layout
        layout = QVBoxLayout()
        layout.addWidget(self.search_bar)
        layout.addLayout(buttons_layout)
        layout.addWidget(self.table)
        self.setLayout(layout)

    def hash_qimage(self, qimage):
        """Generate a reliable hash for image deduplication"""
        try:
            # Convert image to bytes
            buffer = qimage.bits()
            if buffer is None:
                return None

            # Get image data as bytes
            byte_count = qimage.width() * qimage.height() * qimage.depth() // 8
            image_bytes = buffer.asstring(byte_count)

            # Use SHA256 for reliable hashing
            return hashlib.sha256(image_bytes).hexdigest()
        except Exception as e:
            print(f"Error hashing image: {e}")
            return None

    def setup_clipboard_watcher(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_clipboard)
        self.timer.start(300)

    def check_clipboard(self):
        """Monitor clipboard for new content"""
        try:
            mime = self.clipboard.mimeData()
            if not mime:
                return

            # IMAGE HANDLING
            if mime.hasImage():
                qimage = self.clipboard.image()
                if not qimage.isNull():
                    img_hash = self.hash_qimage(qimage)

                    # Skip duplicates
                    if img_hash == self.last_image_hash or self.db.exists_image_hash(img_hash):
                        return

                    self.last_image_hash = img_hash
                    self.last_text = ""

                    filename = os.path.join(IMAGES_DIR, f"img_{int(time.time() * 1000)}.png")
                    if qimage.save(filename, "PNG"):
                        self.db.add_image_item(filename, img_hash)
                        self.refresh_table()
                    else:
                        print(f"Failed to save image to {filename}")
                return

            # TEXT HANDLING
            text = self.clipboard.text()
            if text and text != self.last_text and not self.db.exists_text(text):
                self.last_text = text
                self.last_image_hash = None
                self.db.add_text_item(text)
                self.refresh_table()

        except Exception as e:
            print(f"Error checking clipboard: {e}")

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
                    THUMB_SIZE = 96  # smaller thumbnails
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

    def show_settings(self):
        """Show settings dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.setModal(True)

        layout = QFormLayout()

        # Max history items
        max_history_spin = QSpinBox()
        max_history_spin.setRange(100, 10000)
        max_history_spin.setValue(self.max_history)
        layout.addRow("Max History Items:", max_history_spin)

        # Auto start (placeholder for future implementation)
        auto_start_cb = QCheckBox()
        auto_start_cb.setChecked(self.auto_start)
        auto_start_cb.setEnabled(False)  # Disabled for now
        layout.addRow("Auto-start on login:", auto_start_cb)

        # Buttons
        buttons = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")

        save_btn.clicked.connect(lambda: self.save_settings(dialog, max_history_spin.value(), auto_start_cb.isChecked()))
        cancel_btn.clicked.connect(dialog.reject)

        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addRow(buttons)

        dialog.setLayout(layout)
        dialog.exec()

    def save_settings(self, dialog, max_history, auto_start):
        """Save settings and update application"""
        self.max_history = max_history
        self.auto_start = auto_start

        self.settings.setValue("max_history", max_history)
        self.settings.setValue("auto_start", auto_start)

        # Update database cleanup
        global MAX_HISTORY_ITEMS
        MAX_HISTORY_ITEMS = max_history
        self.db.cleanup_old_items()

        dialog.accept()
        self.refresh_table()

    def clear_history(self):
        """Clear all unpinned history items"""
        reply = QMessageBox.question(
            self,
            "Clear History",
            "This will delete all unpinned items from history. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Get all unpinned items
                cur = self.db.conn.cursor()
                cur.execute("SELECT id, type, path FROM history WHERE pinned = 0")
                items = cur.fetchall()

                # Delete associated image files
                for _, item_type, path in items:
                    if item_type == "image" and path and os.path.exists(path):
                        try:
                            os.remove(path)
                        except Exception as e:
                            print(f"Error deleting image file {path}: {e}")

                # Clear database
                self.db.conn.execute("DELETE FROM history WHERE pinned = 0")
                self.db.conn.commit()

                self.refresh_table()
                QMessageBox.information(self, "Success", "History cleared successfully!")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear history: {e}")

    def setup_tray(self):
        # Create a simple icon for the tray (could be improved with a proper icon file)
        icon = QIcon()
        # For now, use default icon - in production, load from resources
        self.tray = QSystemTrayIcon(icon)
        menu = QMenu()

        show_action = QAction("Show Clipboard Manager")
        show_action.triggered.connect(self.show)
        menu.addAction(show_action)

        menu.addSeparator()

        clear_action = QAction("Clear Unpinned History")
        clear_action.triggered.connect(self.clear_history)
        menu.addAction(clear_action)

        menu.addSeparator()

        quit_action = QAction("Quit")
        quit_action.triggered.connect(sys.exit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.setToolTip("Clipboard Manager")
        self.tray.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ClipboardManager()
    window.show()
    sys.exit(app.exec())