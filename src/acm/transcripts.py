"""Lectura de transcripciones de sesiones de agente CLI (DEC-030).

Por que NO se envuelve la CLI
-----------------------------
El diseño obvio seria `context-manager run claude`: interponerse entre el usuario
y la herramienta para capturar la interaccion. Es fragil. Claude Code y la
mayoria de agentes modernos son **TUI a pantalla completa**, no herramientas de
linea: un envoltorio captura secuencias ANSI, movimientos de cursor y
redibujados, no texto. En Windows, ademas, no hay `pty`.

Resulta que no hace falta. Claude Code ya escribe una transcripcion **JSONL
estructurada** por sesion en `~/.claude/projects/<slug>/<uuid>.jsonl`, con
`timestamp`, `cwd`, `gitBranch` y los mensajes separados por rol. Leerla de ahi
es mas robusto, no interfiere con la herramienta, y funciona retroactivamente.

El slug no se calcula
---------------------
El nombre de carpeta depende de como se lanzo la herramienta y no es estable
(se han visto `C--Users-...` y `c--Users-...` para rutas equivalentes). En vez de
adivinarlo, se leen las transcripciones y se compara el campo `cwd` que llevan
dentro. Es evidencia, no deduccion.

Que se extrae
-------------
Fragmentos **candidatos**, no memoria. La herramienta propone; la persona elige
cuales se convierten en rationale. La conversacion completa nunca entra: su ruta
se guarda como referencia de auditoria (DEC-029).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

#: Donde guarda Claude Code sus transcripciones.
CLAUDE_PROJECTS = Path(os.path.expanduser("~")) / ".claude" / "projects"

#: Por debajo de esto un mensaje no explica nada util.
MIN_FRAGMENT = 200

#: Marcas de que un texto describe trabajo hecho, no charla ni preguntas.
SEÑALES = (
    "porque", "el problema", "la causa", "se debia", "cambi", "modific",
    "añad", "anad", "implement", "corrig", "arregl", "descart", "en vez de",
    "en lugar de", "riesgo", "decidi", "opte", "reemplaz",
)


@dataclass
class Fragment:
    """Un candidato a rationale. Todavia no es evidencia de nada."""

    text: str
    timestamp: str
    role: str = "assistant"
    score: float = 0.0

    @property
    def when(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
        except ValueError:
            return None

    def preview(self, n: int = 88) -> str:
        limpio = " ".join(self.text.split())
        return limpio[:n] + ("..." if len(limpio) > n else "")


@dataclass
class Transcript:
    path: Path
    cwd: str = ""
    session_id: str = ""
    branch: str = ""
    started: str = ""
    ended: str = ""
    fragments: list[Fragment] = field(default_factory=list)

    def describe(self) -> str:
        return (f"{self.path.name[:8]}  {self.ended[:16] or '?'}  "
                f"{len(self.fragments)} fragmentos  {self.branch or '-'}")


def _texto_de(message: dict) -> str:
    """Extrae solo texto. Las llamadas a herramientas no son explicaciones."""
    contenido = message.get("content")
    if isinstance(contenido, str):
        return contenido
    if not isinstance(contenido, list):
        return ""
    partes = [
        bloque.get("text", "")
        for bloque in contenido
        if isinstance(bloque, dict) and bloque.get("type") == "text"
    ]
    return "\n".join(p for p in partes if p)


def _puntuar(texto: str) -> float:
    """Cuanto se parece a una explicacion de trabajo hecho.

    Deliberadamente simple y deterministico: cuenta señales lexicas. No decide
    nada, solo ordena los candidatos que vera la persona.
    """
    bajo = texto.lower()
    return sum(1.0 for s in SEÑALES if s in bajo) + len(texto) / 4000.0


def parse(path: Path, *, role: str = "assistant") -> Transcript:
    t = Transcript(path=path)
    with path.open(encoding="utf-8", errors="replace") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            try:
                d = json.loads(linea)
            except json.JSONDecodeError:
                continue

            t.cwd = d.get("cwd") or t.cwd
            t.session_id = d.get("sessionId") or t.session_id
            t.branch = d.get("gitBranch") or t.branch
            ts = d.get("timestamp", "")
            if ts:
                t.started = t.started or ts
                t.ended = ts

            if d.get("type") != role or d.get("isSidechain"):
                continue
            texto = _texto_de(d.get("message") or {})
            if len(texto.strip()) < MIN_FRAGMENT:
                continue
            t.fragments.append(
                Fragment(text=texto.strip(), timestamp=ts, role=role,
                         score=_puntuar(texto))
            )
    return t


def find_for_repo(repo: Path | str, *, root: Path = CLAUDE_PROJECTS) -> list[Transcript]:
    """Transcripciones cuyo `cwd` cae dentro del repositorio.

    Se compara el cwd real que lleva dentro cada archivo, no el nombre de la
    carpeta, que no es estable.
    """
    if not root.exists():
        return []
    objetivo = str(Path(repo).resolve()).replace("\\", "/").lower()
    encontradas: list[Transcript] = []
    for archivo in root.glob("*/*.jsonl"):
        try:
            t = parse(archivo)
        except OSError:
            continue
        cwd = (t.cwd or "").replace("\\", "/").lower()
        if cwd and (cwd == objetivo or cwd.startswith(objetivo + "/")):
            encontradas.append(t)
    encontradas.sort(key=lambda t: t.ended, reverse=True)
    return encontradas


def candidates(
    transcript: Transcript,
    *,
    since: str = "",
    limit: int = 8,
) -> list[Fragment]:
    """Los fragmentos mas explicativos, opcionalmente desde una fecha."""
    corte = None
    if since:
        try:
            corte = datetime.fromisoformat(since)
        except ValueError:
            corte = None

    utiles = []
    for f in transcript.fragments:
        if corte is not None:
            cuando = f.when
            if cuando is not None:
                # Comparar sin zona horaria para no exigir que coincidan.
                if cuando.replace(tzinfo=None) < corte.replace(tzinfo=None):
                    continue
        utiles.append(f)

    utiles.sort(key=lambda f: -f.score)
    return utiles[:limit]
