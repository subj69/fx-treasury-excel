from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
from datetime import datetime

class RFQRequest(BaseModel):
    pair: Literal["USD/RUB", "EUR/RUB"]
    amount: float = Field(gt=0, le=1_000_000)
    side: Literal["BUY_FROM_CLIENT", "SELL_TO_CLIENT"]
    rfq_id: Optional[str] = None
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        if v < 100:
            raise ValueError('Минимальная сумма: 100')
        return round(v, 2)

class QuoteResponse(BaseModel):
    price: float = Field(gt=0)
    rfq_id: str
    valid_until: datetime

class DealAccept(BaseModel):
    rfq_id: str
    pair: str
    amount: float
    price: float
    side: str