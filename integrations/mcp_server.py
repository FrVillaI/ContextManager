"""Servidor MCP del Context Manager.

Expone el flujo del Context Manager —«pedir contexto», consultar la memoria y
ver el estado del ciclo— como herramientas MCP, para que un IDE con agente
(Visual Studio Code, Google Antigravity, Orca…) pueda pedirlas por si mismo en
lugar de que copies y pegues bloques a mano.

Es un servidor MCP sobre **stdio** implementado solo con la biblioteca estandar
de Python: MCP por stdio no es mas que JSON-RPC 2.0 delimitado por saltos de
linea. No añade dependencias al proyecto y no depende de la version del SDK de
MCP, que aun cambia de API entre versiones mayores.

Reglas heredadas del sistema, respetadas aqui:

- El servidor **solo lee** la memoria canonica y construye contexto. No asciende
  nada a memoria: promocionar sigue siendo decision de una persona (DEC-023).
- Cada proyecto vive aislado; nunca se mezcla la memoria de dos proyectos
  (DEC-018).
- Si el modelo local no esta disponible, se degrada a solapamiento lexico igual
  que hace `ask.py`: que Ollama falte no puede tumbar la respuesta.

Uso directo (para depurar a mano):

    python integrations/mcp_server.py

y se queda esperando mensajes JSON-RPC en la entrada estandar. Lo habitual es
que lo lance el IDE; ver `integrations/README.md`.

Variables de entorno:

    CONTEXT_MANAGER_HOME       raiz de la instalacion (por defecto, la que
                               deduce este archivo). Ahi vive `memory/`.
    CONTEXT_MANAGER_PROJECT    project_id por defecto cuando la llamada no lo da.
    CONTEXT_MANAGER_WORKSPACE  carpeta del repositorio en el que trabajas; se usa
                               para leer `.context/project.json` y deducir el
                               proyecto. Por defecto, el directorio de trabajo.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable

# --------------------------------------------------------------------------
# Localizacion de la instalacion y carga de los modulos del Context Manager
# --------------------------------------------------------------------------

HOME = Path(os.environ.get("CONTEXT_MANAGER_HOME", "")).expanduser()
if not HOME or not HOME.is_dir():
    # integrations/mcp_server.py -> la raiz es el directorio padre.
    HOME = Path(__file__).resolve().parent.parent

MEMORY = HOME / "memory"
sys.path.insert(0, str(HOME / "src"))

# Version del protocolo MCP que anunciamos si el cliente no pide otra.
DEFAULT_PROTOCOL = "2025-06-18"
SERVER_NAME = "context-manager"
SERVER_VERSION = "1.0.0"


def log(*parts: Any) -> None:
    """Traza a stderr. stdout es el canal del protocolo y NO se puede tocar."""
    print(f"[context-manager-mcp]", *parts, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------
# Resolucion del proyecto activo (mismo criterio que ask.py)
# --------------------------------------------------------------------------

def _import_acm():
    """Importa lo minimo del Context Manager. Se hace tarde para dar un error
    claro por MCP si la instalacion no esta lista, en vez de morir al arrancar."""
    from acm.context import build
    from acm.hybrid import retrieve_hybrid
    from acm.retrieval import retrieve
    from acm.semantic import load_index
    from acm.store import MemoryStore, all_projects
    from acm.projects import Registry, read_context_file

    return {
        "build": build,
        "retrieve_hybrid": retrieve_hybrid,
        "retrieve": retrieve,
        "load_index": load_index,
        "MemoryStore": MemoryStore,
        "all_projects": all_projects,
        "Registry": Registry,
        "read_context_file": read_context_file,
    }


class ToolError(Exception):
    """Error que se devuelve al cliente como resultado de herramienta (isError)."""


def resolve_project(acm: dict, project: str | None) -> str:
    """Decide en que memoria se busca, sin mezclar proyectos (DEC-018).

    Orden: argumento explicito -> `.context/project.json` del workspace ->
    CONTEXT_MANAGER_PROJECT -> unico proyecto en disco -> error.
    """
    if project:
        return project

    workspace = os.environ.get("CONTEXT_MANAGER_WORKSPACE") or os.getcwd()
    try:
        marca = acm["read_context_file"](Path(workspace))
    except Exception:  # noqa: BLE001
        marca = None
    if marca and marca.get("project_id"):
        return marca["project_id"]

    env_pid = os.environ.get("CONTEXT_MANAGER_PROJECT")
    if env_pid:
        return env_pid

    disponibles = acm["all_projects"](MEMORY)
    if len(disponibles) == 1:
        return disponibles[0]

    raise ToolError(
        "No se pudo deducir el proyecto. Indica 'project' en la llamada. "
        f"Proyectos disponibles: {', '.join(disponibles) or 'ninguno'}."
    )


# --------------------------------------------------------------------------
# Implementacion de las herramientas
# --------------------------------------------------------------------------

def tool_pedir_contexto(args: dict) -> str:
    """El flujo central: peticion -> bloque de contexto listo para el modelo."""
    acm = _import_acm()

    query = (args.get("query") or "").strip()
    if not query:
        raise ToolError("Falta 'query': describe en lenguaje natural lo que vas a hacer.")

    limit = int(args.get("limit", 8) or 8)
    solo_lexico = bool(args.get("solo_lexico", False))
    usar_modelo = bool(args.get("usar_modelo", True))

    pid = resolve_project(acm, args.get("project"))
    store = acm["MemoryStore"](MEMORY, pid)
    records = list(store.all())

    avisos: list[str] = []
    if not records:
        avisos.append(f"El proyecto '{pid}' no tiene memoria todavia.")

    # Analisis de intencion con el modelo local. Degrada con elegancia: si el
    # modelo (Ollama) no esta, se sigue con solapamiento lexico.
    intent = None
    if usar_modelo and not solo_lexico:
        try:
            from acm.intent import analyze
            intent = analyze(query, records)
            if getattr(intent, "error", ""):
                avisos.append(f"El modelo local fallo, sigo solo con lexico: {intent.error}")
        except Exception as exc:  # noqa: BLE001
            avisos.append(f"Modelo de intencion no disponible ({exc}); uso solo lexico.")
            intent = None
    if intent is None:
        from acm.intent import Intent
        intent = Intent(intent="(sin analisis)")

    index = None if solo_lexico else acm["load_index"](MEMORY, pid)
    if index is None:
        hits = acm["retrieve"](
            records, query,
            extra_terms=intent.keyword_terms,
            hint_modules=intent.modules,
            limit=limit,
        )
    else:
        hits = acm["retrieve_hybrid"](
            records, query, index,
            extra_terms=intent.keyword_terms,
            hint_modules=intent.modules,
            limit=limit,
        )

    context = acm["build"](query, hits, intent)

    cabecera = ""
    if avisos:
        cabecera = "\n".join(f"# aviso: {a}" for a in avisos) + "\n\n"
    return cabecera + context.text


def tool_listar_proyectos(args: dict) -> str:
    """Todos los proyectos gestionados, con cuantos registros tiene cada uno."""
    acm = _import_acm()
    registro = acm["Registry"](HOME).load()
    con_memoria = acm["all_projects"](MEMORY)
    ids = sorted(set(registro) | set(con_memoria))
    if not ids:
        return "No hay proyectos registrados. Usa `python context_manager.py init <ruta>`."

    filas = []
    for pid in ids:
        store = acm["MemoryStore"](MEMORY, pid)
        n = sum(store.stats().values()) if pid in con_memoria else 0
        p = registro.get(pid)
        repo = p.repository if p else "(sin registrar en projects.json)"
        filas.append({"project_id": pid, "registros": n, "repositorio": repo})
    return json.dumps({"proyectos": filas}, ensure_ascii=False, indent=2)


def tool_buscar_memoria(args: dict) -> str:
    """Devuelve los registros que casan con la consulta, en JSON estructurado.

    Mas ligero que `pedir_contexto`: sin el bloque de texto montado, util cuando
    el agente quiere decidir por si mismo que registros expandir.
    """
    acm = _import_acm()
    query = (args.get("query") or "").strip()
    if not query:
        raise ToolError("Falta 'query'.")
    limit = int(args.get("limit", 8) or 8)

    pid = resolve_project(acm, args.get("project"))
    store = acm["MemoryStore"](MEMORY, pid)
    records = list(store.all())

    from acm.intent import Intent
    intent = Intent(intent="(sin analisis)")
    index = acm["load_index"](MEMORY, pid) if not args.get("solo_lexico") else None
    if index is None:
        hits = acm["retrieve"](records, query, limit=limit)
    else:
        hits = acm["retrieve_hybrid"](records, query, index, limit=limit)

    salida = []
    for h in hits:
        r = h.record
        salida.append({
            "id": r.id,
            "tipo": r.type,
            "titulo": r.title,
            "resumen": r.summary,
            "provenance": r.provenance.value,
            "confirmado": r.trusted,
            "precedente_directo": bool(getattr(h, "direct", False)),
            "archivos": list(r.files),
            "modulos": list(r.modules),
        })
    return json.dumps({"proyecto": pid, "resultados": salida}, ensure_ascii=False, indent=2)


def tool_detalle_registro(args: dict) -> str:
    """Un registro concreto de la memoria, entero."""
    acm = _import_acm()
    rid = (args.get("id") or "").strip()
    if not rid:
        raise ToolError("Falta 'id' (por ejemplo BUG-001).")
    pid = resolve_project(acm, args.get("project"))
    store = acm["MemoryStore"](MEMORY, pid)
    r = store.by_id(rid)
    if r is None:
        raise ToolError(f"No existe el registro '{rid}' en el proyecto '{pid}'.")
    return r.model_dump_json(indent=2)


def tool_estado_proyecto(args: dict) -> str:
    """Resumen de salud del ciclo de memoria de un proyecto."""
    acm = _import_acm()
    pid = resolve_project(acm, args.get("project"))
    store = acm["MemoryStore"](MEMORY, pid)
    registros = list(store.all())

    from collections import Counter
    proc = Counter(r.provenance.value for r in registros)
    confirmados = sum(1 for r in registros if r.trusted)

    resumen = {
        "proyecto": pid,
        "registros": len(registros),
        "por_tipo": dict(store.stats()),
        "por_procedencia": dict(proc),
        "confirmados_como_afirmacion": confirmados,
        "integridad": store.check() or "OK",
    }
    return json.dumps(resumen, ensure_ascii=False, indent=2)


# Registro de herramientas: nombre -> (funcion, descripcion, esquema de entrada)
_PROJECT_PROP = {
    "type": "string",
    "description": "project_id. Si se omite, se deduce del workspace "
                   "(.context/project.json), de CONTEXT_MANAGER_PROJECT, o del "
                   "unico proyecto existente.",
}

TOOLS: dict[str, dict] = {
    "pedir_contexto": {
        "fn": tool_pedir_contexto,
        "description": (
            "Pide a la memoria del proyecto el contexto relevante para una tarea "
            "y devuelve un bloque de texto listo para razonar sobre el. Llamala "
            "ANTES de empezar cualquier cambio: recupera bugs previos de la zona, "
            "decisiones vigentes, restricciones que no se pueden romper y "
            "soluciones que ya funcionaron, y NADA mas. Si no hay precedentes, lo "
            "dice explicitamente en vez de inventar experiencia."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "La tarea en lenguaje natural, p. ej. "
                                   "'mostrar el catalogo de dos en dos'.",
                },
                "project": _PROJECT_PROP,
                "limit": {
                    "type": "integer",
                    "description": "Maximo de registros a incluir (por defecto 8).",
                    "default": 8,
                },
                "usar_modelo": {
                    "type": "boolean",
                    "description": "Usar el modelo local (Ollama) para analizar la "
                                   "intencion. Si no esta disponible, degrada a "
                                   "lexico solo. Por defecto true.",
                    "default": True,
                },
                "solo_lexico": {
                    "type": "boolean",
                    "description": "Saltarse el modelo y la capa semantica; usar "
                                   "solo solapamiento lexico. Por defecto false.",
                    "default": False,
                },
            },
            "required": ["query"],
        },
    },
    "buscar_memoria": {
        "fn": tool_buscar_memoria,
        "description": (
            "Busca en la memoria del proyecto y devuelve los registros que casan "
            "en JSON (id, tipo, titulo, resumen, procedencia, archivos, modulos). "
            "Como 'pedir_contexto' pero estructurado, sin montar el bloque de texto."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Consulta en lenguaje natural."},
                "project": _PROJECT_PROP,
                "limit": {"type": "integer", "default": 8},
                "solo_lexico": {"type": "boolean", "default": False},
            },
            "required": ["query"],
        },
    },
    "detalle_registro": {
        "fn": tool_detalle_registro,
        "description": "Devuelve un registro de memoria concreto por su id "
                       "(p. ej. BUG-001), con todos sus campos.",
        "schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Id del registro, p. ej. BUG-001."},
                "project": _PROJECT_PROP,
            },
            "required": ["id"],
        },
    },
    "listar_proyectos": {
        "fn": tool_listar_proyectos,
        "description": "Lista los proyectos gestionados por el Context Manager y "
                       "cuantos registros de memoria tiene cada uno.",
        "schema": {"type": "object", "properties": {}},
    },
    "estado_proyecto": {
        "fn": tool_estado_proyecto,
        "description": "Resumen de la memoria de un proyecto: numero de registros, "
                       "reparto por tipo y por procedencia, cuantos estan "
                       "confirmados y si la integridad de los enlaces es correcta.",
        "schema": {
            "type": "object",
            "properties": {"project": _PROJECT_PROP},
        },
    },
}


# --------------------------------------------------------------------------
# Prompts MCP (plantillas que el usuario puede invocar desde el IDE)
# --------------------------------------------------------------------------

PROMPTS: dict[str, dict] = {
    "contexto_para_tarea": {
        "description": "Recupera el contexto del proyecto para una tarea y lo "
                       "deja listo para trabajar sobre el.",
        "arguments": [
            {"name": "tarea", "description": "Que vas a hacer.", "required": True},
            {"name": "project", "description": "project_id (opcional).", "required": False},
        ],
    },
}


def build_prompt(name: str, args: dict) -> dict:
    if name != "contexto_para_tarea":
        raise ToolError(f"Prompt desconocido: {name}")
    tarea = args.get("tarea", "").strip()
    project = args.get("project", "")
    extra = f" (proyecto {project})" if project else ""
    texto = (
        f"Antes de tocar nada, usa la herramienta `pedir_contexto` del Context "
        f"Manager para la tarea{extra}: \"{tarea}\". Lee los precedentes, "
        f"decisiones y restricciones que devuelva y tenlos en cuenta. Si dice "
        f"que no hay precedentes, tratalo como territorio nuevo."
    )
    return {
        "description": PROMPTS[name]["description"],
        "messages": [
            {"role": "user", "content": {"type": "text", "text": texto}},
        ],
    }


# --------------------------------------------------------------------------
# Bucle JSON-RPC sobre stdio
# --------------------------------------------------------------------------

def _result(id_: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _error(id_: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def handle_initialize(params: dict) -> dict:
    client_proto = (params or {}).get("protocolVersion") or DEFAULT_PROTOCOL
    return {
        "protocolVersion": client_proto,
        "capabilities": {
            "tools": {"listChanged": False},
            "prompts": {"listChanged": False},
        },
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        "instructions": (
            "Context Manager: memoria de proyecto para desarrollo con IA. Llama a "
            "`pedir_contexto` antes de cambiar codigo para recuperar precedentes, "
            "decisiones y restricciones relevantes. El servidor solo lee la "
            "memoria; nada se asciende a memoria sin verificacion humana."
        ),
    }


def handle_tools_list() -> dict:
    return {
        "tools": [
            {
                "name": name,
                "description": spec["description"],
                "inputSchema": spec["schema"],
            }
            for name, spec in TOOLS.items()
        ]
    }


def handle_tools_call(params: dict) -> dict:
    name = (params or {}).get("name")
    args = (params or {}).get("arguments") or {}
    spec = TOOLS.get(name)
    if spec is None:
        raise ToolError(f"Herramienta desconocida: {name}")
    t0 = time.perf_counter()
    texto = spec["fn"](args)
    log(f"tool '{name}' -> {len(texto)} chars en {time.perf_counter() - t0:.2f}s")
    return {"content": [{"type": "text", "text": texto}], "isError": False}


def handle_prompts_list() -> dict:
    return {
        "prompts": [
            {"name": name, "description": spec["description"], "arguments": spec["arguments"]}
            for name, spec in PROMPTS.items()
        ]
    }


def handle_prompts_get(params: dict) -> dict:
    name = (params or {}).get("name")
    args = (params or {}).get("arguments") or {}
    return build_prompt(name, args)


def dispatch(method: str, params: dict) -> Any:
    """Devuelve el `result` para un metodo con respuesta. Lanza en caso de error."""
    if method == "initialize":
        return handle_initialize(params)
    if method == "ping":
        return {}
    if method == "tools/list":
        return handle_tools_list()
    if method == "tools/call":
        return handle_tools_call(params)
    if method == "prompts/list":
        return handle_prompts_list()
    if method == "prompts/get":
        return handle_prompts_get(params)
    if method in ("resources/list", "resources/templates/list"):
        # No exponemos recursos; algunos clientes lo piden igualmente.
        return {"resources": [], "resourceTemplates": []}
    raise LookupError(method)


def send(message: dict, out) -> None:
    out.write(json.dumps(message, ensure_ascii=False) + "\n")
    out.flush()


def main() -> int:
    log(f"arrancado. HOME={HOME} MEMORY={MEMORY}")
    stdin = sys.stdin
    stdout = sys.stdout

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            log(f"json invalido: {exc}")
            send(_error(None, -32700, f"Parse error: {exc}"), stdout)
            continue

        method = msg.get("method")
        params = msg.get("params") or {}
        msg_id = msg.get("id")
        is_notification = "id" not in msg

        # Notificaciones (sin id): no llevan respuesta.
        if is_notification:
            if method == "notifications/initialized":
                log("cliente inicializado")
            elif method == "notifications/cancelled":
                pass
            else:
                log(f"notificacion ignorada: {method}")
            continue

        try:
            result = dispatch(method, params)
            send(_result(msg_id, result), stdout)
        except ToolError as exc:
            # Errores esperables de herramienta: se devuelven como resultado
            # isError para que el agente los vea, no como fallo de protocolo.
            if method == "tools/call":
                send(_result(msg_id, {
                    "content": [{"type": "text", "text": f"ERROR: {exc}"}],
                    "isError": True,
                }), stdout)
            else:
                send(_error(msg_id, -32602, str(exc)), stdout)
        except LookupError:
            send(_error(msg_id, -32601, f"Metodo no soportado: {method}"), stdout)
        except Exception as exc:  # noqa: BLE001
            log("error interno:\n" + traceback.format_exc())
            if method == "tools/call":
                send(_result(msg_id, {
                    "content": [{"type": "text", "text": f"ERROR interno: {exc}"}],
                    "isError": True,
                }), stdout)
            else:
                send(_error(msg_id, -32603, f"Internal error: {exc}"), stdout)

    log("stdin cerrado; fin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
