@echo off
REM Scheduled runner for Research Intelligence Engine
cd /d "%~dp0.."
if not exist "data\logs" mkdir "data\logs"
set PYTHONPATH=src
".venv\Scripts\python.exe" -m research_intel.jobs.run_daily %1 >> "data\logs\scheduler.log" 2>&1
