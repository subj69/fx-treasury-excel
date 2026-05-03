import pytest
from app.services.pricing_service import PricingService

@pytest.fixture
def pricing():
    return PricingService()

def test_suggested_price_buy_from_client(pricing):
    """Банк покупает у клиента → цена ниже ЦБ"""
    cbr = 75.0
    suggested = pricing.calculate_suggested_price(cbr, 'BUY_FROM_CLIENT')
    assert suggested < cbr
    assert suggested == pytest.approx(74.625, rel=1e-3)  # 75 * 0.995

def test_suggested_price_sell_to_client(pricing):
    """Банк продаёт клиенту → цена выше ЦБ"""
    cbr = 75.0
    suggested = pricing.calculate_suggested_price(cbr, 'SELL_TO_CLIENT')
    assert suggested > cbr
    assert suggested == pytest.approx(75.375, rel=1e-3)  # 75 * 1.005

def test_deal_pl_buy_profit(pricing):
    """Купили дешевле ЦБ → прибыль"""
    pl = pricing.calculate_deal_pl(amount=1000, price=74, cbr_rate=75, side='BUY_FROM_CLIENT')
    assert pl == 1000.0  # (75-74)*1000

def test_deal_pl_sell_profit(pricing):
    """Продали дороже ЦБ → прибыль"""
    pl = pricing.calculate_deal_pl(amount=1000, price=76, cbr_rate=75, side='SELL_TO_CLIENT')
    assert pl == 1000.0  # (76-75)*1000

def test_unrealized_pl_long_position(pricing):
    """Длинная позиция: курс вырос → нереализованная прибыль"""
    pl = pricing.calculate_unrealized_pl(
        position_amount=1000, 
        avg_entry_price=74, 
        current_cbr_rate=75
    )
    assert pl == 1000.0