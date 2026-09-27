"""Modo de ejecucion de la IA local (DEC-032).

«Encender o apagar la IA local» resulto ser la pregunta equivocada, porque la IA
local son **dos piezas con relacion coste-beneficio opuesta**:

    llama3.2:3b (intencion)   4-10 s por consulta, ~2 GB residentes
                              solo reordena: DEC-015 le quito el poder de
                              admitir candidatos por ser demasiado grueso

    nomic-embed-text          ~0,3 s, ~300 MB, el indice ya esta calculado
                              recall de sinonimos x2, nDCG x3,6

El modelo caro es el que menos aporta. Un interruptor unico obliga a tirar los
dos juntos, asi que hay tres modos y el intermedio es el predeterminado:

    completo   intencion + embeddings
    ahorro     solo embeddings          <- por defecto
    minimo     solo lexico, sin Ollama

El modo se guarda en disco porque el servidor MCP **no puede recibir banderas**:
lo lanza el IDE. Sin un ajuste persistente, la extension intentaria siempre usar
el modelo local aunque no lo quisieras.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

CONFIG_FILE = "config.json"

#: Cuanto se recuerda que Ollama respondia o no, para no pagar el fallo de
#: conexion en cada llamada. Un proceso de CLI vive un instante, asi que el
#: recuerdo tiene que sobrevivir en disco.
SALUD_TTL = 30.0

OLLAMA_BASE = os.getenv("ACM_OLLAMA_BASE", "http://127.0.0.1:11434")


@dataclass(frozen=True)
class Modo:
    nombre: str
    usa_intencion: bool
    usa_embeddings: bool
    descripcion: str

    def describe(self) -> str:
        piezas = []
        if self.usa_intencion:
            piezas.append("intencion")
        if self.usa_embeddings:
            piezas.append("embeddings")
        return f"{self.nombre} ({', '.join(piezas) or 'solo lexico'})"


MODOS: dict[str, Modo] = {
    "completo": Modo(
        "completo", True, True,
        "modelo generativo + embeddings. La mejor calidad y el mayor coste.",
    ),
    "ahorro": Modo(
        "ahorro", False, True,
        "solo embeddings. Conserva el recall de sinonimos sin los 2 GB "
        "ni los 4-10 s del modelo generativo.",
    ),
    "minimo": Modo(
        "minimo", False, False,
        "solo solapamiento lexico. No necesita Ollama en absoluto.",
    ),
}

MODO_POR_DEFECTO = "ahorro"


# --------------------------------------------------------------------------
# Configuracion en disco
# --------------------------------------------------------------------------

def config_path(root: Path | str) -> Path:
    return Path(root) / CONFIG_FILE


def load_config(root: Path | str) -> dict:
    ruta = config_path(root)
    if not ruta.exists():
        return {}
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(root: Path | str, data: dict) -> Path:
    ruta = config_path(root)
    ruta.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return ruta


def resolve(root: Path | str, project_id: str | None = None) -> Modo:
    """Modo efectivo: la anulacion del proyecto gana sobre la global.

    La variable de entorno `ACM_MODO` gana sobre todo, para poder probar un modo
    puntualmente sin tocar la configuracion.
    """
    forzado = os.getenv("ACM_MODO", "").strip().lower()
    if forzado in MODOS:
        return MODOS[forzado]

    cfg = load_config(root)
    if project_id:
        propio = (cfg.get("por_proyecto") or {}).get(project_id)
        if propio in MODOS:
            return MODOS[propio]
    global_ = cfg.get("modo")
    return MODOS.get(global_, MODOS[MODO_POR_DEFECTO])


def set_mode(root: Path | str, modo: str, project_id: str | None = None) -> Modo:
    if modo not in MODOS:
        raise ValueError(f"modo desconocido: {modo}. Usa {', '.join(MODOS)}")
    cfg = load_config(root)
    if project_id:
        cfg.setdefault("por_proyecto", {})[project_id] = modo
    else:
        cfg["modo"] = modo
    save_config(root, cfg)
    return MODOS[modo]


def clear_project_mode(root: Path | str, project_id: str) -> bool:
    cfg = load_config(root)
    quitado = (cfg.get("por_proyecto") or {}).pop(project_id, None) is not None
    if quitado:
        save_config(root, cfg)
    return quitado


# --------------------------------------------------------------------------
# Salud de Ollama, con memoria corta
# --------------------------------------------------------------------------

def _cache_path(root: Path | str) -> Path:
    return Path(root) / ".ollama_health"


def ollama_disponible(root: Path | str, *, timeout: float = 1.5,
                      usar_cache: bool = True) -> bool:
    """Si Ollama responde. Se recuerda el resultado unos segundos.

    Sin este recuerdo, cada invocacion de la CLI paga el intento de conexion.
    Con el servicio simplemente parado el fallo es inmediato, pero con uno
    colgado se espera el tiempo completo en cada llamada.
    """
    cache = _cache_path(root)
    if usar_cache and cache.exists():
        try:
            datos = json.loads(cache.read_text(encoding="utf-8"))
            if time.time() - datos.get("t", 0) < SALUD_TTL:
                return bool(datos.get("ok"))
        except (OSError, json.JSONDecodeError):
            pass

    ok = False
    try:
        import httpx

        with httpx.Client(timeout=timeout, trust_env=False) as client:
            ok = client.get(f"{OLLAMA_BASE}/api/version").status_code == 200
    except Exception:  # noqa: BLE001
        ok = False

    try:
        cache.write_text(json.dumps({"ok": ok, "t": time.time()}), encoding="utf-8")
    except OSError:
        pass
    return ok


def forget_health(root: Path | str) -> None:
    """Olvida el estado recordado. Util tras arrancar o parar Ollama."""
    cache = _cache_path(root)
    if cache.exists():
        try:
            cache.unlink()
        except OSError:
            pass


# --------------------------------------------------------------------------
# Liberar memoria de verdad
# --------------------------------------------------------------------------

def unload_models(modelos: list[str], *, timeout: float = 10.0) -> list[tuple[str, bool]]:
    """Descarga modelos de la memoria de Ollama.

    Dejar de llamar al modelo no lo descarga: Ollama lo mantiene cargado unos
    minutos esperando la siguiente peticion. Para liberar la RAM hay que pedirlo
    explicitamente con `keep_alive: 0`.
    """
    resultados: list[tuple[str, bool]] = []
    try:
        import httpx
    except ImportError:
        return [(m, False) for m in modelos]

    with httpx.Client(timeout=timeout, trust_env=False) as client:
        for modelo in modelos:
            try:
                r = client.post(f"{OLLAMA_BASE}/api/generate",
                                json={"model": modelo, "keep_alive": 0})
                resultados.append((modelo, r.status_code == 200))
            except Exception:  # noqa: BLE001
                resultados.append((modelo, False))
    return resultados


def loaded_models(*, timeout: float = 5.0) -> list[dict]:
    """Que modelos tiene Ollama cargados ahora mismo, y cuanta memoria ocupan."""
    try:
        import httpx

        with httpx.Client(timeout=timeout, trust_env=False) as client:
            r = client.get(f"{OLLAMA_BASE}/api/ps")
            if r.status_code == 200:
                return r.json().get("models", [])
    except Exception:  # noqa: BLE001
        pass
    return []
