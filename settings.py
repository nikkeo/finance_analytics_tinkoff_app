"""
Runtime settings for Finance Tracker.

Everything here has a working default, so проект запускается сразу после клона.
Любое значение переопределяется переменной окружения — секреты и пути
не нужно править в коде.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Путь к базе. По умолчанию — finance.db рядом с проектом.
# Своя база: FINANCE_DB_PATH=/path/to/finance.db
DB_PATH = os.environ.get('FINANCE_DB_PATH') or os.path.join(BASE_DIR, 'finance.db')

# Ключ сессии Flask. Для локального запуска дефолта достаточно,
# при выкладывании наружу задайте FINANCE_SECRET_KEY.
SECRET_KEY = os.environ.get('FINANCE_SECRET_KEY', 'dev-only-insecure-key')

# Режим отладки. Включён по умолчанию для локальной разработки,
# выключается через FINANCE_DEBUG=0.
DEBUG = os.environ.get('FINANCE_DEBUG', '1').lower() not in ('0', 'false', 'no', '')

PORT = int(os.environ.get('FINANCE_PORT', '5001'))
