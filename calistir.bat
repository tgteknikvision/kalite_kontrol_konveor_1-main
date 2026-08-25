@echo off
REM ============================================================
REM Konveyor Bant Denetim Sistemi - Windows TEMIZ baslatici
REM - pythonw.exe : konsol penceresi YOK (sadece uygulama acilir)
REM - start ""    : bu pencere bloklanmaz, hemen kapanir (terminal serbest)
REM - DAIMA venv kullanir (sistem Python'u DEGIL; eksik paket sorunu olmaz)
REM Kullanim: bu dosyaya CIFT TIKLA. (VS Code Run dugmesini kullanma.)
REM ============================================================
cd /d "%~dp0"
start "" "%~dp0veri_toplama\Scripts\pythonw.exe" main.py
