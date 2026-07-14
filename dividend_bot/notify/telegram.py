import requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, BUY_DAYS_BEFORE, SELL_DAYS_BEFORE


def _send(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"[telegram] send error: {e}")


def _imoex_line(imoex):
    if not imoex:
        return "нет данных"
    price = imoex["price"]
    ma50  = imoex["ma50"]
    ma200 = imoex["ma200"]
    a50   = "✅" if imoex["above_ma50"]  else "❌"
    a200  = "✅" if imoex["above_ma200"] else "❌"
    return (
        f"IMOEX: <b>{price}</b>\n"
        f"MA50:  {ma50}  (выше {a50})\n"
        f"MA200: {ma200}  (выше {a200})"
    )


def send_new_dividend(signal):
    s = signal

    # Universe label
    if s["in_top50"]:
        universe = f"Top-50 #{s['rank']} / Top-100 #{s['rank']}"
    else:
        universe = f"Top-100 #{s['rank']}"

    # Dividend yield
    yield_str = f"{s['div_yield_pct']}%" if s["div_yield_pct"] else "—"

    # Days to ex
    days_str = f"{s['days_to_ex']} торг. дней"

    # Entry/exit dates
    buy_str  = s["buy_date"]  or "нет данных"
    sell_str = s["sell_date"] or "нет данных"

    # 52w position
    price_str = f"{s['current_price']} ₽" if s["current_price"] else "—"
    if s["high_52w"] and s["low_52w"]:
        range_str = f"{s['low_52w']} ₽ — {s['high_52w']} ₽"
        pos_str   = f"{int(s['pos_52w'])}% от диапазона" if s["pos_52w"] is not None else "—"
    else:
        range_str = "—"
        pos_str   = "—"

    text = (
        f"📊 <b>НОВЫЙ ДИВИДЕНД</b>\n\n"
        f"<b>{s['ticker']}</b> / {s['name']}\n"
        f"{universe}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Дивиденд:   <b>{s['dividend']} ₽</b>  ({yield_str} от цены)\n"
        f"📅 Отсечка:    <b>{s['ex_date']}</b>\n"
        f"⏳ До отсечки: {days_str}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 <b>РЫНОК</b>\n\n"
        f"{_imoex_line(s['imoex'])}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>ОКНО ВХОДА</b>  (T-{BUY_DAYS_BEFORE} → T-{SELL_DAYS_BEFORE})\n\n"
        f"Вход:  <b>{buy_str}</b>\n"
        f"Выход: <b>{sell_str}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📉 <b>АКЦИЯ</b>\n\n"
        f"Цена сейчас:  {price_str}\n"
        f"52w диапазон: {range_str}\n"
        f"Позиция:      {pos_str}"
    )
    _send(text)


def send_buy_reminder(signal):
    s = signal
    price_str = f"{s['current_price']} ₽" if s["current_price"] else "—"
    text = (
        f"🟢 <b>ДЕНЬ ВХОДА — {s['ticker']}</b>\n\n"
        f"Отсечка через {BUY_DAYS_BEFORE} торг. дней ({s['ex_date']})\n"
        f"Покупать сегодня на закрытии (~18:50 МСК)\n\n"
        f"Цена вчера: {price_str}\n\n"
        f"{_imoex_line(s['imoex'])}"
    )
    _send(text)


def send_sell_reminder(signal):
    s = signal
    price_str = f"{s['current_price']} ₽" if s["current_price"] else "—"
    buy_price_str = f"{s.get('buy_price')} ₽" if s.get("buy_price") else "—"

    # Calculate P&L if we have buy price
    pnl_str = ""
    if s.get("buy_price") and s["current_price"]:
        pnl = (s["current_price"] - s["buy_price"]) / s["buy_price"] * 100
        pnl_str = f"\nИзменение с входа: <b>{pnl:+.1f}%</b>"

    text = (
        f"🔴 <b>ДЕНЬ ВЫХОДА — {s['ticker']}</b>\n\n"
        f"Отсечка завтра ({s['ex_date']})\n"
        f"Продавать сегодня на закрытии (~18:50 МСК)\n\n"
        f"Цена вчера:  {price_str}\n"
        f"Цена входа:  {buy_price_str}"
        f"{pnl_str}\n\n"
        f"{_imoex_line(s['imoex'])}"
    )
    _send(text)
