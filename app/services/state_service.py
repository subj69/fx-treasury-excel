import aiosqlite
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import asyncio
from app.core.config import get_settings
from app.core.currency_pairs import SUPPORTED_PAIRS

class StateService:
    def __init__(self):
        self.settings = get_settings()
        # 🔥 Динамическая инициализация позиций на основе конфигурации валютных пар
        self.positions: dict[str, dict] = {}
        for pair in SUPPORTED_PAIRS.keys():
            self.positions[pair] = {"amount": 0.0, "avg_entry_price": 0.0}
        self._db_pool: Optional[aiosqlite.Connection] = None
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._lock = asyncio.Lock()
    
    @asynccontextmanager
    async def get_connection(self):
        """Пул соединений для эффективной работы с БД"""
        conn = await aiosqlite.connect(
            self.settings.DATABASE_PATH,
            timeout=30.0
        )
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()
    
    async def init_db(self):
        async with self.get_connection() as db:
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
            # 🔥 Индексы для ускорения запросов
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_deals_pair ON deals(pair)
            ''')
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_deals_timestamp ON deals(timestamp DESC)
            ''')
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_deals_side ON deals(side)
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
            print("✅ Database tables and indexes created")

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

        async with self.get_connection() as db:
            # 🔥 Batch fetch всех сделок для эффективности
            async with db.execute(
                "SELECT pair, amount, side, price FROM deals ORDER BY id"
            ) as cursor:
                rows = await cursor.fetchall()
                
                # Обрабатываем в памяти - быстрее чем много отдельных запросов
                for row in rows:
                    pair, amount, side, price = row
                    
                    try:
                        if side == 'BUY_FROM_CLIENT':
                            current_amt = self.positions[pair]["amount"]
                            current_price = self.positions[pair]["avg_entry_price"]
                            
                            new_amt = current_amt + amount
                            if new_amt != 0:
                                total_val = (current_price * current_amt) + (price * amount)
                                self.positions[pair]["avg_entry_price"] = total_val / new_amt
                            
                            self.positions[pair]["amount"] = new_amt
                            
                        elif side == 'SELL_TO_CLIENT':
                            self.positions[pair]["amount"] -= amount
                            
                    except KeyError:
                        # Пара не найдена в конфигурации - пропускаем с предупреждением
                        print(f"⚠️  Warning: Unknown currency pair '{pair}' in deal history. Skipping...")
                        continue
        
        # Сохраняем пересчитанное состояние в таблицу positions
        await self.save_positions_to_db()
        print(f"✅ Positions recalculated: {self.positions}")

    async def save_positions_to_db(self):
        try:
            async with self.get_connection() as db:
                # 🔥 Batch insert для всех позиций
                positions_data = [
                    (pair, data["amount"], data["avg_entry_price"], datetime.now().isoformat())
                    for pair, data in self.positions.items()
                ]
                await db.executemany('''
                    INSERT OR REPLACE INTO positions (pair, amount, avg_entry_price, updated_at)
                    VALUES (?, ?, ?, ?)
                ''', positions_data)
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
        async with self.get_connection() as db:
            await db.execute('''
                INSERT INTO deals (timestamp, pair, amount, price, side, cbr_rate, realized_pl)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (datetime.now().isoformat(), pair, amount, price, side, cbr_rate, pl))
            await db.commit()

    async def get_deal_history(self, limit: int = 50):
        async with self.get_connection() as db:
            async with db.execute(
                "SELECT * FROM deals ORDER BY id DESC LIMIT ?", 
                (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_all_deals_batch(self, offset: int = 0, batch_size: int = 1000):
        """
        🔥 Пагинация для экспорта больших объемов данных
        Возвращает порцию сделок для эффективной работы с памятью
        """
        async with self.get_connection() as db:
            async with db.execute(
                "SELECT * FROM deals ORDER BY id LIMIT ? OFFSET ?",
                (batch_size, offset)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def count_deals(self) -> int:
        """🔥 Быстрый подсчет количества сделок"""
        async with self.get_connection() as db:
            async with db.execute("SELECT COUNT(*) FROM deals") as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 0
    
    async def cleanup(self):
        """Очистка ресурсов при завершении"""
        if self._executor:
            self._executor.shutdown(wait=False)