@echo off
pwsh -NoProfile -File "%~dp0run_v3_pipeline.ps1"
exit /b %errorlevel%
