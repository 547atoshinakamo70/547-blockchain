#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# 1) Crear venv si no existe
if [ ! -d ".venv" ]; then
  echo "[*] Creando entorno .venv ..."
  python3 -m venv .venv
fi

# 2) Activar venv
source .venv/bin/activate

# 3) Instalar deps
python -m pip install --upgrade pip
[ -f requirements.txt ] && echo "[*] Instalando deps nodo..." && pip install -r requirements.txt
[ -f p2p_bridge/requirements.txt ] && echo "[*] Instalando deps bridge..." && pip install -r p2p_bridge/requirements.txt

# 4) Arrancar nodo (5000)
echo "[*] Arrancando nodo..."
(.venv/bin/python My_blockchain.py > node.log 2>&1 &)

# 5) Espera corta y arranca bridge (15471)
sleep 2
echo "[*] Arrancando bridge..."
.exec_cmd=".venv/bin/python p2p_bridge/bridge.py"
$exec_cmd > bridge.log 2>&1 &

# 6) Abrir PWA
URL="https://547atoshinakamo70.github.io/547-blockchain/"
if command -v xdg-open >/dev/null; then xdg-open "$URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null; then open "$URL" >/dev/null 2>&1 || true
fi

echo "✅ Todo lanzado. Logs: node.log / bridge.log"
# Mantener terminal visible si se lanza con doble-clic (Terminal.app)
read -p "Pulsa Enter para cerrar esta ventana..."
