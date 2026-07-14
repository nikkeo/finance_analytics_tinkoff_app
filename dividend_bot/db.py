import sqlite3
import json
from datetime import date

DB_PATH = "dividend_bot.db"


def init():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                key         TEXT NOT NULL UNIQUE,   -- TICKER_EXDATE
                ticker      TEXT NOT NULL,
                ex_date     TEXT NOT NULL,
                buy_date    TEXT,
                sell_date   TEXT,
                buy_price   REAL,
                payload     TEXT,                   -- full signal JSON
                sent_at     TEXT DEFAULT CURRENT_TIMESTAMP,
                buy_reminded  INTEGER DEFAULT 0,
                sell_reminded INTEGER DEFAULT 0
            )
        """)
        conn.commit()


def get_seen_keys():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT key FROM signals").fetchall()
    return {r[0] for r in rows}


def save_signal(signal):
    key     = f"{signal['ticker']}_{signal['ex_date']}"
    payload = json.dumps(signal, ensure_ascii=False, default=str)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO signals (key, ticker, ex_date, buy_date, sell_date, payload) VALUES (?,?,?,?,?,?)",
            (key, signal["ticker"], signal["ex_date"], signal.get("buy_date"), signal.get("sell_date"), payload)
        )
        conn.commit()


def get_pending_buy_reminders():
    """Return signals where today == buy_date and not yet reminded."""
    today = date.today().strftime("%Y-%m-%d")
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT key, payload FROM signals WHERE buy_date = ? AND buy_reminded = 0",
            (today,)
        ).fetchall()
    return [(r[0], json.loads(r[1])) for r in rows]


def get_pending_sell_reminders():
    """Return signals where today == sell_date and not yet reminded."""
    today = date.today().strftime("%Y-%m-%d")
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT key, payload FROM signals WHERE sell_date = ? AND sell_reminded = 0",
            (today,)
        ).fetchall()
    return [(r[0], json.loads(r[1])) for r in rows]


def mark_buy_reminded(key, buy_price=None):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE signals SET buy_reminded = 1, buy_price = ? WHERE key = ?",
            (buy_price, key)
        )
        conn.commit()


def mark_sell_reminded(key):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE signals SET sell_reminded = 1 WHERE key = ?", (key,))
        conn.commit()


def get_buy_price(key):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT buy_price FROM signals WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None
