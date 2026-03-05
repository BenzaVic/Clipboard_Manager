import sys
import sqlite3


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

