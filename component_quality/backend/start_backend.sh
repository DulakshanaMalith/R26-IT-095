#!/bin/bash

# Move to the directory where the script is located
cd "$(dirname "$0")"

# Load environment variables from .env if it exists
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Create logs directory
mkdir -p logs

# Set default values if they aren't provided in .env
if [ -f "venv/bin/python" ]; then
    PYTHON_EXE="${PYTHON_EXE:-venv/bin/python}"
else
    PYTHON_EXE="${PYTHON_EXE:-python3}"
fi
APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-9000}"
LOG_FILE="logs/backend.combined.log"

# Run Uvicorn and append all output to the log file
$PYTHON_EXE -m uvicorn src.api.main:app --host "$APP_HOST" --port "$APP_PORT" >> "$LOG_FILE" 2>&1
