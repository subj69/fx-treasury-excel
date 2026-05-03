from typing import Literal
from app.core.config import get_settings

PositionSide = Literal['BUY_FROM_CLIENT', 'SELL_TO_CLIENT']

class RiskService:
    """Проверки рисков и лимитов"""
    
    def __init__(self):
        # 🔥 Важно: получаем settings через функцию, а не импортируем напрямую
        settings = get_settings()
        self.limits = {
            "USD/RUB": settings.POSITION_LIMIT_USD,
            "EUR/RUB": settings.POSITION_LIMIT_EUR
        }
    
    def check_position_limit(self, pair: str, current_position: float, 
                            amount: float, side: PositionSide) -> dict:
        """Проверить, не превысит ли сделка лимит позиции"""
        delta = amount if side == 'BUY_FROM_CLIENT' else -amount
        new_position = current_position + delta
        limit = self.limits.get(pair, float('inf'))
        
        if abs(new_position) > limit:
            return {
                "ok": False,
                "message": f"Превышен лимит позиции {pair}: {abs(new_position):,.0f} > {limit:,.0f}",
                "new_position": new_position,
                "utilization_pct": round(abs(new_position) / limit * 100, 1) if limit else 0
            }
        
        utilization = abs(new_position) / limit * 100 if limit else 0
        if utilization > 80:
            return {
                "ok": True,
                "message": f"Внимание: позиция {pair} на {utilization:.1f}% от лимита",
                "new_position": new_position,
                "utilization_pct": round(utilization, 1),
                "warning": True
            }
        
        return {
            "ok": True,
            "message": "OK",
            "new_position": new_position,
            "utilization_pct": round(utilization, 1)
        }
    
    def validate_rfq(self, pair: str, amount: float, min_amount: float = 100, 
                    max_amount: float = 1_000_000) -> tuple[bool, str]:
        """Валидация параметров заявки"""
        if pair not in self.limits:
            return False, f"Неподдерживаемая валютная пара: {pair}"
        if not (min_amount <= amount <= max_amount):
            return False, f"Сумма вне допустимого диапазона: {min_amount} - {max_amount}"
        return True, "OK"