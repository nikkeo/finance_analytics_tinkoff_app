import requests
import time
from config import MOEX_BASE

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "dividend-bot/1.0"})
REQUEST_DELAY = 0.3


def _get(url, params=None):
    try:
        r = SESSION.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[moex] error {url}: {e}")
        return None


def get_top_tickers(limit=100):
    """Returns list of (rank, ticker) sorted by market cap, top N."""
    data = _get(
        f"{MOEX_BASE}/engines/stock/markets/shares/boards/TQBR/securities.json",
        {"securities.columns": "SECID,ISSUESIZE,PREVPRICE"}
    )
    if not data:
        return []

    cols = data["securities"]["columns"]
    rows = data["securities"]["data"]
    si = cols.index("SECID")
    zi = cols.index("ISSUESIZE")
    pi = cols.index("PREVPRICE")

    stocks = []
    for row in rows:
        secid = row[si]
        size  = row[zi] or 0
        price = row[pi] or 0
        if secid and size > 0 and price > 0:
            stocks.append((secid, size * price))

    stocks.sort(key=lambda x: x[1], reverse=True)
    return [(i + 1, s[0]) for i, s in enumerate(stocks[:limit])]


def get_dividends(ticker):
    """Returns list of {ex_date, dividend} for ticker, RUB only."""
    data = _get(f"{MOEX_BASE}/securities/{ticker}/dividends.json")
    if not data or not data["dividends"]["data"]:
        return []

    cols = data["dividends"]["columns"]
    rows = data["dividends"]["data"]

    try:
        di = cols.index("registryclosedate")
        vi = cols.index("value")
        ci = cols.index("currencyid")
    except ValueError:
        return []

    result = []
    for row in rows:
        d_str    = row[di]
        value    = row[vi]
        currency = row[ci]
        if d_str and value and currency == "RUB":
            result.append({"ex_date": d_str, "dividend": value})

    return result


def get_candles(ticker, from_date, till_date, interval=24):
    """Returns {date_str: close_price} for ticker."""
    url = (
        f"{MOEX_BASE}/engines/stock/markets/shares"
        f"/boards/TQBR/securities/{ticker}/candles.json"
    )
    prices = {}
    start = 0
    while True:
        data = _get(url, {
            "from": from_date, "till": till_date,
            "interval": interval, "start": start
        })
        if not data:
            break
        cols = data["candles"]["columns"]
        rows = data["candles"]["data"]
        if not rows:
            break
        ci = cols.index("close")
        bi = cols.index("begin")
        for row in rows:
            d = row[bi][:10]
            c = row[ci]
            if c:
                prices[d] = c
        if len(rows) < 500:
            break
        start += 500
    return prices


def get_imoex_candles(from_date, till_date):
    """Returns {date_str: close_price} for IMOEX index."""
    url = (
        f"{MOEX_BASE}/engines/stock/markets/index"
        f"/boards/SNDX/securities/IMOEX/candles.json"
    )
    prices = {}
    data = _get(url, {"from": from_date, "till": till_date, "interval": 24})
    if not data:
        return prices
    cols = data["candles"]["columns"]
    rows = data["candles"]["data"]
    ci = cols.index("close")
    bi = cols.index("begin")
    for row in rows:
        d = row[bi][:10]
        c = row[ci]
        if c:
            prices[d] = c
    return prices


def get_company_info(ticker):
    """Returns basic company info: name, price, 52w high/low."""
    data = _get(
        f"{MOEX_BASE}/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json",
        {"securities.columns": "SECID,SECNAME,PREVPRICE,HIGH52WEEK,LOW52WEEK"}
    )
    if not data or not data["securities"]["data"]:
        return {}

    cols = data["securities"]["columns"]
    row  = data["securities"]["data"][0]

    def safe(col):
        try:
            return row[cols.index(col)]
        except (ValueError, IndexError):
            return None

    return {
        "name":     safe("SECNAME"),
        "price":    safe("PREVPRICE"),
        "high_52w": safe("HIGH52WEEK"),
        "low_52w":  safe("LOW52WEEK"),
    }
