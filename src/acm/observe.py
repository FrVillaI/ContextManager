"""Observacion post-tarea: convertir trabajo real en memoria (DEC-023).

Es la mitad que faltaba del ciclo. Hasta ahora toda la memoria entraba por
siembra manual o por extraccion del historial; aqui el sistema mira lo que acaba
de pasar en el repositorio y propone que se aprendio.

La disciplina es la misma que en DEC-013, aplicada al otro extremo:

    OBSERVED     lo que dice git. Verificable, no opinable.
    EXTRACTED    estructura derivada por regla fija: modulos, relaciones por
                 archivo compartido con la memoria existente.
    PROPOSED     lo que el modelo local cree que ocurrio. Nunca canonico.
    VERIFIED     lo que una persona confirmo.

Un commit que dice `fix cosas` produce un OBSERVED perfectamente valido y un
PROPOSED muy pobre. Eso es correcto: el sistema no puede saber mas de lo que la
evidencia dice.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import httpx

from .events import Evidence, EvidenceKind, EvidenceOrigin, Inference, TaskEvent
from .models import MemoryRecord, Provenance, Source, SourceKind, Stage

OLLAMA_CHAT = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL = "llama3.2:3b"

IGNORAR = re.compile(
    r"\.(png|jpe?g|gif|mp4|zip|rar|ico|webp|ttf|otf|pdf|docx|lock)$"
    r"|(^|/)(node_modules|dist|build|bin|obj)/",
    re.IGNORECASE,
)

RAICES = {"mobile", "web", "backend", "docs", "scripts", "design", "src", "tests", "tools"}

TIPOS = ["bug", "solution", "decision", "constraint", "change"]


# --------------------------------------------------------------------------
# OBSERVED — lo que dice git
# --------------------------------------------------------------------------

@dataclass
class Observation:
    """Evidencia bruta. Todo lo de aqui se puede comprobar contra el repositorio."""

    repo: Path
    ref: str                       # sha del commit, o 'worktree'
    subject: str = ""
    body: str = ""
    when: str = ""
    files: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0

    @property
    def empty(self) -> bool:
        return not self.files

    def describe(self) -> str:
        return (f"{len(self.files)} archivos, +{self.insertions}/-{self.deletions} "
                f"({self.ref})")


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return out.stdout


def _contar(repo: Path, *args: str) -> tuple[int, int]:
    ins = dele = 0
    for linea in _git(repo, *args).splitlines():
        partes = linea.split("\t")
        if len(partes) == 3:
            ins += int(partes[0]) if partes[0].isdigit() else 0
            dele += int(partes[1]) if partes[1].isdigit() else 0
    return ins, dele


def observe_commit(repo: Path | str, ref: str = "HEAD") -> Observation:
    """OBSERVED a partir de un commit concreto."""
    repo = Path(repo)
    cabecera = _git(repo, "show", "-s", "--format=%H%n%ad%n%s%n%b", "--date=short", ref)
    lineas = cabecera.splitlines()
    if not lineas:
        return Observation(repo=repo, ref=ref)

    archivos = [
        f.strip() for f in _git(repo, "show", "--name-only", "--format=", ref).splitlines()
        if f.strip() and not IGNORAR.search(f.strip())
    ]
    ins, dele = _contar(repo, "show", "--numstat", "--format=", ref)
    return Observation(
        repo=repo,
        ref=lineas[0][:7],
        when=lineas[1] if len(lineas) > 1 else "",
        subject=lineas[2] if len(lineas) > 2 else "",
        body="\n".join(lineas[3:]).strip(),
        files=archivos,
        insertions=ins, deletions=dele,
    )


def observe_worktree(repo: Path | str) -> Observation:
    """OBSERVED del trabajo aun sin confirmar. Es el caso normal justo despues
    de que Claude o GPT hayan tocado el codigo."""
    repo = Path(repo)
    archivos = sorted({
        linea[3:].strip().strip('"')
        for linea in _git(repo, "status", "--porcelain").splitlines()
        if linea and not IGNORAR.search(linea[3:].strip())
    })
    ins, dele = _contar(repo, "diff", "--numstat", "HEAD")
    return Observation(
        repo=repo, ref="worktree", when=date.today().isoformat(),
        subject="", body="", files=archivos, insertions=ins, deletions=dele,
    )


# --------------------------------------------------------------------------
# EXTRACTED — estructura derivada por regla fija
# --------------------------------------------------------------------------

@dataclass
class Extraction:
    modules: list[str] = field(default_factory=list)
    related: list[tuple[str, str]] = field(default_factory=list)  # (record_id, evidencia)

    def describe(self) -> str:
        rel = ", ".join(f"{r} ({e})" for r, e in self.related[:3]) or "ninguna"
        return f"modulos: {', '.join(self.modules) or '-'} | relacionado con: {rel}"


def modules_from(files: list[str]) -> list[str]:
    mods: list[str] = []
    for f in files:
        partes = f.replace("\\", "/").split("/")
        raiz = partes[0]
        if raiz not in RAICES or len(partes) < 2:
            continue
        stem = Path(partes[-1]).stem
        mod = f"{raiz}/{stem}" if stem else raiz
        if mod not in mods:
            mods.append(mod)
    return mods[:8]


def extract(observation: Observation, memoria: list[MemoryRecord]) -> Extraction:
    """EXTRACTED. Las relaciones salen de archivos compartidos con la memoria
    existente, no de similitud semantica: DEC-013 sigue vigiendo aqui."""
    tocados = set(observation.files)
    relacionados: list[tuple[str, float, str]] = []
    for record in memoria:
        comunes = tocados & set(record.files)
        if comunes:
            muestra = ", ".join(sorted(comunes)[:2])
            relacionados.append((record.id, len(comunes), f"comparte {muestra}"))
    relacionados.sort(key=lambda r: -r[1])
    return Extraction(
        modules=modules_from(observation.files),
        related=[(rid, ev) for rid, _, ev in relacionados[:5]],
    )


# --------------------------------------------------------------------------
# PROPOSED — lo que el modelo local cree
# --------------------------------------------------------------------------

PROMPT = """Un desarrollador acaba de terminar un trabajo. Esta es TODA la
evidencia disponible:

{evidencia}

Archivos modificados ({n}):
{files}
Modulos afectados: {modules}

Resume QUE se hizo y, si la evidencia lo permite, POR QUE. Basate unicamente en
la evidencia mostrada. Si nada la explica, dilo en el resumen en lugar de
inventar una explicacion."""

SYSTEM = (
    "Analizas cambios de codigo y los resumes con honestidad. Nunca afirmas mas "
    "de lo que la evidencia permite. Si no hay informacion suficiente para saber "
    "que problema se resolvio, lo dices explicitamente."
)


@dataclass
class Proposal:
    type: str = "change"
    title: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    confidence: str = "baja"
    model: str = DEFAULT_MODEL
    error: str = ""


def render_evidence(event: TaskEvent) -> str:
    """Presenta cada fragmento con su origen, para que el modelo no confunda
    una explicacion de la IA que hizo el trabajo con un mensaje de commit."""
    bloques: list[str] = []
    for e in event.evidence:
        if not e.content.strip():
            continue
        etiqueta = {
            EvidenceKind.GIT_COMMIT: "Mensaje del commit",
            EvidenceKind.RATIONALE: "Explicacion de quien hizo el trabajo",
            EvidenceKind.TERMINAL: "Salida de terminal",
            EvidenceKind.PULL_REQUEST: "Descripcion del pull request",
            EvidenceKind.ISSUE: "Issue asociado",
            EvidenceKind.TEST_RESULTS: "Resultado de los tests",
            EvidenceKind.USER_NOTE: "Nota del desarrollador",
        }.get(e.kind, e.kind.value)
        procedencia = f" [{e.cite()}]"
        bloques.append(f"--- {etiqueta}{procedencia}\n{e.content.strip()[:3000]}")
    return "\n\n".join(bloques) or "(no hay ninguna evidencia textual)"


def propose(
    event: TaskEvent,
    *,
    model: str = DEFAULT_MODEL,
    timeout: float = 240.0,
) -> Proposal:
    """PROPOSED. Salida restringida por esquema; jamas canonica."""
    schema = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": TIPOS},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "string", "enum": ["alta", "media", "baja"]},
        },
        "required": ["type", "title", "summary", "confidence"],
    }
    contenido = PROMPT.format(
        evidencia=render_evidence(event),
        n=len(event.files),
        files="\n".join(f"  {f}" for f in event.files[:15]),
        modules=", ".join(event.modules) or "(ninguno reconocible)",
    )
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            resp = client.post(OLLAMA_CHAT, json={
                "model": model, "stream": False, "format": schema,
                "options": {"temperature": 0},
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": contenido},
                ],
            })
            resp.raise_for_status()
            datos = json.loads(resp.json()["message"]["content"])
    except Exception as exc:  # noqa: BLE001
        return Proposal(error=str(exc)[:160], model=model)

    return Proposal(
        type=datos.get("type", "change"),
        title=str(datos.get("title", ""))[:150],
        summary=str(datos.get("summary", ""))[:800],
        tags=[str(t) for t in datos.get("tags", [])][:6],
        confidence=datos.get("confidence", "baja"),
        model=model,
    )


# --------------------------------------------------------------------------
# Ensamblado
# --------------------------------------------------------------------------

def build_event(
    observation: Observation,
    extraction: Extraction,
    *,
    task_id: str,
    project_id: str,
    project: str,
    extra_evidence: list[Evidence] | None = None,
) -> TaskEvent:
    """Ensambla el evento: evidencias por un lado, derivacion por otro."""
    evidencias: list[Evidence] = []

    if observation.subject or observation.body:
        evidencias.append(Evidence(
            kind=EvidenceKind.GIT_COMMIT,
            origin=EvidenceOrigin.GIT,
            content="\n".join(x for x in (observation.subject, observation.body) if x),
            meta={"ref": observation.ref, "when": observation.when},
        ))
    evidencias.append(Evidence(
        kind=EvidenceKind.GIT_DIFF,
        origin=EvidenceOrigin.GIT,
        content="",
        meta={
            "archivos": len(observation.files),
            "insertions": observation.insertions,
            "deletions": observation.deletions,
        },
    ))
    evidencias.extend(extra_evidence or [])

    return TaskEvent(
        task_id=task_id, project_id=project_id, project=project,
        created_at=observation.when or date.today().isoformat(),
        commit="" if observation.ref == "worktree" else observation.ref,
        evidence=evidencias,
        files=observation.files[:20],
        modules=extraction.modules,
        related=[{"id": rid, "evidencia": ev} for rid, ev in extraction.related],
        stats={
            "archivos": len(observation.files),
            "insertions": observation.insertions,
            "deletions": observation.deletions,
        },
    )


def attach_proposal(event: TaskEvent, proposal: Proposal) -> TaskEvent:
    """Guarda la propuesta como inferencias trazables, no como hechos."""
    base = ", ".join(event.explanation_sources) or "solo rutas de archivo"
    event.inferences = [
        Inference(kind=campo, value=str(valor), basis=base, by=proposal.model)
        for campo, valor in (
            ("tipo", proposal.type),
            ("titulo", proposal.title),
            ("resumen", proposal.summary),
            ("etiquetas", ", ".join(proposal.tags)),
            ("confianza_declarada", proposal.confidence),
        ) if valor
    ]
    event.proposal = {
        "type": proposal.type, "title": proposal.title,
        "summary": proposal.summary, "tags": proposal.tags,
        "model": proposal.model, "confidence": proposal.confidence,
        "error": proposal.error,
    }
    return event


def event_to_record(event: TaskEvent, record_id: str) -> MemoryRecord:
    """Convierte un evento en registro PENDIENTE, en stage PROPOSED.

    La procedencia depende de si ALGUNA evidencia explica el trabajo, venga de
    donde venga. Una justificacion de la IA externa cuenta igual que un mensaje
    de commit detallado: es evidencia, no adivinacion.
    """
    prop = event.proposal
    tipo = prop.get("type", "change")
    return MemoryRecord(
        id=record_id,
        type=tipo if tipo in TIPOS else "change",
        project_id=event.project_id, project=event.project,
        provenance=Provenance.PROPOSAL if event.has_explanation else Provenance.INFERENCE,
        stage=Stage.PROPOSED,
        title=prop.get("title") or f"Cambio en {event.commit or 'worktree'}",
        source=Source(
            kind=SourceKind.GIT_COMMIT if event.commit else SourceKind.GIT_DIFF,
            ref=event.commit or "worktree",
            detail="; ".join(event.explanation_sources) or "sin explicacion",
        ),
        created_at=event.created_at,
        summary=prop.get("summary", ""),
        modules=event.modules,
        files=event.files[:12],
        tags=prop.get("tags", []),
        body={
            "task_id": event.task_id,
            "evidencia": [e.cite() for e in event.evidence],
            "explican": event.explanation_sources,
            "relacionado_con": event.related,
            "inferencias": [i.model_dump() for i in event.inferences],
        },
    )
