@echo off
title AMU-ECSF Counseling Bot
echo ========================================================
echo Starting AMU-ECSF Counseling Bot...
echo ========================================================
cd /d "%~dp0"

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ and make sure to check "Add Python to PATH".
    pause
    exit /b 1
)

REM Run bot
python main.py
if %errorlevel% neq 0 (
    echo.
    echo Bot stopped with an error. Check the messages above.
    pause
)
