#!/bin/bash

# Startup script for Cloud Run
set -e

# Get the port from environment variable (Cloud Run sets this)
PORT=${PORT:-8080}

echo "Starting Raseed Backend on port $PORT"

# Start the application with gunicorn
exec gunicorn \
    --bind "0.0.0.0:$PORT" \
    --workers 1 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 0 \
    --keep-alive 2 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --preload \
    --log-level info \
    app.main:app
