import aiosqlite
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, date
from utils.logger import setup_logger
from optimization.db_optimizer import optimize_db

logger = setup_logger(__name__)

async def init_db(db_path: str = "trading_terminal.db") -> None:
    """Create the database and all required tables if they don't exist."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(str(db_path)) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                qty REAL,
                price REAL,
                order_id TEXT,
                success BOOLEAN,
                latency_submit_ms REAL,
                latency_ack_ms REAL
            );

            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT,
                qty REAL,
                entry_price REAL,
                mark_price REAL,
                unrealized_pnl REAL,
                leverage INTEGER,
                liquidation_price REAL,
                margin REAL,
                notional REAL,
                roe REAL,
                break_even_price REAL,
                margin_ratio REAL,
                funding_rate REAL,
                funding_fee REAL,
                liquidation_distance_pct REAL
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                order_id TEXT UNIQUE,
                symbol TEXT NOT NULL,
                type TEXT,
                side TEXT,
                price REAL,
                amount REAL,
                filled REAL,
                remaining REAL,
                status TEXT,
                reduce_only BOOLEAN,
                client_order_id TEXT
            );

            CREATE TABLE IF NOT EXISTS executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                order_id TEXT,
                symbol TEXT NOT NULL,
                side TEXT,
                price REAL,
                qty REAL,
                commission REAL,
                commission_asset TEXT,
                exec_type TEXT
            );

            CREATE TABLE IF NOT EXISTS latency_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                symbol TEXT,
                action TEXT,
                latency_ms REAL,
                details TEXT
            );

            CREATE TABLE IF NOT EXISTS account_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                total_equity REAL,
                available_margin REAL,
                used_margin REAL,
                position_count INTEGER,
                open_orders_count INTEGER
            );

            CREATE TABLE IF NOT EXISTS daily_pnl (
                date TEXT PRIMARY KEY,
                realized_pnl REAL DEFAULT 0,
                unrealized_pnl REAL DEFAULT 0,
                net_pnl REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS equity_curve (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                equity REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS risk_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                peak_equity REAL DEFAULT 0,
                trading_paused BOOLEAN DEFAULT 0,
                pause_reason TEXT,
                circuit_breaker_json TEXT,
                updated_ts TEXT
            );
        """)
        await db.commit()
    await optimize_db(str(db_path))
    logger.info(f"Database initialized at {db_path}")


async def insert_execution(
    db_path: str,
    symbol: str,
    order_id: Optional[str],
    side: str,
    price: Optional[float],
    qty: Optional[float],
    commission: Optional[float] = None,
    commission_asset: Optional[str] = None,
    exec_type: str = "fill"
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """INSERT INTO executions (ts, order_id, symbol, side, price, qty,
               commission, commission_asset, exec_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.utcnow().isoformat(),
                order_id,
                symbol,
                side,
                price,
                qty,
                commission,
                commission_asset,
                exec_type,
            ),
        )
        await db.commit()


async def insert_position_snapshot(db_path: str, position_data: dict) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM positions WHERE symbol = ?", (position_data["symbol"],))
        await db.execute(
            """INSERT INTO positions (
                ts, symbol, side, qty, entry_price, mark_price,
                unrealized_pnl, leverage, liquidation_price, margin,
                notional, roe, break_even_price, margin_ratio,
                funding_rate, funding_fee, liquidation_distance_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.utcnow().isoformat(),
                position_data["symbol"],
                position_data.get("side"),
                position_data.get("quantity"),
                position_data.get("entry_price"),
                position_data.get("mark_price"),
                position_data.get("unrealized_pnl"),
                position_data.get("leverage"),
                position_data.get("liquidation_price"),
                position_data.get("margin"),
                position_data.get("notional"),
                position_data.get("roe"),
                position_data.get("break_even_price"),
                position_data.get("margin_ratio"),
                position_data.get("funding_rate"),
                position_data.get("funding_fee"),
                position_data.get("liquidation_distance_pct"),
            ),
        )
        await db.commit()


async def get_daily_pnl(db_path: str, target_date: date) -> Optional[Dict]:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT * FROM daily_pnl WHERE date = ?", (target_date.isoformat(),))
        row = await cursor.fetchone()
        if row:
            return dict(zip([desc[0] for desc in cursor.description], row))
        return None

async def upsert_daily_pnl(db_path: str, pnl: Dict) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """INSERT OR REPLACE INTO daily_pnl (date, realized_pnl, unrealized_pnl, net_pnl)
               VALUES (?, ?, ?, ?)""",
            (pnl["date"].isoformat(), pnl["realized_pnl"], pnl["unrealized_pnl"], pnl["net_pnl"]),
        )
        await db.commit()

async def get_equity_curve(db_path: str, limit: int = 100) -> List[Dict]:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT * FROM equity_curve ORDER BY ts DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in rows]

async def insert_equity_snapshot(db_path: str, equity: float) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO equity_curve (ts, equity) VALUES (?, ?)",
            (datetime.utcnow().isoformat(), equity),
        )
        await db.commit()

async def get_risk_state(db_path: str) -> Optional[Dict]:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT * FROM risk_state WHERE id = 1")
        row = await cursor.fetchone()
        if row:
            cols = [desc[0] for desc in cursor.description]
            return dict(zip(cols, row))
        return None

async def save_risk_state(db_path: str, state: Dict) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """INSERT OR REPLACE INTO risk_state (id, peak_equity, trading_paused, pause_reason, circuit_breaker_json, updated_ts)
               VALUES (1, ?, ?, ?, ?, ?)""",
            (state["peak_equity"], state["trading_paused"], state["pause_reason"],
             state["circuit_breaker_json"], datetime.utcnow().isoformat()),
        )
        await db.commit()

async def get_completed_trades(db_path: str, min_trades: int = 20) -> List[Dict]:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """SELECT * FROM trades WHERE success = 1
               ORDER BY ts DESC LIMIT ?""", (min_trades,)
        )
        rows = await cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in rows]