"""Prueba de humo del servidor MCP (integrations/mcp_server.py).

Arranca el servidor como subproceso, hace el saludo del protocolo y llama a las
herramientas contra el proyecto de ejemplo. No necesita Ollama: usa el modo
solo-lexico, igual que `ask.py --lexico`.

    python tests/smoke_mcp.py

Si no existe el proyecto `demo-tienda`, lo siembra primero.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "integrations" / "mcp_server.py"
PROJECT = "demo-tienda"


def ensure_demo() -> None:
    if not (ROOT / "memory" / PROJECT).is_dir():
        print(f"[setup] sembrando proyecto de ejemplo '{PROJECT}'")
        subprocess.run([sys.executable, str(ROOT / "tools" / "seed_demo.py")],
                       check=True, capture_output=True)


def run_session(messages: list[dict]) -> list[dict]:
    proc = subprocess.Popen(
        [sys.executable, str(SERVER)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )
    payload = "".join(json.dumps(m) + "\n" for m in messages)
    out, _ = proc.communicate(payload, timeout=90)
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def result_for(responses: list[dict], id_: int) -> dict:
    for r in responses:
        if r.get("id") == id_:
            return r
    raise AssertionError(f"sin respuesta para id {id_}")


def text_of(response: dict) -> str:
    return response["result"]["content"][0]["text"]


def main() -> int:
    ensure_demo()

    responses = run_session([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "listar_proyectos", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "pedir_contexto", "arguments": {
             "query": "el carrito se vacia al perder la conexion",
             "project": PROJECT, "solo_lexico": True}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
         "params": {"name": "pedir_contexto", "arguments": {
             "query": "como integro los pagos con stripe",
             "project": PROJECT, "solo_lexico": True}}},
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
         "params": {"name": "detalle_registro",
                    "arguments": {"id": "BUG-003", "project": PROJECT}}},
        {"jsonrpc": "2.0", "id": 99, "method": "tools/call",
         "params": {"name": "pedir_contexto", "arguments": {"project": PROJECT}}},
    ])

    checks: list[tuple[str, bool]] = []

    init = result_for(responses, 1)["result"]
    checks.append(("initialize devuelve serverInfo",
                   init.get("serverInfo", {}).get("name") == "context-manager"))

    tools = {t["name"] for t in result_for(responses, 2)["result"]["tools"]}
    esperadas = {"pedir_contexto", "buscar_memoria", "detalle_registro",
                 "listar_proyectos", "estado_proyecto"}
    checks.append((f"tools/list expone {esperadas}", esperadas <= tools))

    proyectos = text_of(result_for(responses, 3))
    checks.append(("listar_proyectos incluye el demo", PROJECT in proyectos))

    con_precedente = text_of(result_for(responses, 4))
    checks.append(("pedir_contexto recupera BUG-003", "BUG-003" in con_precedente))

    sin_precedente = text_of(result_for(responses, 5))
    checks.append(("consulta sin memoria responde 'no hay ... relevante'",
                   "No hay memoria" in sin_precedente))

    detalle = text_of(result_for(responses, 6))
    checks.append(("detalle_registro devuelve el JSON de BUG-003",
                   '"id": "BUG-003"' in detalle))

    err = result_for(responses, 99)["result"]
    checks.append(("falta 'query' -> isError",
                   err.get("isError") is True and "query" in text_of(result_for(responses, 99))))

    print()
    ok = True
    for nombre, passed in checks:
        print(f"  [{'OK' if passed else 'FALLA'}] {nombre}")
        ok = ok and passed

    print("\nServidor MCP operativo." if ok else "\nHubo fallos.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
