@echo off
setlocal
title SpaceRouge mobile - PC test
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Creating a Python environment for the mobile build...
    py -3 -m venv .venv 2>nul || python -m venv .venv
    if errorlevel 1 (
        echo Could not create a venv - is Python installed?
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
".venv\Scripts\python.exe" main.py %*
if errorlevel 1 pause
