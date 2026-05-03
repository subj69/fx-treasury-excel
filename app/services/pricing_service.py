from app.core.config import get_settings

class PricingService:
    """Расчёт цен, спредов и P&L"""
    
    def __init__(self):
        self.settings = get_settings()
    
    def calculate_suggested_price(self, cbr_rate: float, side: str, spread_override: float = None) -> float:
        """Рассчитать рекомендуемую цену для клиента"""
        if spread_override is None:
            spread = self.settings.DEFAULT_SPREAD_BUY if side == 'BUY_FROM_CLIENT' else self.settings.DEFAULT_SPREAD_SELL
        else:
            spread = spread_override
        
        if side == 'BUY_FROM_CLIENT':
            # Банк покупает дешевле ЦБ
            return round(cbr_rate * (1 - spread), 4)
        else:
            # Банк продаёт дороже ЦБ
            return round(cbr_rate * (1 + spread), 4)
    
    @staticmethod
    def calculate_deal_pl(amount: float, price: float, cbr_rate: float, side: str) -> float:
        """Расчёт реализованной прибыли по сделке"""
        if cbr_rate == 0:
            return 0.0
        
        if side == 'BUY_FROM_CLIENT':
            pl = (cbr_rate - price) * amount
        else:
            pl = (price - cbr_rate) * amount
        
        return round(pl, 2)
    
    @staticmethod
    def calculate_unrealized_pl(position_amount: float, avg_entry_price: float, current_cbr_rate: float) -> float:
        """Расчёт нереализованной прибыли по открытой позиции"""
        if position_amount == 0 or current_cbr_rate == 0:
            return 0.0
        pl = position_amount * (current_cbr_rate - avg_entry_price)
        return round(pl, 2)