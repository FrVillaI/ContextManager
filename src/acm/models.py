"""Esquema de la memoria del proyecto.

Los objetos de este modulo son la *fuente de verdad* de la memoria (DEC-002).
Se serializan a JSONL versionado en git; el grafo es un indice reconstruible.

Regla central (seccion 15 de la especificacion): nada asciende a FACT solo
porque un modelo lo haya generado. La procedencia es obligatoria y explicita.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Provenance(str, Enum):
    """De donde viene la afirmacion y cuanto se puede confiar en ella."""

    FACT = "FACT"            # confirmado contra el codigo, el repo o el usuario
    INFERENCE = "INFERENCE"  # deducido por un modelo, sin confirmar
    PROPOSAL = "PROPOSAL"    # propuesta que aun no se ha implementado
    DECISION = "DECISION"    # decision aceptada explicitamente
    RESOLVED = "RESOLVED"    # problema confirmado como solucionado


#: Solo estas procedencias pueden entrar en el contexto que se envia a la IA de
#: pago como afirmacion. El resto viaja marcado, o no viaja.
TRUSTED: frozenset[Provenance] = frozenset(
    {Provenance.FACT, Provenance.DECISION, Provenance.RESOLVED}
)


class Stage(str, Enum):
    """Escalera de confianza de la observacion post-tarea (DEC-023).

    Solo VERIFIED entra en la memoria canonica. Los tres anteriores viven en el
    area de espera y no participan en ninguna recuperacion.
    """

    OBSERVED = "OBSERVED"      # evidencia bruta del repositorio
    EXTRACTED = "EXTRACTED"    # estructura derivada por regla fija
    PROPOSED = "PROPOSED"      # interpretacion del modelo local
    VERIFIED = "VERIFIED"      # confirmado por una persona


#: Orden de la escalera, para comprobar que nunca se salta un peldaño hacia
#: arriba sin pasar por la verificacion humana.
STAGE_ORDER: list[Stage] = [
    Stage.OBSERVED, Stage.EXTRACTED, Stage.PROPOSED, Stage.VERIFIED
]


class SourceKind(str, Enum):
    GIT_COMMIT = "git_commit"
    GIT_DIFF = "git_diff"
    FILE = "file"
    USER = "user"
    LLM = "llm"


class Source(BaseModel):
    """Rastro verificable de donde salio la memoria."""

    kind: SourceKind
    ref: str                      # sha del commit, ruta del archivo, o modelo
    detail: str | None = None

    def cite(self) -> str:
        return f"{self.kind.value}:{self.ref}"


class Link(BaseModel):
    """Arista del grafo. El campo `rel` es el nombre de la relacion."""

    rel: str                      # afecta, causado_por, solucionado_con, ...
    target: str                   # id de otro registro de memoria

    @field_validator("rel")
    @classmethod
    def _snake(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "_")


class MemoryRecord(BaseModel):
    """Envoltura comun a todos los tipos de memoria.

    La identidad real de un registro es `project_id + id`, no `id` a secas: dos
    proyectos distintos pueden tener cada uno su BUG-001 sin colisionar. Ver
    DEC-018.
    """

    id: str                       # BUG-001, ADR-004, CONSTRAINT-002, ...
    type: Literal["project", "bug", "decision", "constraint", "solution", "change"]
    project_id: str               # identificador estable, en minusculas
    project: str = ""             # nombre legible; vacio = usar project_id
    title: str
    provenance: Provenance
    source: Source
    created_at: date
    #: Peldaño de la escalera de DEC-023. Los registros sembrados a mano o
    #: extraidos con evidencia explicita nacen ya VERIFIED.
    stage: Stage = Stage.VERIFIED
    summary: str = ""
    modules: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    body: dict = Field(default_factory=dict)

    @property
    def uid(self) -> str:
        """Identidad global del registro."""
        return f"{self.project_id}/{self.id}"

    @property
    def display_project(self) -> str:
        return self.project or self.project_id

    @property
    def canonical(self) -> bool:
        """True si puede vivir en la memoria canonica del proyecto."""
        return self.stage == Stage.VERIFIED

    @property
    def trusted(self) -> bool:
        """True si puede presentarse a la IA de pago como afirmacion."""
        return self.canonical and self.provenance in TRUSTED

    def to_context_line(self) -> str:
        """Representacion compacta para el Context Builder."""
        mark = "" if self.trusted else f" [{self.provenance.value}]"
        return f"{self.id}{mark}: {self.title}"
