import pytest
import aiosqlite
import os
from database.db import init_db, insert_execution, insert_position_snapshot

@pytest.mark.asyncio
async def test_init_db_creates_tables(mock_db):
    await init_db(mock_db)
    async with aiosqlite.connect(mock_db) as db:
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] async for row in cursor]
    assert "trades" in tables
    assert "positions" in tables
    assert "orders" in tables
    assert "executions" in tables

@pytest.mark.asyncio
async def test_insert_execution(mock_db):
    await init_db(mock_db)
    await insert_execution(mock_db, "BTCUSDT", "123", "buy", 50000.0, 0.1)
    async with aiosqlite.connect(mock_db) as db:
        cursor = await db.execute("SELECT * FROM executions")
        rows = await cursor.fetchall()
    assert len(rows) == 1
    assert rows[0][2] == "BTCUSDT"