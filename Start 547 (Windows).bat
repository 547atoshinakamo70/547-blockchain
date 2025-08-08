@echo off
setlocal ENABLEDELAYEDEXPANSION
title 547 Launcher

REM Ir a la carpeta del script
cd /d "%~dp0"

REM 1) Crear venv si no existe
if not exist .venv (
  echo [*] Creando entorno .venv ...
  py -3 -m venv .venv 2>nul || python -m venv .venv
)

REM 2) Activar venv
call .venv\Scripts\activate

REM 3) Actualizar pip e instalar dependencias (nodo + bridge)
python -m pip install --upgrade pip
if exist requirements.txt (
  echo [*] Instalando deps del nodo...
  python -m pip install -r requirements.txt
)
if exist p2p_bridge\requirements.txt (
  echo [*] Instalando deps del bridge...
  python -m pip install -r p2p_bridge\requirements.txt
)

REM 4) Arrancar nodo (puerto 5000)
echo [*] Arrancando nodo en segundo plano...
start "547-node" cmd /c ".venv\Scripts\python.exe My_blockchain.py"

REM pequeña espera
timeout /t 3 >nul

REM 5) Arrancar bridge (puerto 15471)
echo [*] Arrancando bridge (API local)...
start "547-bridge" cmd /k ".venv\Scripts\python.exe p2p_bridge\bridge.py"

REM 6) Abrir la PWA en el navegador (auto-detecta localhost)
start "" "https://547atoshinakamo70.github.io/547-blockchain/"

echo.
echo ✅ Todo lanzado. Deja esta ventana abierta para ver logs del bridge.
pause
