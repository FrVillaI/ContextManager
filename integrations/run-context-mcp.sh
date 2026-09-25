#!/usr/bin/env bash
# Lanzador del servidor MCP del Context Manager para Linux/macOS.
#
# Un IDE (VS Code, Antigravity, Orca...) apunta su configuracion MCP a este
# archivo. El lanzador se encarga de:
#   - situar CONTEXT_MANAGER_HOME en la raiz de la instalacion,
#   - usar el Python del entorno virtual (.venv) si existe,
#   - arrancar el servidor con la entrada/salida estandar conectadas al IDE.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CONTEXT_MANAGER_HOME="$(cd "$HERE/.." && pwd)"

PY="$CONTEXT_MANAGER_HOME/.venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3 || command -v python)"
fi

exec "$PY" "$HERE/mcp_server.py" "$@"
