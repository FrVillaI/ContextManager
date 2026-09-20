"""Sesion de desarrollo y captura de justificacion (DEC-029).

El sistema no se diseña alrededor de Claude. La abstraccion es la **sesion de
desarrollo**, y la justificacion es un fragmento de evidencia con su origen
declarado. Mañana puede venir de GPT, Cursor, Copilot, Gemini, del terminal o de
una persona escribiendo a mano, y el Context Manager no necesita saber quien la
produjo.

    SESION
      ├── rationale   (fragmentos, con su origen)
      ├── commits     (los que ocurrieron durante su ventana)
      └── transcript  (referencia para auditoria, NO memoria)

Correlacion temporal, no causal
-------------------------------
El sistema sabe que un rationale existia *antes* de unos commits. Eso es
**evidencia temporal**, no una relacion causal. La distincion importa: es la
misma disciplina que evito contaminar el grafo con relaciones inventadas.

Nunca se afirma «este rationale causo este commit», solo «ocurrieron durante la
misma sesion».

Que NO se guarda
----------------
La conversacion completa no entra en memoria. Guardarla convertiria el sistema en
un almacen gigante de conversaciones, que es justo lo que la especificacion
original descartaba. Solo entra el **rationale**: la explicacion del cambio. Si
se quiere conservar la conversacion para auditoria, se guarda su ruta como
referencia y nunca se carga como evidencia.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from .events import Evidence, EvidenceKind, EvidenceOrigin

SESSIONS_DIR = "sessions"

#: De donde puede venir una justificacion. La lista es abierta a proposito: el
#: valor se guarda tal cual y no condiciona ninguna logica.
ORIGENES = {
    "claude": EvidenceOrigin.EXTERNAL_LLM,
    "gpt": EvidenceOrigin.EXTERNAL_LLM,
    "gemini": EvidenceOrigin.EXTERNAL_LLM,
    "copilot": EvidenceOrigin.EXTERNAL_LLM,
    "cursor": EvidenceOrigin.EXTERNAL_LLM,
    "human": EvidenceOrigin.USER,
    "terminal": EvidenceOrigin.TOOL,
    "ci": EvidenceOrigin.CI,
}


class RationaleFragment(BaseModel):
    """Un trozo de explicacion, con su procedencia propia."""

    content: str
    source: str = "human"            # claude, gpt, cursor, human, terminal...
    provider: str = ""
    model: str = ""
    captured_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    @property
    def origin(self) -> EvidenceOrigin:
        return ORIGENES.get(self.source.lower(), EvidenceOrigin.TOOL)

    def to_evidence(self) -> Evidence:
        return Evidence(
            kind=EvidenceKind.RATIONALE,
            origin=self.origin,
            content=self.content,
            provider=self.provider or self.source,
            model=self.model,
            captured_at=self.captured_at,
            meta={"source": self.source},
        )


class Session(BaseModel):
    session_id: str
    project_id: str
    started_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    ended_at: str = ""
    head_at_start: str = ""
    goal: str = ""
    rationale: list[RationaleFragment] = Field(default_factory=list)
    commits: list[str] = Field(default_factory=list)
    #: Solo una referencia para auditoria. Nunca se carga como evidencia.
    transcript_ref: str = ""

    @property
    def open(self) -> bool:
        return not self.ended_at

    def evidence(self) -> list[Evidence]:
        return [f.to_evidence() for f in self.rationale]

    def temporal_note(self, commit: str) -> Evidence:
        """Correlacion temporal explicita, redactada para no sonar causal."""
        return Evidence(
            kind=EvidenceKind.USER_NOTE,
            origin=EvidenceOrigin.TOOL,
            content=(
                f"Este commit ({commit}) ocurrio durante {self.session_id}, "
                f"abierta el {self.started_at}. La justificacion adjunta es "
                f"anterior a el. Es correlacion temporal, no una afirmacion de "
                f"que la causara."
            ),
            meta={"session_id": self.session_id, "correlacion": "temporal"},
        )

    def describe(self) -> str:
        estado = "abierta" if self.open else "cerrada"
        return (f"{self.session_id}  [{estado}]  "
                f"{len(self.rationale)} rationale, {len(self.commits)} commits"
                + (f"  — {self.goal[:40]}" if self.goal else ""))


# --------------------------------------------------------------------------
# Persistencia dentro del repositorio gestionado
# --------------------------------------------------------------------------

def sessions_dir(repo: Path | str) -> Path:
    carpeta = Path(repo) / ".context" / SESSIONS_DIR
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def save(session: Session, repo: Path | str) -> Path:
    destino = sessions_dir(repo) / f"{session.session_id}.json"
    destino.write_text(
        json.dumps(session.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return destino


def load_all(repo: Path | str) -> list[Session]:
    return [
        Session.model_validate_json(f.read_text(encoding="utf-8"))
        for f in sorted(sessions_dir(repo).glob("SESSION-*.json"))
    ]


def load(repo: Path | str, session_id: str) -> Session | None:
    ruta = sessions_dir(repo) / f"{session_id}.json"
    if not ruta.exists():
        return None
    return Session.model_validate_json(ruta.read_text(encoding="utf-8"))


def open_session(repo: Path | str) -> Session | None:
    """La sesion abierta, si la hay. Solo puede haber una."""
    abiertas = [s for s in load_all(repo) if s.open]
    return abiertas[-1] if abiertas else None


def next_session_id(repo: Path | str) -> str:
    usados = [
        int(f.stem.split("-")[1])
        for f in sessions_dir(repo).glob("SESSION-*.json")
        if f.stem.split("-")[1].isdigit()
    ]
    return f"SESSION-{max(usados, default=0) + 1:03d}"


def git_head(repo: Path | str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    )
    return out.stdout.strip()
