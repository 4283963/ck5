import sqlite3
import os

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "space_miner.db")

_conn = None


def get_conn():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA busy_timeout = 5000")
        _conn.execute("PRAGMA synchronous = NORMAL")
    return _conn


def close_conn():
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


def init_db():
    conn = get_conn()
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


def _row_to_dict(row):
    return dict(row) if row else None


def get_player(username):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM players WHERE username = ?", (username,)
    ).fetchone()
    return _row_to_dict(row)


def create_player(username):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO players (username) VALUES (?)",
        (username,),
    )
    conn.commit()
    return get_player(username)


def update_player(username, **fields):
    if not fields:
        return get_player(username)
    conn = get_conn()
    set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
    values = list(fields.values()) + [username]
    conn.execute(
        f"UPDATE players SET {set_clause} WHERE username = ?",
        values,
    )
    conn.commit()
    return get_player(username)


def upgrade_cargo(username):
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT ore, max_cargo FROM players WHERE username = ?",
            (username,)
        ).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return None, "Player not found"

        cost = row["max_cargo"]
        if row["ore"] < cost:
            conn.execute("ROLLBACK")
            return None, f"Need {cost} ore to upgrade cargo!"

        conn.execute(
            "UPDATE players SET ore = ore - ?, max_cargo = max_cargo + 50 WHERE username = ?",
            (cost, username),
        )
        conn.execute("COMMIT")
        return get_player(username), None
    except Exception as e:
        conn.execute("ROLLBACK")
        raise e


def refuel(username):
    cost_per_unit = 10 / 20
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT ore, fuel FROM players WHERE username = ?",
            (username,)
        ).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return None, "Player not found"

        if row["ore"] < 10:
            conn.execute("ROLLBACK")
            return None, "Not enough ore to refuel!"

        if row["fuel"] >= 100:
            conn.execute("ROLLBACK")
            return None, "Fuel tank is full!"

        desired_add = 20
        actual_add = min(desired_add, 100 - row["fuel"])
        actual_cost = int(actual_add * cost_per_unit)
        if actual_cost < 1:
            actual_cost = 1

        if row["ore"] < actual_cost:
            conn.execute("ROLLBACK")
            return None, "Not enough ore to refuel!"

        conn.execute(
            "UPDATE players SET ore = ore - ?, fuel = fuel + ? WHERE username = ?",
            (actual_cost, actual_add, username),
        )
        conn.execute("COMMIT")
        return get_player(username), None
    except Exception as e:
        conn.execute("ROLLBACK")
        raise e


def mining_tick(username, ore_per_tick, fuel_per_tick):
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT ore, fuel, max_cargo, mining FROM players WHERE username = ?",
            (username,)
        ).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return None

        if row["fuel"] <= 0 or not row["mining"]:
            if row["mining"]:
                conn.execute(
                    "UPDATE players SET mining = 0 WHERE username = ?",
                    (username,),
                )
                conn.execute("COMMIT")
                return get_player(username)
            conn.execute("ROLLBACK")
            return get_player(username)

        new_ore = min(row["ore"] + ore_per_tick, row["max_cargo"])
        new_fuel = max(row["fuel"] - fuel_per_tick, 0)
        still_mining = 1 if new_fuel > 0 else 0

        conn.execute(
            "UPDATE players SET ore = ?, fuel = ?, mining = ? WHERE username = ?",
            (new_ore, new_fuel, still_mining, username),
        )
        conn.execute("COMMIT")
        return get_player(username)
    except Exception as e:
        conn.execute("ROLLBACK")
        raise e
