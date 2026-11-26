"""SQLite-Zustand: gesehene Angebote, Erstlauf-Marker, Warn-Zeitstempel."""
from __future__ import annotations

import sqlite3
import time


class Store:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS seen (
                key TEXT PRIMARY KEY, title TEXT, ts INTEGER);
            CREATE TABLE IF NOT EXISTS baseline (
                search_key TEXT PRIMARY KEY, watch TEXT, ts INTEGER);
            CREATE TABLE IF NOT EXISTS meta (
                k TEXT PRIMARY KEY, v TEXT);
            """
        )
        self.db.commit()

    # --- gesehene Angebote -------------------------------------------------
    def is_seen(self, key: str) -> bool:
        return self.db.execute("SELECT 1 FROM seen WHERE key=?", (key,)).fetchone() is not None

    def mark_seen(self, key: str, title: str = "") -> None:
        self.db.execute("INSERT OR IGNORE INTO seen VALUES (?,?,?)", (key, title[:200], int(time.time())))
        self.db.commit()

    def prune(self, days: int = 90) -> None:
        self.db.execute("DELETE FROM seen WHERE ts < ?", (int(time.time()) - days * 86400,))
        self.db.commit()

    # --- Erstlauf ----------------------------------------------------------
    def has_baseline(self, search_key: str) -> bool:
        return self.db.execute("SELECT 1 FROM baseline WHERE search_key=?", (search_key,)).fetchone() is not None

    def set_baseline(self, search_key: str, watch: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO baseline VALUES (?,?,?)", (search_key, watch, int(time.time())))
        self.db.commit()

    # --- Meta (Warnungen) --------------------------------------------------
    def get_meta(self, k: str):
        row = self.db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return row[0] if row else None

    def set_meta(self, k: str, v) -> None:
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (k, str(v)))
        self.db.commit()

    def close(self):
        self.db.close()
