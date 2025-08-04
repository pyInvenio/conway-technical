#!/bin/sh

# Run database migrations
echo "Running database migrations..."
cd /app && alembic upgrade head

# Start supervisord
echo "Starting services..."
exec supervisord -c /etc/supervisor/conf.d/supervisord.conf