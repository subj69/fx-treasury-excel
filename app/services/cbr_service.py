import httpx
from datetime import datetime, timedelta
from app.core.config import get_settings
from app.core.currency_pairs import get_all_pair_symbols, SUPPORTED_PAIRS

class CBRService:
    """Сервис для работы с курсами ЦБ РФ с кэшированием"""
    
    def __init__(self):
        self.settings = get_settings()
        # 🔥 Динамическая инициализация кэша на основе конфигурации валютных пар
        self._cache: dict[str, dict] = {}
        for pair, config in SUPPORTED_PAIRS.items():
            symbol = config.get("symbol", pair.split("/")[0])
            # Начальное значение (фолбэк) - можно загрузить из конфига при необходимости
            default_rate = 75.0 if symbol == "USD" else (80.0 if symbol == "EUR" else 13.0)
            self._cache[pair] = {"rate": default_rate, "updated": None}
    
    async def get_rate(self, currency: str) -> float | None:
        """Получить курс с кэшированием"""
        key = f"{currency}/RUB"
        cached = self._cache.get(key)
        
        # Проверка TTL кэша
        if cached and cached["updated"]:
            age = datetime.now() - cached["updated"]
            if age.total_seconds() < self.settings.CBR_CACHE_TTL_SECONDS:
                return cached["rate"]
        
        # Попытка получить свежий курс
        rate = await self._fetch_from_api(currency)
        
        if rate:
            self._cache[key] = {"rate": rate, "updated": datetime.now()}
            return rate
        
        # Фолбэк на кэшированное значение
        if cached and cached["rate"]:
            return cached["rate"]
        
        return None
    
    async def _fetch_from_api(self, currency: str) -> float | None:
        """Парсинг API cbr-xml-daily.ru"""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(self.settings.CBR_API_URL)
                resp.raise_for_status()
                data = resp.json()
                return float(data["Valute"][currency]["Value"])
        except Exception:
            return None
    
    async def get_all_rates(self) -> dict[str, float]:
        """Вернуть все кэшированные курсы"""
        return {key: val["rate"] for key, val in self._cache.items()}
    
    async def refresh_all_rates(self):
        """🔥 Обновить все курсы из API ЦБ для всех поддерживаемых валютных пар"""
        for pair, config in SUPPORTED_PAIRS.items():
            symbol = config.get("symbol", pair.split("/")[0])
            await self.get_rate(symbol)