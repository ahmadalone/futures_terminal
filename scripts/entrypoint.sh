#!/bin/bash
set -e

echo "Starting Futures Terminal $APP_VERSION"
# Initialize database if not exists
python -c "from database.db import init_db; import asyncio; asyncio.run(init_db('$DB_PATH'))"

# Launch the terminal
exec python main.py