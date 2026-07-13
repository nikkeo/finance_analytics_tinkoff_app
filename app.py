from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
import requests as http_requests
from datetime import date, timedelta, datetime, timezone

app = Flask(__name__)
app.secret_key = 'finance-tracker-secret'
DB_PATH = '/Users/vlad/Desktop/dev/finance_app/finance.db'


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS balance_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                balance REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                type TEXT NOT NULL DEFAULT 'withdrawal',
                note TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # migrate existing DB if type column missing
        try:
            conn.execute("ALTER TABLE withdrawals ADD COLUMN type TEXT NOT NULL DEFAULT 'withdrawal'")
        except Exception:
            pass
        conn.commit()


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn



def calculate_daily_earnings():
    """
    Returns {date_str: daily_earnings} for all days covered by data.
    Earnings = (bal2 - bal1) + withdrawals - deposits, distributed evenly per day.
    Withdrawals are added back (taking money out isn't a loss).
    Deposits are subtracted (putting money in isn't a gain).
    """
    db = get_db()
    entries = db.execute(
        'SELECT date, balance FROM balance_entries ORDER BY date'
    ).fetchall()
    withdrawals_raw = db.execute(
        'SELECT date, amount, type FROM withdrawals ORDER BY date'
    ).fetchall()
    db.close()

    if len(entries) < 2:
        return {}

    # Build per-date adjustments: +withdrawal, -deposit
    adjustment_by_date = {}
    for w in withdrawals_raw:
        delta = w['amount'] if w['type'] == 'withdrawal' else -w['amount']
        adjustment_by_date[w['date']] = adjustment_by_date.get(w['date'], 0) + delta

    daily_earnings = {}

    for i in range(len(entries) - 1):
        d1_str = entries[i]['date']
        d2_str = entries[i + 1]['date']
        bal1 = entries[i]['balance']
        bal2 = entries[i + 1]['balance']

        d1 = datetime.strptime(d1_str, '%Y-%m-%d').date()
        d2 = datetime.strptime(d2_str, '%Y-%m-%d').date()
        days = (d2 - d1).days

        if days <= 0:
            continue

        # Include transactions on d1 and between d1..d2, exclude transactions on d2
        adj_sum = sum(
            delta for d_str, delta in adjustment_by_date.items()
            if d1_str <= d_str < d2_str
        )

        # Only count and assign earnings to trading days (Mon–Fri)
        trading_days = [
            (d1 + timedelta(days=j + 1))
            for j in range(days)
            if (d1 + timedelta(days=j + 1)).weekday() < 5
        ]

        if not trading_days:
            continue

        daily = ((bal2 - bal1) + adj_sum) / len(trading_days)

        for day in trading_days:
            daily_earnings[day.isoformat()] = daily

    return daily_earnings


def get_stats():
    daily = calculate_daily_earnings()
    today = date.today()
    TAX = 0.13

    week = sum(daily.get((today - timedelta(days=i)).isoformat(), 0) for i in range(7))
    month = sum(daily.get((today - timedelta(days=i)).isoformat(), 0) for i in range(30))
    total_earned = sum(daily.values())

    db = get_db()
    txs = db.execute('SELECT amount, type FROM withdrawals').fetchall()
    db.close()

    total_withdrawn = sum(t['amount'] for t in txs if t['type'] == 'withdrawal')
    total_deposited = sum(t['amount'] for t in txs if t['type'] == 'deposit')

    return {
        'week': week,
        'week_net': week * (1 - TAX),
        'month': month,
        'month_net': month * (1 - TAX),
        'total_earned': total_earned,
        'total_withdrawn': total_withdrawn,
        'total_deposited': total_deposited,
    }


def fmt(value):
    """Format number with spaces as thousands separator."""
    if value is None:
        return '0'
    return f'{value:,.2f}'.replace(',', ' ')


app.jinja_env.filters['fmt'] = fmt


@app.route('/')
def index():
    db = get_db()
    entries = db.execute(
        'SELECT * FROM balance_entries ORDER BY date DESC'
    ).fetchall()
    withdrawals = db.execute(
        'SELECT * FROM withdrawals ORDER BY date DESC, created_at DESC'
    ).fetchall()
    db.close()

    stats = get_stats()
    today = date.today().isoformat()
    has_data = len(entries) >= 2

    return render_template('index.html',
                           entries=entries,
                           withdrawals=withdrawals,
                           stats=stats,
                           today=today,
                           has_data=has_data)


@app.route('/update-balance', methods=['POST'])
def update_balance():
    entry_date = request.form.get('date', '').strip()
    balance_raw = request.form.get('balance', '').strip()

    if not entry_date or not balance_raw:
        flash('Заполните все поля', 'error')
        return redirect(url_for('index'))

    try:
        balance = float(balance_raw.replace(',', '.').replace(' ', ''))
    except ValueError:
        flash('Некорректная сумма', 'error')
        return redirect(url_for('index'))

    db = get_db()
    existing = db.execute(
        'SELECT id FROM balance_entries WHERE date = ?', (entry_date,)
    ).fetchone()

    if existing:
        db.execute('UPDATE balance_entries SET balance = ? WHERE date = ?', (balance, entry_date))
    else:
        db.execute('INSERT INTO balance_entries (date, balance) VALUES (?, ?)', (entry_date, balance))

    db.commit()
    db.close()

    flash(f'Баланс на {entry_date} сохранён: {fmt(balance)} ₽', 'success')
    return redirect(url_for('index'))


@app.route('/withdraw', methods=['POST'])
def withdraw():
    entry_date = request.form.get('date', '').strip()
    amount_raw = request.form.get('amount', '').strip()
    tx_type = request.form.get('type', 'withdrawal').strip()
    note = request.form.get('note', '').strip()

    if not entry_date or not amount_raw:
        flash('Заполните все поля', 'error')
        return redirect(url_for('index'))

    if tx_type not in ('withdrawal', 'deposit'):
        tx_type = 'withdrawal'

    try:
        amount = float(amount_raw.replace(',', '.').replace(' ', ''))
    except ValueError:
        flash('Некорректная сумма', 'error')
        return redirect(url_for('index'))

    db = get_db()
    db.execute(
        'INSERT INTO withdrawals (date, amount, type, note) VALUES (?, ?, ?, ?)',
        (entry_date, amount, tx_type, note)
    )
    db.commit()
    db.close()

    label = 'Снятие' if tx_type == 'withdrawal' else 'Пополнение'
    flash(f'{label} {fmt(amount)} ₽ записано', 'success')
    return redirect(url_for('index'))


@app.route('/delete-entry/<int:entry_id>', methods=['POST'])
def delete_entry(entry_id):
    db = get_db()
    db.execute('DELETE FROM balance_entries WHERE id = ?', (entry_id,))
    db.commit()
    db.close()
    return redirect(url_for('index'))


@app.route('/delete-withdrawal/<int:w_id>', methods=['POST'])
def delete_withdrawal(w_id):
    db = get_db()
    db.execute('DELETE FROM withdrawals WHERE id = ?', (w_id,))
    db.commit()
    db.close()
    return redirect(url_for('index'))


@app.route('/chart-data')
def chart_data():
    daily = calculate_daily_earnings()
    today = date.today()

    labels = []
    values = []
    cumulative = []
    running = 0

    types = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        d_str = d.isoformat()
        val = round(daily.get(d_str, 0), 2)
        running += val
        labels.append(d_str[5:])  # MM-DD
        values.append(val)
        cumulative.append(round(running, 2))
        types.append('weekend' if d.weekday() >= 5 else 'weekday')

    return jsonify({'labels': labels, 'values': values, 'cumulative': cumulative, 'types': types})


TINKOFF_BASE = 'https://invest-public-api.tinkoff.ru/rest'


def t_request(path, body, token):
    r = http_requests.post(
        f'{TINKOFF_BASE}{path}',
        json=body,
        headers={'Authorization': f'Bearer {token}'},
        timeout=10
    )
    r.raise_for_status()
    return r.json()


def money_value(mv):
    """Convert T-Invest MoneyValue {units, nano} to float."""
    return float(mv.get('units', 0)) + mv.get('nano', 0) / 1e9


@app.route('/tinkoff-accounts')
def tinkoff_accounts():
    try:
        from config import T_INVEST_TOKEN
    except ImportError:
        return jsonify({'error': 'config.py не найден'}), 400

    if not T_INVEST_TOKEN:
        return jsonify({'error': 'Токен не указан в config.py'}), 400

    try:
        resp = t_request(
            '/tinkoff.public.invest.api.contract.v1.UsersService/GetAccounts',
            {}, T_INVEST_TOKEN
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    accounts = [
        {'id': a['id'], 'name': a.get('name') or a['id']}
        for a in resp.get('accounts', [])
    ]
    return jsonify({'accounts': accounts})


@app.route('/sync-tinkoff', methods=['POST'])
def sync_tinkoff():
    try:
        from config import T_INVEST_TOKEN, T_INVEST_ACCOUNT_ID
    except ImportError:
        return jsonify({'error': 'config.py не найден'}), 400

    if not T_INVEST_TOKEN:
        return jsonify({'error': 'Токен не указан в config.py'}), 400

    if not T_INVEST_ACCOUNT_ID:
        return jsonify({'error': 'ID счёта не указан в config.py'}), 400

    try:
        # Текущий баланс портфеля
        portfolio = t_request(
            '/tinkoff.public.invest.api.contract.v1.OperationsService/GetPortfolio',
            {'accountId': T_INVEST_ACCOUNT_ID, 'currency': 'RUB'},
            T_INVEST_TOKEN
        )
        total = money_value(portfolio['totalAmountPortfolio'])
        today_str = date.today().isoformat()

        db = get_db()

        # Сохранить баланс
        existing = db.execute(
            'SELECT id FROM balance_entries WHERE date = ?', (today_str,)
        ).fetchone()
        if existing:
            db.execute('UPDATE balance_entries SET balance = ? WHERE date = ?', (total, today_str))
        else:
            db.execute('INSERT INTO balance_entries (date, balance) VALUES (?, ?)', (today_str, total))

        # Операции за последние 90 дней
        from_dt = (datetime.now(timezone.utc) - timedelta(days=90)).strftime('%Y-%m-%dT%H:%M:%SZ')
        to_dt = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        ops_resp = t_request(
            '/tinkoff.public.invest.api.contract.v1.OperationsService/GetOperations',
            {
                'accountId': T_INVEST_ACCOUNT_ID,
                'from': from_dt,
                'to': to_dt,
                'state': 'OPERATION_STATE_EXECUTED',
            },
            T_INVEST_TOKEN
        )

        new_ops = 0
        for op in ops_resp.get('operations', []):
            op_type = op.get('operationType', '')
            if op_type not in ('OPERATION_TYPE_INPUT', 'OPERATION_TYPE_OUTPUT'):
                continue

            op_id = op['id']
            already = db.execute(
                "SELECT id FROM withdrawals WHERE note LIKE ?", (f'%[t:{op_id}]%',)
            ).fetchone()
            if already:
                continue

            amount = abs(money_value(op.get('payment', {})))
            tx_type = 'deposit' if op_type == 'OPERATION_TYPE_INPUT' else 'withdrawal'
            op_date = op['date'][:10]

            db.execute(
                'INSERT INTO withdrawals (date, amount, type, note) VALUES (?, ?, ?, ?)',
                (op_date, amount, tx_type, f'T-Invest [t:{op_id}]')
            )
            new_ops += 1

        db.commit()
        db.close()

        return jsonify({
            'success': True,
            'balance': round(total, 2),
            'date': today_str,
            'new_operations': new_ops,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)
