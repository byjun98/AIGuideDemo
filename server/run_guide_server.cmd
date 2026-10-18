@echo off
set PYTHONUTF8=1
if not defined AIGD_ROOT set "AIGD_ROOT=%~dp0.."
set "HF_HOME=%AIGD_ROOT%\cache\hf"
if not exist "%AIGD_ROOT%\logs" mkdir "%AIGD_ROOT%\logs"
cd /d "%~dp0"
"%AIGD_ROOT%\env\Scripts\python.exe" -m uvicorn guide_server:app --host 127.0.0.1 --port 8000 > "%AIGD_ROOT%\logs\guide_server.out.txt" 2> "%AIGD_ROOT%\logs\guide_server.err.txt"
exit /b %errorlevel%
