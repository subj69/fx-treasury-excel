"""
Конфигурация валютных пар для FX Treasury System.
Все поддерживаемые валютные пары и их настройки вынесены в этот файл.
"""

from typing import TypedDict
from functools import lru_cache


class CurrencyPairConfig(TypedDict, total=False):
    """Конфигурация валютной пары"""
    symbol: str           # Код валюты для API ЦБ (например, "USD", "EUR", "CNY")
    name: str             # Отображаемое имя
    default_limit: float  # Лимит позиции по умолчанию
    min_amount: float     # Минимальная сумма сделки
    max_amount: float     # Максимальная сумма сделки
    spread_buy: float     # Спред для покупки (по умолчанию)
    spread_sell: float    # Спред для продажи (по умолчанию)


# 🔥 СПИСОК ВСЕХ ВАЛЮТНЫХ ПАР
# Добавляйте новые пары сюда, а не в код сервисов
SUPPORTED_PAIRS: dict[str, CurrencyPairConfig] = {
    "USD/RUB": {
        "symbol": "USD",
        "name": "Доллар США",
        "default_limit": 100_000,
        "min_amount": 100,
        "max_amount": 1_000_000,
        "spread_buy": 0.005,
        "spread_sell": 0.005,
    },
    "EUR/RUB": {
        "symbol": "EUR",
        "name": "Евро",
        "default_limit": 100_000,
        "min_amount": 100,
        "max_amount": 1_000_000,
        "spread_buy": 0.005,
        "spread_sell": 0.005,
    },
    # ✅ Новая валютная пара CNY/RUB
    "CNY/RUB": {
        "symbol": "CNY",
        "name": "Китайский юань",
        "default_limit": 1_000_000,  # Юаней больше из-за меньшего курса
        "min_amount": 1000,
        "max_amount": 10_000_000,
        "spread_buy": 0.008,  # Чуть больший спред для менее ликвидной валюты
        "spread_sell": 0.008,
    },
    # ✅ Новая валютная пара RSD/RUB
    "RSD/RUB": {
        "symbol": "RSD",
        "name": "Сербский Динар",
        "default_limit": 1_000_000,  # Юаней больше из-за меньшего курса
        "min_amount": 1000,
        "max_amount": 10_000_000,
        "spread_buy": 0.008,  # Чуть больший спред для менее ликвидной валюты
        "spread_sell": 0.008,
    },
    # ✅ Новая валютная пара TRY/RUB
    "TRY/RUB": {
        "symbol": "TRY",
        "name": "Турецкая лира",
        "default_limit": 1_000_000,  # Юаней больше из-за меньшего курса
        "min_amount": 1000,
        "max_amount": 10_000_000,
        "spread_buy": 0.008,  # Чуть больший спред для менее ликвидной валюты
        "spread_sell": 0.008,
    },
}


@lru_cache(maxsize=1)
def get_all_pairs() -> list[str]:
    """Вернуть список всех поддерживаемых валютных пар"""
    return list(SUPPORTED_PAIRS.keys())


@lru_cache(maxsize=1)
def get_all_pair_symbols() -> list[str]:
    """Вернуть список символов валют для API ЦБ"""
    return [config["symbol"] for config in SUPPORTED_PAIRS.values()]


def get_pair_config(pair: str) -> CurrencyPairConfig | None:
    """Получить конфигурацию конкретной валютной пары"""
    return SUPPORTED_PAIRS.get(pair)


def get_pair_symbol(pair: str) -> str | None:
    """Получить символ валюты для API ЦБ (например, 'USD' из 'USD/RUB')"""
    config = SUPPORTED_PAIRS.get(pair)
    return config["symbol"] if config else None


def get_pair_limit(pair: str) -> float:
    """Получить лимит позиции для валютной пары"""
    config = SUPPORTED_PAIRS.get(pair)
    return config["default_limit"] if config else float("inf")


def is_supported_pair(pair: str) -> bool:
    """Проверить, поддерживается ли валютная пара"""
    return pair in SUPPORTED_PAIRS
