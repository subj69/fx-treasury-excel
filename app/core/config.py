from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # === Безопасность ===
    TREASURY_USERNAME: str = "treasury"
    TREASURY_PASSWORD: str = "change_me_in_production"
    
    # === Курсы ЦБ ===
    CBR_API_URL: str = "https://www.cbr-xml-daily.ru/daily_json.js"
    CBR_CACHE_TTL_SECONDS: int = 300
    
    # === Лимиты позиций ===
    POSITION_LIMIT_USD: float = 100_000
    POSITION_LIMIT_EUR: float = 100_000
    
    # === Спреды ===
    DEFAULT_SPREAD_BUY: float = 0.005
    DEFAULT_SPREAD_SELL: float = 0.005
    
    # === База данных ===
    DATABASE_PATH: str = "fx_deals.db"
    
    # === Логирование ===
    LOG_LEVEL: str = "INFO"
    
    # 🔥 Ключевая настройка для Pydantic v2:
    # - env_file: загружать переменные из .env
    # - extra: ignore: игнорировать неизвестные поля (чтобы host/port не ломали)
    model_config = {
        "env_file": ".env",
        "extra": "ignore",
        "case_sensitive": False  # HOST и host — одно и то же
    }

@lru_cache()
def get_settings() -> Settings:
    return Settings()
