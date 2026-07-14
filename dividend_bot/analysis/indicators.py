from datetime import date, timedelta
from data.moex import get_imoex_candles


def get_imoex_analysis():
    """
    Returns current IMOEX price, MA50, MA200 and trend signals.
    """
    today    = date.today().strftime("%Y-%m-%d")
    from_date = (date.today() - timedelta(days=300)).strftime("%Y-%m-%d")

    prices = get_imoex_candles(from_date, today)
    if not prices:
        return None

    dates  = sorted(prices.keys())
    closes = [prices[d] for d in dates]

    current = closes[-1]
    current_date = dates[-1]

    ma50  = sum(closes[-50:])  / min(50,  len(closes)) if len(closes) >= 10 else None
    ma200 = sum(closes[-200:]) / min(200, len(closes)) if len(closes) >= 10 else None

    return {
        "date":         current_date,
        "price":        round(current, 1),
        "ma50":         round(ma50,  1) if ma50  else None,
        "ma200":        round(ma200, 1) if ma200 else None,
        "above_ma50":   current > ma50  if ma50  else None,
        "above_ma200":  current > ma200 if ma200 else None,
    }


def trading_days_between(start_str, end_str, prices_dates):
    """Count trading days between two date strings (exclusive start, inclusive end)."""
    return sum(1 for d in prices_dates if start_str < d <= end_str)


def nth_trading_day_before(target_str, n, prices_dates):
    """Return date string that is N trading days before target_str."""
    dates_sorted = sorted(prices_dates)
    idx = next((i for i, d in enumerate(dates_sorted) if d >= target_str), None)
    if idx is None or idx < n:
        return None
    return dates_sorted[idx - n]
