import sqlite3
import requests
from datetime import datetime, timezone, timedelta

from config import T_INVEST_TOKEN, T_INVEST_ACCOUNT_ID

DB_PATH = '/Users/vlad/Desktop/dev/finance_app/finance.db'
BASE = 'https://invest-public-api.tinkoff.ru/rest'


def t_request(path, body):
    r = requests.post(
        f'{BASE}{path}',
        json=body,
        headers={'Authorization': f'Bearer {T_INVEST_TOKEN}'},
        timeout=15
    )
    r.raise_for_status()
    return r.json()


def money_value(mv):
    return float(mv.get('units', 0)) + mv.get('nano', 0) / 1e9


conn = sqlite3.connect(DB_PATH, timeout=10)
conn.execute('PRAGMA journal_mode=WAL')

from_dt = (datetime.now(timezone.utc) - timedelta(days=365)).strftime('%Y-%m-%dT%H:%M:%SZ')
to_dt = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

print(f'Загружаю операции с {from_dt[:10]} по {to_dt[:10]}...')

resp = t_request(
    '/tinkoff.public.invest.api.contract.v1.OperationsService/GetOperations',
    {
        'accountId': T_INVEST_ACCOUNT_ID,
        'from': from_dt,
        'to': to_dt,
        'state': 'OPERATION_STATE_EXECUTED',
    }
)

operations = resp.get('operations', [])
print(f'Получено операций: {len(operations)}')

added = 0
skipped = 0

for op in operations:
    op_type = op.get('operationType', '')
    if op_type not in ('OPERATION_TYPE_INPUT', 'OPERATION_TYPE_OUTPUT'):
        continue

    op_id = op['id']
    already = conn.execute(
        "SELECT id FROM withdrawals WHERE note LIKE ?", (f'%[t:{op_id}]%',)
    ).fetchone()
    if already:
        skipped += 1
        continue

    amount = abs(money_value(op.get('payment', {})))
    tx_type = 'deposit' if op_type == 'OPERATION_TYPE_INPUT' else 'withdrawal'
    op_date = op['date'][:10]

    conn.execute(
        'INSERT INTO withdrawals (date, amount, type, note) VALUES (?, ?, ?, ?)',
        (op_date, amount, tx_type, f'T-Invest [t:{op_id}]')
    )
    added += 1
    print(f'  {op_date} | {tx_type:10} | {amount:>12.2f} ₽')

conn.commit()
conn.close()

print(f'\nГотово. Добавлено: {added}, пропущено (уже есть): {skipped}')
