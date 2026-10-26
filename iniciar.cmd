@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Primero instala Python 3.12 y sigue los pasos del README.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m src.cli cargar --fuente ATM --archivo datasets/transacciones_atm.xlsx --catalogo datasets/catalogo_cuentas.csv
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m src.cli cargar --fuente DIGITAL --archivo datasets/transferencias_digitales.json
if errorlevel 1 exit /b 1
echo Abre http://127.0.0.1:8765 en tu navegador. Ctrl+C para detener.
.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8765
