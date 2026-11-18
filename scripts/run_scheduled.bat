@echo off
REM Morning job for Task Scheduler. Runs the pipeline from the repo root
REM and appends stdout and stderr to data\logs\scheduler.log.
cd /d "%~dp0.."
if not exist "data\logs" mkdir "data\logs"
set PYTHONPATH=src
".venv\Scripts\python.exe" -m research_intel.jobs.run_daily %1 >> "data\logs\scheduler.log" 2>&1
