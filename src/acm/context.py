"""Context Builder (seccion 12 de la especificacion, DEC-004).

Produce el bloque de texto que se pega en Claude o GPT. Su exito NO se mide por
cobertura sino por reduccion: si esto envia mucho, el proyecto fallo su proposito.

Dos reglas heredadas del esquema:

- Nada que no sea `FACT`, `DECISION` o `RESOLVED` se presenta como afirmacion;
  lo demas viaja marcado con su procedencia (DEC-009).
- Las relaciones mostradas llevan su evidencia, porque ninguna viene de
  inferencia del modelo (DEC-013).
"""

from __future__ import annotations

from dataclasses import dataclass

from .intent import Intent
from .models import MemoryRecord
from .retrieval import Hit

#: Orden de presentacion. Las restricciones van primero porque son lo unico que
#: puede invalidar una solucion entera.
SECTION_ORDER = [
    ("constraint", "RESTRICCIONES QUE NO SE PUEDEN ROMPER"),
    ("decision", "DECISIONES VIGENTES"),
    ("bug", "PROBLEMAS ANTERIORES EN ESTA ZONA"),
    ("solution", "SOLUCIONES QUE YA FUNCIONARON"),
    ("project", "CONTEXTO DEL PROYECTO"),
]


@dataclass
class Context:
    text: str
    hits: list[Hit]
    intent: Intent

    @property
    def chars(self) -> int:
        return len(self.text)

    def savings(self, records: list[MemoryRecord]) -> tuple[int, float]:
        """Cuanto se ahorra frente a mandar la memoria entera."""
        total = sum(len(r.title) + len(r.summary) for r in records)
        if not total:
            return 0, 0.0
        return total, 100.0 * (1 - self.chars / total)


def _files(hits: list[Hit]) -> list[str]:
    vistos: list[str] = []
    for hit in hits:
        for f in hit.record.files:
            if f not in vistos:
                vistos.append(f)
    return vistos


def build(
    query: str,
    hits: list[Hit],
    intent: Intent,
    *,
    project: str = "",
) -> Context:
    if not hits:
        texto = (
            "No hay memoria registrada relevante para esta tarea.\n"
            "Tratala como territorio nuevo y registra lo que aprendas al terminar."
        )
        return Context(texto, hits, intent)

    proyecto = project or hits[0].record.display_project
    lineas: list[str] = [
        f"PROYECTO: {proyecto}",
        f"TAREA: {query.strip()}",
        f"INTENCION DETECTADA: {intent.intent}",
    ]
    if intent.modules:
        lineas.append(f"MODULOS IMPLICADOS: {', '.join(intent.modules)}")

    # Distinguir "hay precedentes" de "solo hay reglas generales del area" es
    # importante: presentar lo segundo como lo primero seria enganar.
    if not any(h.direct for h in hits):
        lineas.append("")
        lineas.append(
            "SIN PRECEDENTES REGISTRADOS: no hay bugs, decisiones ni soluciones "
            "previas sobre esta tarea. Lo que sigue son las reglas vigentes del "
            "area, no experiencia acumulada sobre este problema."
        )

    por_tipo: dict[str, list[Hit]] = {}
    for hit in hits:
        por_tipo.setdefault(hit.record.type, []).append(hit)

    for tipo, titulo in SECTION_ORDER:
        grupo = por_tipo.get(tipo)
        if not grupo:
            continue
        lineas.append("")
        lineas.append(titulo)
        for hit in grupo:
            r = hit.record
            marca = "" if r.trusted else f"  <-- {r.provenance.value}, SIN CONFIRMAR"
            lineas.append(f"  [{r.id}] {r.title}{marca}")
            if r.summary:
                lineas.append(f"      {r.summary}")
            if not hit.direct:
                lineas.append(f"      (relacionado: {hit.why()})")

    archivos = _files(hits)
    if archivos:
        lineas.append("")
        lineas.append("ARCHIVOS QUE TOCARON ESTOS PRECEDENTES")
        lineas.extend(f"  {f}" for f in archivos)

    dudosos = [h.record.id for h in hits if not h.record.trusted]
    if dudosos:
        lineas.append("")
        lineas.append(
            f"AVISO: {', '.join(dudosos)} no estan confirmados. Tratalos como "
            "hipotesis, no como hechos."
        )

    return Context("\n".join(lineas), hits, intent)
