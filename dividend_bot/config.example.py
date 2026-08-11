"""
Шаблон конфига Dividend Bot.

Скопируйте в config.py и подставьте свои значения:
    cp config.example.py config.py

Без config.py бот не запустится — токен и chat_id обязательны.
"""

# Токен бота от @BotFather.
TELEGRAM_TOKEN = ''

# Куда слать сигналы: свой chat_id (можно узнать у @userinfobot)
# или id канала/группы вида -1001234567890.
TELEGRAM_CHAT_ID = ''

# MOEX ISS API — публичный, авторизация не нужна.
MOEX_BASE = 'https://iss.moex.com/iss'

# ── Параметры стратегии T-7 → T-1 ────────────────────────────────────────────
BUY_DAYS_BEFORE = 7     # вход за N торговых дней до отсечки
SELL_DAYS_BEFORE = 1    # выход за N торговых дней до отсечки
MIN_DAYS_TO_EX = 7      # пропускать отсечки, до которых осталось меньше N дней

# Размер вселенной сканирования: топ-N акций MOEX по капитализации.
TOP_50_LIMIT = 50
TOP_100_LIMIT = 100
