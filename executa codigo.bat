@echo off
setlocal

REM === Caminhos do projeto (ATENÇÃO: tem espaço no nome da pasta) ===
set "PROJECT_DIR=C:\script python\lucenera"

REM === Ir para a pasta do projeto ===
cd /d "%PROJECT_DIR%"

REM === Ativar o venv ===
call ".venv\Scripts\activate.bat"

REM === Flags úteis do app ===
set "NGROK_KILL_ON_START=1"
REM set "ZAPI_WEBHOOK_MODE=receive_only"  REM opcional: modo de webhook alternativo

REM === Rodar o app com o Python do venv ===
"%PROJECT_DIR%\.venv\Scripts\python.exe" "%PROJECT_DIR%\app.py"

REM Mantém a janela aberta se o app encerrar
pause
