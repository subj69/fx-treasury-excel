import aiosqlite
from datetime import datetime
from app.core.config import get_settings

class StateService:
    def __init__(self):
        self.settings = get_settings()
        self.positions: dict[str, dict] = {
            "USD/RUB": {"amount": 0.0, "avg_entry_price": 0.0},
            "EUR/RUB": {"amount": 0.0, "avg_entry_price": 0.0}
        }
    
    async def init_db(self):
        async with aiosqlite.connect(self.settings.DATABASE_PATH) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS deals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    pair TEXT NOT NULL,
                    amount REAL NOT NULL,
                    price REAL NOT NULL,
                    side TEXT NOT NULL,
                    cbr_rate REAL NOT NULL,
                    realized_pl REAL DEFAULT 0
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS positions (
                    pair TEXT UNIQUE NOT NULL,
                    amount REAL NOT NULL DEFAULT 0,
                    avg_entry_price REAL NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
            ''')
            await db.commit()
            print("✅ Database tables checked")

    async def recalculate_positions_from_history(self):
        """
        🔥 НАДЕЖНЫЙ МЕТОД: Пересчитывает позицию по всем сделкам в БД.
        Это гарантирует, что позиция будет верной даже после сбоя.
        """
        print("🔄 Recalculating positions from deal history...")
        
        # Сбрасываем текущие позиции в 0 перед расчетом
        for pair in self.positions:
            self.positions[pair]["amount"] = 0.0
            self.positions[pair]["avg_entry_price"] = 0.0

        async with aiosqlite.connect(self.settings.DATABASE_PATH) as db:
            # Берем все сделки
            async with db.execute("SELECT pair, amount, side, price FROM deals") as cursor:
                async for row in cursor:
                    pair, amount, side, price = row
                    
                    if side == 'BUY_FROM_CLIENT':
                        # Банк покупает -> Позиция растет (+)
                        current_amt = self.positions[pair]["amount"]
                        current_price = self.positions[pair]["avg_entry_price"]
                        
                        new_amt = current_amt + amount
                        # Пересчет средней цены входа
                        if new_amt != 0:
                            total_val = (current_price * current_amt) + (price * amount)
                            self.positions[pair]["avg_entry_price"] = total_val / new_amt
                        
                        self.positions[pair]["amount"] = new_amt
                        
                    elif side == 'SELL_TO_CLIENT':
                        # Банк продает -> Позиция падает (-)
                        self.positions[pair]["amount"] -= amount
        
        # Сохраняем пересчитанное состояние в таблицу positions
        await self.save_positions_to_db()
        print(f"✅ Positions recalculated: {self.positions}")

    async def save_positions_to_db(self):
        try:
            async with aiosqlite.connect(self.settings.DATABASE_PATH) as db:
                for pair, data in self.positions.items():
                    await db.execute('''
                        INSERT OR REPLACE INTO positions (pair, amount, avg_entry_price, updated_at)
                        VALUES (?, ?, ?, ?)
                    ''', (pair, data["amount"], data["avg_entry_price"], datetime.now().isoformat()))
                await db.commit()
        except Exception as e:
            print(f"❌ Error saving positions: {e}")

    def update_position(self, pair: str, amount: float, side: str, price: float):
        current = self.positions[pair]
        if side == 'BUY_FROM_CLIENT':
            new_amount = current["amount"] + amount
            if new_amount != 0:
                total_value = (current["avg_entry_price"] * current["amount"]) + (price * amount)
                current["avg_entry_price"] = total_value / new_amount
        else:
            new_amount = current["amount"] - amount
        current["amount"] = new_amount

    async def save_deal(self, pair: str, amount: float, price: float, 
                       side: str, cbr_rate: float, pl: float):
        async with aiosqlite.connect(self.settings.DATABASE_PATH) as db:
            await db.execute('''
                INSERT INTO deals (timestamp, pair, amount, price, side, cbr_rate, realized_pl)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (datetime.now().isoformat(), pair, amount, price, side, cbr_rate, pl))
            await db.commit()

    async def get_deal_history(self, limit: int = 50):
        async with aiosqlite.connect(self.settings.DATABASE_PATH) as db:
            async with db.execute("SELECT * FROM deals ORDER BY id DESC LIMIT ?", (limit,)) as cursor:
                rows = await cursor.fetchall()
                cols = [d[0] for d in cursor.description]
                return [dict(zip(cols, row)) for row in rows]