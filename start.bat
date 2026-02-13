@echo off
chcp 65001 >nul 2>&1
title Twitch Channel Points Miner
echo ============================================
echo   Twitch Channel Points Miner Baslatiliyor
echo ============================================
echo.

cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [!] Virtual environment bulunamadi. Olusturuluyor...
    python -m venv venv
    echo [+] Venv olusturuldu.
    echo [*] Bagimliliklar yukleniyor...
    venv\Scripts\pip install -r requirements.txt
    echo [+] Bagimliliklar yuklendi.
    echo.
)

echo [*] Miner baslatiliyor...
echo.
venv\Scripts\python run.py

echo.
echo [!] Miner kapandi. Kapatmak icin bir tusa bas...
pause >nul
