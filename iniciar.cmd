@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Instala Python 3.12 y sigue la preparacion del README.
  pause
  exit /b 1
)
echo Abre http://127.0.0.1:8765 y selecciona tus archivos en Entrada.
echo Ctrl+C para detener. Los archivos se procesan desde la pagina.
.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8765
