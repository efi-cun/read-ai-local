@echo off
title ReadAI Local - Servidor de Asistencia y Reuniones
cd /d "%~dp0"

echo ========================================================
echo       INICIANDO READAI LOCAL - MEETSENSE
echo ========================================================
echo.
echo [*] Abriendo panel de control en tu navegador...
start http://localhost:8000/attendance
echo [*] Servidor ejecutandose en http://127.0.0.1:8000
echo [*] Para detener el servidor, cierra esta ventana.
echo ========================================================
echo.

python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
pause
