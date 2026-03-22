@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
pip install -q -r backend\requirements.txt
python backend\server.py
pause
