@echo off
REM Production startup script for Windows (testing/local deployment)
REM Usage: start.bat

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Start Gunicorn
gunicorn --workers 4 --bind 0.0.0.0:8000 --timeout 120 buffett_app:app

REM Notes:
REM - Open browser to http://localhost:8000
REM - Press Ctrl+C to stop
