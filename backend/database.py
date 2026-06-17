import sqlite3
import threading
import os

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "space_miner.db")

_lock = threading.Lock()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS players (
                username TEXT PRIMARY KEY,
                ore INTEGER NOT NULL DEFAULT 0,
                fuel INTEGER NOT NULL DEFAULT 100,
                max_cargo INTEGER NOT NULL DEFAULT 100,
                oxygen INTEGER NOT NULL DEFAULT 100,
                max_oxygen INTEGER NOT NULL DEFAULT 100,
                mining INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def get_player(username):
    with _lock:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM players WHERE username = ?", (username,)
            ).fetchone()
            if row:
                return dict(row)
            return None


def create_player(username):
    with _lock:
        with get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO players (username) VALUES (?)",
                (username,),
            )
            conn.commit()
    return get_player(username)


def update_player(username, **fields):
    if not fields:
        return
    with _lock:
        set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
        values = list(fields.values()) + [username]
        with get_conn() as conn:
            conn.execute(
                f"UPDATE players SET {set_clause} WHERE username = ?",
                values,
            )
            conn.commit()
    return get_player(username)
