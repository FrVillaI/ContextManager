"""Evento de tarea y sus evidencias (DEC-025).

Un `TaskEvent` es lo que el sistema sabe sobre un trabajo concreto. Su valor
esta en que **admite varias fuentes de evidencia** y conserva la procedencia de
cada fragmento por separado, de modo que mañana se puedan añadir descripciones
de PR, salida de terminal o resultados de tests sin rediseñar nada.

La separacion que sostiene todo el diseño:

    EVIDENCE     lo que alguien o algo *dijo* o *hizo*, con su origen
                 git, rationale de la IA externa, tests, nota del usuario
    INFERENCE    lo que un modelo *cree* a partir de esa evidencia
                 tipo del registro, titulo, resumen, bugs sospechados

Una justificacion de Claude o GPT es evidencia de primera clase: mejora mucho la
calidad de la propuesta. Pero **no promociona nada por si sola**. Sigue haciendo
falta que una persona verifique, igual que en DEC-023.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class EvidenceKind(str, Enum):
    GIT_COMMIT = "git_commit"
    GIT_DIFF = "git_diff"
    RATIONALE = "rationale"          # explicacion de quien hizo el trabajo
    TERMINAL = "terminal"
    PULL_REQUEST = "pull_request"
    ISSUE = "issue"
    TEST_RESULTS = "test_results"
    USER_NOTE = "user_note"


class EvidenceOrigin(str, Enum):
    GIT = "git"
    EXTERNAL_LLM = "external_llm"    # Claude, GPT u otra IA de pago
    USER = "user"
    CI = "ci"
    TOOL = "tool"


class Evidence(BaseModel):
    """Un fragmento de evidencia con su procedencia propia."""

    kind: EvidenceKind
    origin: EvidenceOrigin
    content: str = ""
    provider: str = ""               # anthropic, openai, github...
    model: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)
    captured_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def cite(self) -> str:
        detalle = f"/{self.provider}" if self.provider else ""
        detalle += f"/{self.model}" if self.model else ""
        return f"{self.origin.value}:{self.kind.value}{detalle}"

    @property
    def explains(self) -> bool:
        """Si este fragmento aporta una explicacion utilizable.

        Un mensaje de commit de cuatro palabras no explica nada; una
        justificacion de la IA que hizo el trabajo, normalmente si.
        """
        return len(self.content.strip()) >= 80


class Inference(BaseModel):
    """Algo que un modelo dedujo. Nunca es evidencia, por bien que suene."""

    kind: str                        # tipo, titulo, resumen, bug_sospechado...
    value: str
    basis: str = ""                  # sobre que evidencia se apoya
    by: str = ""                     # modelo que lo produjo


class TaskEvent(BaseModel):
    """Todo lo que se sabe de un trabajo, antes de decidir que se recuerda."""

    task_id: str
    project_id: str
    project: str = ""
    created_at: str = Field(default_factory=lambda: date.today().isoformat())
    commit: str = ""
    #: Sesion de desarrollo durante la que ocurrio, si la habia.
    #: Es correlacion temporal, no causal (DEC-029).
    session_id: str = ""

    evidence: list[Evidence] = Field(default_factory=list)

    # Derivado por regla fija de la evidencia. No interviene ningun modelo.
    files: list[str] = Field(default_factory=list)
    modules: list[str] = Field(default_factory=list)
    related: list[dict[str, str]] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)

    # Lo que el modelo local propone. Separado a proposito.
    inferences: list[Inference] = Field(default_factory=list)
    proposal: dict[str, Any] = Field(default_factory=dict)

    def evidence_of(self, kind: EvidenceKind) -> Evidence | None:
        return next((e for e in self.evidence if e.kind == kind), None)

    @property
    def has_explanation(self) -> bool:
        """Si alguna evidencia explica de verdad lo que se hizo.

        Es el criterio que decide la procedencia de la propuesta: sin
        explicacion, lo maximo a lo que puede aspirar es a INFERENCE.
        """
        return any(e.explains for e in self.evidence)

    @property
    def explanation_sources(self) -> list[str]:
        return [e.cite() for e in self.evidence if e.explains]

    def summary_line(self) -> str:
        fuentes = ", ".join(e.kind.value for e in self.evidence)
        return (f"{self.task_id}  {len(self.files)} archivos  "
                f"+{self.stats.get('insertions', 0)}/-{self.stats.get('deletions', 0)}  "
                f"[{fuentes}]")


# --------------------------------------------------------------------------
# Persistencia: un archivo por evento en el area de espera
# --------------------------------------------------------------------------

def events_dir(memory_root: Path | str, project_id: str) -> Path:
    carpeta = Path(memory_root) / project_id / "pending"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def save_event(event: TaskEvent, memory_root: Path | str) -> Path:
    destino = events_dir(memory_root, event.project_id) / f"{event.task_id}.json"
    destino.write_text(
        json.dumps(event.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return destino


def load_events(memory_root: Path | str, project_id: str) -> list[TaskEvent]:
    carpeta = events_dir(memory_root, project_id)
    eventos = [
        TaskEvent.model_validate_json(f.read_text(encoding="utf-8"))
        for f in sorted(carpeta.glob("TASK-*.json"))
    ]
    return eventos


def load_event(memory_root: Path | str, project_id: str, task_id: str) -> TaskEvent | None:
    ruta = events_dir(memory_root, project_id) / f"{task_id}.json"
    if not ruta.exists():
        return None
    return TaskEvent.model_validate_json(ruta.read_text(encoding="utf-8"))


def drop_event(memory_root: Path | str, project_id: str, task_id: str) -> bool:
    ruta = events_dir(memory_root, project_id) / f"{task_id}.json"
    if ruta.exists():
        ruta.unlink()
        return True
    return False


def next_task_id(memory_root: Path | str, project_id: str) -> str:
    existentes = [
        int(f.stem.split("-")[1])
        for f in events_dir(memory_root, project_id).glob("TASK-*.json")
        if f.stem.split("-")[1].isdigit()
    ]
    return f"TASK-{max(existentes, default=0) + 1:03d}"
