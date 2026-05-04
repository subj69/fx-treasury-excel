import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.services.cbr_service import CBRService
from app.core.currency_pairs import SUPPORTED_PAIRS

class StateService:
    def __init__(self, db_path: str = "app/data/treasury.db"):
        self.db_path = db_path
        self.cbr_service = CBRService()
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                currency_pair TEXT NOT NULL,
                deal_type TEXT NOT NULL,
                amount REAL NOT NULL,
                rate REAL NOT NULL,
                cbr_rate REAL NOT NULL,
                pl REAL NOT NULL,
                client_name TEXT DEFAULT 'Неизвестный клиент'
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_deals_timestamp ON deals(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_deals_pair ON deals(currency_pair)")
        
        conn.commit()
        conn.close()

    async def recalculate_positions(self) -> Dict[str, Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        positions = {}
        for pair in SUPPORTED_PAIRS:
            positions[pair] = {"amount": 0.0, "avg_entry_price": 0.0}
            
        cursor.execute("SELECT currency_pair, deal_type, amount, rate FROM deals ORDER BY timestamp")
        deals = cursor.fetchall()
        
        for pair, deal_type, amount, rate in deals:
            if pair not in positions:
                positions[pair] = {"amount": 0.0, "avg_entry_price": 0.0}
                
            if deal_type == "ПОКУПКА":
                old_amount = positions[pair]["amount"]
                old_avg = positions[pair]["avg_entry_price"]
                new_amount = old_amount + amount
                if new_amount != 0:
                    positions[pair]["avg_entry_price"] = ((old_amount * old_avg) + (amount * rate)) / new_amount
                positions[pair]["amount"] = new_amount
            else:  # ПРОДАЖА
                positions[pair]["amount"] -= amount
                
        conn.close()
        return positions

    def save_deal(self, pair: str, deal_type: str, amount: float, rate: float, cbr_rate: float, client_name: str = "Неизвестный клиент") -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        pl = self._calculate_pl(pair, deal_type, amount, rate, cbr_rate)
        timestamp = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
        
        cursor.execute("""
            INSERT INTO deals (timestamp, currency_pair, deal_type, amount, rate, cbr_rate, pl, client_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (timestamp, pair, deal_type, amount, rate, cbr_rate, pl, client_name))
        
        deal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return deal_id

    def get_deal_history(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, timestamp, currency_pair, deal_type, amount, rate, cbr_rate, pl, client_name
            FROM deals 
            ORDER BY timestamp DESC
        """)
        
        deals = []
        for row in cursor.fetchall():
            ts_parts = row['timestamp'].split(' ')
            date_part = ts_parts[0] if len(ts_parts) > 0 else ""
            time_part = ts_parts[1] if len(ts_parts) > 1 else ""
            
            deals.append({
                "id": row['id'],
                "date": date_part,
                "time": time_part,
                "pair": row['currency_pair'],
                "type": row['deal_type'],
                "client_name": row['client_name'] or "Неизвестный клиент",
                "amount": row['amount'],
                "rate": row['rate'],
                "cbr_rate": row['cbr_rate'],
                "pl": row['pl']
            })
            
        conn.close()
        return deals

    def _calculate_pl(self, pair: str, deal_type: str, amount: float, rate: float, cbr_rate: float) -> float:
        if deal_type == "ПОКУПКА":
            return (cbr_rate - rate) * amount
        else:
            return (rate - cbr_rate) * amount
