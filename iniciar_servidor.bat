@echo off
chcp 65001 >nul
title ReadAI Local - Servidor de Asistencia y Reuniones
cd /d "%~dp0"

echo ========================================================
echo       INICIANDO READAI LOCAL - MEETSENSE
echo ========================================================
echo.

:: Verificar si el puerto 8000 ya esta en uso
netstat -ano | findstr :8000 | findstr LISTENING >nul
if %errorlevel% equ 0 (
    echo [!] El servidor ya se encuentra encendido en el puerto 8000.
    echo [*] Abriendo el panel de control en tu navegador...
    start http://localhost:8000/attendance
    timeout /t 2 >nul
    exit /b 0
)

echo [*] Abriendo panel de control en tu navegador...
start http://localhost:8000/attendance
echo [*] Servidor ejecutandose en http://127.0.0.1:8000
echo [*] Para detener el servidor, cierra esta ventana.
echo ========================================================
echo.

python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
pause
