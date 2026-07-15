"""
Database performance optimizations: WAL mode, indexes, connection pooling.
"""
import aiosqlite
from pathlib import Path
from utils.logger import setup_logger

logger = setup_logger(__name__)

async def optimize_db(db_path: str) -> None:
    """Apply all optimizations to an existing SQLite database."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA synchronous=NORMAL;")
        await db.execute("PRAGMA cache_size=-20000;")  # 20MB cache
        await db.execute("PRAGMA temp_store=MEMORY;")
        await db.execute("PRAGMA mmap_size=268435456;")  # 256MB

        # Create indexes for common queries
        await db.executescript("""
            CREATE INDEX IF NOT EXISTS idx_trades_symbol_ts ON trades(symbol, ts);
            CREATE INDEX IF NOT EXISTS idx_executions_symbol_ts ON executions(symbol, ts);
            CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
            CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id);
            CREATE INDEX IF NOT EXISTS idx_latency_logs_symbol ON latency_logs(symbol);
            CREATE INDEX IF NOT EXISTS idx_account_snapshots_ts ON account_snapshots(ts);
        """)
        await db.commit()
        logger.info("Database optimizations applied")

# Simple connection pool for aiosqlite (single connection suffices for most uses)
class ConnectionPool:
    def __init__(self, db_path: str, pool_size: int = 1):
        self.db_path = db_path
        self.pool_size = pool_size
        self._pool = asyncio.Queue()

    async def init(self):
        for _ in range(self.pool_size):
            conn = await aiosqlite.connect(self.db_path)
            await conn.execute("PRAGMA journal_mode=WAL;")
            self._pool.put_nowait(conn)

    async def acquire(self):
        return await self._pool.get()

    async def release(self, conn):
        self._pool.put_nowait(conn)

    async def close(self):
        while not self._pool.empty():
            conn = self._pool.get_nowait()
            await conn.close()