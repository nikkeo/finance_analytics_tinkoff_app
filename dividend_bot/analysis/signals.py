from datetime import date, timedelta
from data.moex import get_dividends, get_candles, get_company_info, get_top_tickers
from analysis.indicators import get_imoex_analysis, nth_trading_day_before
from config import BUY_DAYS_BEFORE, SELL_DAYS_BEFORE, MIN_DAYS_TO_EX, TOP_50_LIMIT, TOP_100_LIMIT
import time


def get_trading_days_to_ex(ex_date_str, prices):
    """Count trading days from today to ex_date."""
    today_str = date.today().strftime("%Y-%m-%d")
    return sum(1 for d in prices if today_str <= d < ex_date_str)


def build_signal(rank, ticker, ex_date_str, dividend_val, imoex):
    """Build a full signal dict for a dividend event."""
    today      = date.today()
    today_str  = today.strftime("%Y-%m-%d")
    from_date  = (today - timedelta(days=60)).strftime("%Y-%m-%d")
    # need extra buffer to find T-7 before ex_date
    fetch_from = (date.fromisoformat(ex_date_str) - timedelta(days=30)).strftime("%Y-%m-%d")

    prices = get_candles(ticker, fetch_from, ex_date_str)
    time.sleep(0.3)

    dates_sorted = sorted(prices.keys())

    buy_date_str  = nth_trading_day_before(ex_date_str, BUY_DAYS_BEFORE,  dates_sorted)
    sell_date_str = nth_trading_day_before(ex_date_str, SELL_DAYS_BEFORE, dates_sorted)

    # Count trading days from today to ex_date
    days_to_ex = sum(1 for d in dates_sorted if today_str <= d < ex_date_str)

    # Current price
    company = get_company_info(ticker)
    time.sleep(0.3)

    current_price = company.get("price")
    high_52w      = company.get("high_52w")
    low_52w       = company.get("low_52w")
    name          = company.get("name", ticker)

    div_yield_pct = round(dividend_val / current_price * 100, 2) if current_price else None

    # Position in 52w range
    pos_52w = None
    if high_52w and low_52w and current_price and high_52w > low_52w:
        pos_52w = round((current_price - low_52w) / (high_52w - low_52w) * 100, 0)

    # Universe rank labels
    in_top50  = rank <= TOP_50_LIMIT
    in_top100 = rank <= TOP_100_LIMIT

    return {
        "ticker":        ticker,
        "name":          name,
        "rank":          rank,
        "in_top50":      in_top50,
        "in_top100":     in_top100,
        "ex_date":       ex_date_str,
        "dividend":      dividend_val,
        "div_yield_pct": div_yield_pct,
        "days_to_ex":    days_to_ex,
        "buy_date":      buy_date_str,
        "sell_date":     sell_date_str,
        "current_price": current_price,
        "high_52w":      high_52w,
        "low_52w":       low_52w,
        "pos_52w":       pos_52w,
        "imoex":         imoex,
    }


def find_new_dividends(seen_keys):
    """
    Scan Top-100 for upcoming dividends not yet in seen_keys.
    seen_keys: set of "TICKER_EXDATE" strings already sent.
    Returns list of signal dicts.
    """
    today_str = date.today().strftime("%Y-%m-%d")
    imoex     = get_imoex_analysis()
    time.sleep(0.3)

    tickers = get_top_tickers(TOP_100_LIMIT)
    time.sleep(0.3)

    signals = []
    for rank, ticker in tickers:
        divs = get_dividends(ticker)
        time.sleep(0.3)

        for div in divs:
            ex_date_str  = div["ex_date"]
            dividend_val = div["dividend"]
            key          = f"{ticker}_{ex_date_str}"

            if key in seen_keys:
                continue
            if ex_date_str <= today_str:
                continue

            # Rough check: need at least MIN_DAYS_TO_EX trading days
            ex_dt    = date.fromisoformat(ex_date_str)
            cal_days = (ex_dt - date.today()).days
            if cal_days < MIN_DAYS_TO_EX:
                continue

            print(f"  [signals] new dividend: {ticker} ex={ex_date_str} div={dividend_val}")
            signal = build_signal(rank, ticker, ex_date_str, dividend_val, imoex)
            signals.append(signal)

    return signals
