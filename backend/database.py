import sqlite3
import os
import time
import random

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
            credits INTEGER NOT NULL DEFAULT 50,
            mining INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    try:
        conn.execute("ALTER TABLE players ADD COLUMN credits INTEGER NOT NULL DEFAULT 50")
    except sqlite3.OperationalError:
        pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_type TEXT NOT NULL,
            item TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price_per_unit INTEGER NOT NULL,
            remaining INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
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


def refuel_with_ore(username):
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


def get_market_orders():
    conn = get_conn()
    now = int(time.time())
    rows = conn.execute(
        "SELECT * FROM market_orders WHERE expires_at > ? ORDER BY id",
        (now,)
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_market_expiry():
    conn = get_conn()
    now = int(time.time())
    row = conn.execute(
        "SELECT MAX(expires_at) as expires FROM market_orders WHERE expires_at > ?",
        (now,)
    ).fetchone()
    return row["expires"] if row and row["expires"] else 0


def refresh_market_orders(duration_seconds=300):
    conn = get_conn()
    now = int(time.time())
    expires = now + duration_seconds

    order_templates = [
        ("buy", "ore", random.randint(20, 80), random.randint(3, 8)),
        ("sell", "fuel", random.randint(10, 40), random.randint(2, 5)),
        ("buy", "ore", random.randint(30, 100), random.randint(4, 10)),
        ("sell", "fuel", random.randint(20, 50), random.randint(1, 3)),
    ]
    selected = random.sample(order_templates, random.randint(2, 3))

    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM market_orders")
        for order_type, item, quantity, price in selected:
            conn.execute(
                "INSERT INTO market_orders (order_type, item, quantity, price_per_unit, remaining, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (order_type, item, quantity, price, quantity, expires),
            )
        conn.execute("COMMIT")
    except Exception as e:
        conn.execute("ROLLBACK")
        raise e

    return get_market_orders(), expires


def execute_market_trade(username, order_id, amount):
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")

        order = conn.execute(
            "SELECT * FROM market_orders WHERE id = ?",
            (order_id,)
        ).fetchone()
        if not order:
            conn.execute("ROLLBACK")
            return None, "Order not found"

        now = int(time.time())
        if order["expires_at"] <= now:
            conn.execute("ROLLBACK")
            return None, "Order has expired"

        if order["remaining"] <= 0:
            conn.execute("ROLLBACK")
            return None, "Order is sold out"

        actual_amount = min(amount, order["remaining"])
        if actual_amount <= 0:
            conn.execute("ROLLBACK")
            return None, "Invalid amount"

        player = conn.execute(
            "SELECT * FROM players WHERE username = ?",
            (username,)
        ).fetchone()
        if not player:
            conn.execute("ROLLBACK")
            return None, "Player not found"

        order_type = order["order_type"]
        item = order["item"]
        total_price = 0
        final_amount = 0

        if order_type == "buy":
            if item == "ore":
                if player["ore"] < actual_amount:
                    actual_amount = player["ore"]
                if actual_amount <= 0:
                    conn.execute("ROLLBACK")
                    return None, "Not enough ore!"
                total_price = actual_amount * order["price_per_unit"]
                conn.execute(
                    "UPDATE players SET ore = ore - ?, credits = credits + ? WHERE username = ?",
                    (actual_amount, total_price, username),
                )
                final_amount = actual_amount
            else:
                conn.execute("ROLLBACK")
                return None, "Unknown item"

        elif order_type == "sell":
            if item == "fuel":
                max_add = 100 - player["fuel"]
                actual_amount = min(actual_amount, max_add)
                if actual_amount <= 0:
                    conn.execute("ROLLBACK")
                    return None, "Fuel tank is full!"
                total_price = actual_amount * order["price_per_unit"]
                if player["credits"] < total_price:
                    max_afford = player["credits"] // order["price_per_unit"]
                    if max_afford <= 0:
                        conn.execute("ROLLBACK")
                        return None, "Not enough credits!"
                    actual_amount = max_afford
                    total_price = actual_amount * order["price_per_unit"]
                conn.execute(
                    "UPDATE players SET credits = credits - ?, fuel = fuel + ? WHERE username = ?",
                    (total_price, actual_amount, username),
                )
                final_amount = actual_amount
            else:
                conn.execute("ROLLBACK")
                return None, "Unknown item"

        conn.execute(
            "UPDATE market_orders SET remaining = remaining - ? WHERE id = ?",
            (final_amount, order_id),
        )

        conn.execute("COMMIT")

        updated_player = get_player(username)
        updated_order_row = conn.execute(
            "SELECT * FROM market_orders WHERE id = ?",
            (order_id,)
        ).fetchone()
        return {
            "player": updated_player,
            "order": _row_to_dict(updated_order_row),
            "amount": final_amount,
            "total_price": total_price,
        }, None

    except Exception as e:
        conn.execute("ROLLBACK")
        raise e
