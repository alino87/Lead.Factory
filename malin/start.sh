#!/bin/sh
set -e

echo "Running Alembic migrations..."
cd /app
python -m alembic -c malin/alembic.ini upgrade head

echo "Starting MALIN backend..."
exec python -m malin.app.main
