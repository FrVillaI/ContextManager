"""Revision editable de propuestas (DEC-026).

Principio: **la salida del modelo nunca es memoria canonica, aunque este
respaldada por evidencia correcta.** `CHG-142` lo demostro: con la justificacion
de Claude delante, el modelo aun resumio «mostrar el numero exacto de clientes»
cuando el cambio devolvia *la lista* de clientes. La evidencia era buena; la
compresion la estropeo.

Por eso la ultima milla antes de canonicalizar es editable, y **editar no vuelve
a pasar por el modelo**: lo que escribe la persona es lo que queda.

Se conservan las dos versiones, nunca se sobrescribe una con otra:

    proposal      lo que creyo el modelo, y quien lo genero
    verification  lo que corrigio la persona, y que campos toco

Eso da trazabilidad —¿que creyo la IA? ¿que corrigio la persona? ¿que entro en
memoria?— y permite medir cuanto se equivoca el modelo al comprimir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .events import TaskEvent
from .models import MemoryRecord, Provenance, Source, Stage

#: Campos que una persona puede corregir antes de canonicalizar.
EDITABLES = ["type", "title", "summary", "tags", "modules", "related"]


@dataclass
class Draft:
    """Version editable de la propuesta. Empieza siendo lo que dijo el modelo."""

    type: str = "change"
    title: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)

    @classmethod
    def from_event(cls, event: TaskEvent) -> Draft:
        p = event.proposal
        return cls(
            type=p.get("type", "change"),
            title=p.get("title", ""),
            summary=p.get("summary", ""),
            tags=list(p.get("tags", [])),
            modules=list(event.modules),
            related=[r["id"] for r in event.related],
        )

    def as_dict(self) -> dict:
        return {
            "type": self.type, "title": self.title, "summary": self.summary,
            "tags": self.tags, "modules": self.modules, "related": self.related,
        }


def corrected_fields(original: Draft, editado: Draft) -> list[str]:
    """Que campos toco la persona. Es la base de las metricas de correccion."""
    a, b = original.as_dict(), editado.as_dict()
    return [campo for campo in EDITABLES if a[campo] != b[campo]]


def build_verified(
    event: TaskEvent,
    original: Draft,
    editado: Draft,
    record_id: str,
    *,
    verified_by: str = "human",
) -> MemoryRecord:
    """Ensambla el registro canonico conservando ambas versiones."""
    tocados = corrected_fields(original, editado)
    ahora = datetime.now().isoformat(timespec="seconds")

    return MemoryRecord(
        id=record_id,
        type=editado.type,
        project_id=event.project_id,
        project=event.project,
        stage=Stage.VERIFIED,
        provenance=Provenance.RESOLVED if editado.type in ("bug", "solution")
                   else Provenance.FACT,
        title=editado.title or f"Cambio en {event.commit or 'worktree'}",
        source=Source(
            kind=event.evidence[0].kind.value if event.evidence else "user",  # type: ignore[arg-type]
            ref=event.commit or "worktree",
            detail=(
                "; ".join(event.explanation_sources) or "sin explicacion"
            ) + f" | verificado por {verified_by} el {ahora[:10]}",
        ),
        created_at=event.created_at,
        summary=editado.summary,
        modules=editado.modules,
        files=event.files[:12],
        tags=editado.tags,
        body={
            "task_id": event.task_id,
            "evidencia": [e.cite() for e in event.evidence],
            "explican": event.explanation_sources,
            "relacionado_con": [
                r for r in event.related if r["id"] in editado.related
            ],
            # Las dos versiones, nunca una sobre la otra.
            "proposal": {
                **original.as_dict(),
                "generated_by": event.proposal.get("model", "?"),
                "confidence_declared": event.proposal.get("confidence", "?"),
            },
            "verification": {
                **editado.as_dict(),
                "verified_by": verified_by,
                "verified_at": ahora,
                "corrected_fields": tocados,
                "accepted_as_is": not tocados,
            },
        },
    )


# --------------------------------------------------------------------------
# Metricas de correccion (DEC-026)
# --------------------------------------------------------------------------

@dataclass
class CorrectionStats:
    verificadas: int = 0
    con_correccion: int = 0
    por_campo: dict[str, int] = field(default_factory=dict)

    @property
    def proposal_correction_rate(self) -> float:
        return self.con_correccion / self.verificadas if self.verificadas else 0.0

    def field_rate(self, campo: str) -> float:
        return self.por_campo.get(campo, 0) / self.verificadas if self.verificadas else 0.0


def correction_stats(records: list[MemoryRecord]) -> CorrectionStats:
    """Cuanto corrige la persona al modelo, en conjunto y por campo.

    Un 1/100 de propuestas corregidas no es lo mismo que 100/100 con un solo
    campo menor tocado, asi que se miden ambas cosas.
    """
    stats = CorrectionStats()
    for r in records:
        verificacion = r.body.get("verification")
        if not isinstance(verificacion, dict):
            continue
        stats.verificadas += 1
        tocados = verificacion.get("corrected_fields", [])
        if tocados:
            stats.con_correccion += 1
        for campo in tocados:
            stats.por_campo[campo] = stats.por_campo.get(campo, 0) + 1
    return stats
