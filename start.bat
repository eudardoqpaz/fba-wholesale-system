@echo off
title Amazon FBA Wholesale System
echo ============================================
echo   Amazon FBA Wholesale System
echo ============================================
echo.

cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado.
    echo Descarga Python 3.10+ desde https://python.org
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

echo [OK] Python encontrado:
python --version
echo.

REM Create venv if not exists
if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] Creando entorno virtual...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    echo [OK] Entorno virtual creado.
    echo.
)

REM Activate venv
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] No se pudo activar el entorno virtual.
    pause
    exit /b 1
)

REM Install dependencies
echo [INFO] Verificando dependencias...
pip install -r requirements.txt -q 2>nul
if errorlevel 1 (
    echo [WARN] Reinstalando dependencias...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] No se pudieron instalar las dependencias.
        pause
        exit /b 1
    )
)
echo [OK] Dependencias instaladas.
echo.

REM Copy .env if not exists
if not exist ".env" (
    echo [INFO] Creando archivo .env...
    copy .env.example .env >nul
    echo [WARN] Archivo .env creado. Editalo con tus API keys cuando sea necesario.
    echo.
)

echo ============================================
echo   Servidor iniciando en:
echo   http://localhost:8000
echo   
echo   Presiona Ctrl+C para detener
echo ============================================
echo.

python main.py

echo.
echo [INFO] El servidor se detuvo.
pause
