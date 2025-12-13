#!/bin/bash
# Production startup script for Gunicorn
# Usage: chmod +x start.sh && ./start.sh

# Activate virtual environment
source venv/bin/activate

# Start Gunicorn with production settings
gunicorn \
  --workers 4 \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile /var/log/buffett_access.log \
  --error-logfile /var/log/buffett_error.log \
  --log-level info \
  buffett_app:app

# Notes:
# - --workers: number of worker processes (adjust based on CPU cores)
# - --bind: IP and port to listen on
# - --timeout: request timeout in seconds (TTS can take time)
# - --log-level: set to 'debug' if troubleshooting
