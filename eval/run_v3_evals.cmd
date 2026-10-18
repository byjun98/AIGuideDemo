@echo off
pwsh -NoProfile -File "%~dp0run_evaluations.ps1"
exit /b %errorlevel%
