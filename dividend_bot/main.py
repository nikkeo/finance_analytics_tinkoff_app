"""
Dividend Bot — main entry point.
Runs APScheduler daily at 07:00 UTC (10:00 MSK).

Schedule:
  07:00 UTC — scan for new dividends, send buy/sell reminders
"""

import sys
import os
# abspath — чтобы бот запускался из любой рабочей директории,
# а не только из dividend_bot/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import config  # noqa: F401
except ImportError:
    sys.exit('config.py не найден. Скопируйте dividend_bot/config.example.py '
             'в dividend_bot/config.py и укажите токен Telegram.')

from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import date

import db
from analysis.signals import find_new_dividends
from analysis.indicators import get_imoex_analysis
from data.moex import get_company_info
from notify.telegram import send_new_dividend, send_buy_reminder, send_sell_reminder
import time


def run_daily_check():
    print(f"\n[{date.today()}] Starting daily check...")

    # ── 1. Buy reminders ────────────────────────────────────────────────────
    buy_reminders = db.get_pending_buy_reminders()
    for key, signal in buy_reminders:
        print(f"  [buy reminder] {signal['ticker']} ex={signal['ex_date']}")
        imoex = get_imoex_analysis()
        time.sleep(0.3)
        info  = get_company_info(signal["ticker"])
        time.sleep(0.3)
        signal["imoex"]         = imoex
        signal["current_price"] = info.get("price")
        send_buy_reminder(signal)
        db.mark_buy_reminded(key, buy_price=info.get("price"))

    # ── 2. Sell reminders ───────────────────────────────────────────────────
    sell_reminders = db.get_pending_sell_reminders()
    for key, signal in sell_reminders:
        print(f"  [sell reminder] {signal['ticker']} ex={signal['ex_date']}")
        imoex = get_imoex_analysis()
        time.sleep(0.3)
        info  = get_company_info(signal["ticker"])
        time.sleep(0.3)
        signal["imoex"]         = imoex
        signal["current_price"] = info.get("price")
        signal["buy_price"]     = db.get_buy_price(key)
        send_sell_reminder(signal)
        db.mark_sell_reminded(key)

    # ── 3. Scan for new dividends ────────────────────────────────────────────
    seen = db.get_seen_keys()
    new_signals = find_new_dividends(seen)

    if not new_signals:
        print("  No new dividends found.")
    else:
        for signal in new_signals:
            send_new_dividend(signal)
            db.save_signal(signal)
            print(f"  [sent] {signal['ticker']} ex={signal['ex_date']}")
            time.sleep(1)

    print(f"  Done. buy={len(buy_reminders)} sell={len(sell_reminders)} new={len(new_signals)}")


if __name__ == "__main__":
    db.init()

    # Run once immediately on start (useful for testing)
    if "--now" in sys.argv:
        run_daily_check()
        sys.exit(0)

    scheduler = BlockingScheduler(timezone="UTC")
    # Every weekday at 07:00 UTC = 10:00 MSK
    scheduler.add_job(run_daily_check, "cron", day_of_week="mon-fri", hour=7, minute=0)

    print("Dividend bot started. Waiting for schedule (Mon-Fri 07:00 UTC)...")
    print("Run with --now to trigger immediately.")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("Bot stopped.")
