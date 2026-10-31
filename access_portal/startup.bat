@echo off
rem Usage: startup.bat [--setup]   (--setup also creates the sample USTA databases)
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
  python -m venv .venv
  .venv\Scripts\python.exe -m pip install -q -r requirements.txt
)

if "%AURORA_ADMIN_USER%"=="" set AURORA_ADMIN_USER=admin
if "%AURORA_ADMIN_PASSWORD%"=="" set /p AURORA_ADMIN_PASSWORD=Aurora password for %AURORA_ADMIN_USER%: 

.venv\Scripts\python.exe test_connection.py || exit /b 1
if "%1"=="--setup" .venv\Scripts\python.exe setup_sample_data.py

.venv\Scripts\python.exe -m streamlit run app.py
