"""Persistencia de la memoria en JSONL (DEC-002).

Un archivo por tipo de memoria. Este modulo es la unica puerta de escritura:
el grafo se alimenta siempre *desde* aqui, nunca al reves.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from .models import MemoryRecord

#: Nombre de archivo por tipo de memoria (seccion 7 de la especificacion).
FILES: dict[str, str] = {
    "project": "projects.jsonl",
    "bug": "bugs.jsonl",
    "decision": "decisions.jsonl",
    "constraint": "constraints.jsonl",
    "solution": "solutions.jsonl",
    "change": "changes.jsonl",
}


class MemoryStore:
    """Memoria de UN proyecto (DEC-018).

    Cada proyecto vive en `memory/<project_id>/`. El aislamiento es fisico, no
    un filtro que se pueda olvidar aplicar: una consulta sobre BackupCenter no
    puede alcanzar un bug del proyecto piloto porque ni siquiera lee ese directorio.
    """

    def __init__(self, root: Path | str, project_id: str) -> None:
        if not project_id:
            raise ValueError("un almacen de memoria pertenece siempre a un proyecto")
        self.project_id = project_id
        self.root = Path(root) / project_id
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, type_: str) -> Path:
        try:
            return self.root / FILES[type_]
        except KeyError:
            raise ValueError(f"tipo de memoria desconocido: {type_}") from None

    def append(self, record: MemoryRecord) -> None:
        """Añade un registro. Rechaza ids duplicados dentro de su tipo."""
        if record.project_id != self.project_id:
            raise ValueError(
                f"{record.uid} no pertenece al proyecto '{self.project_id}'"
            )
        existing = {r.id for r in self.read(record.type)}
        if record.id in existing:
            raise ValueError(f"id duplicado: {record.id}")
        line = record.model_dump_json(exclude_defaults=False)
        with self.path_for(record.type).open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def read(self, type_: str) -> list[MemoryRecord]:
        path = self.path_for(type_)
        if not path.exists():
            return []
        out: list[MemoryRecord] = []
        with path.open(encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(MemoryRecord.model_validate_json(line))
                except Exception as exc:
                    raise ValueError(f"{path.name}:{n} invalido -> {exc}") from None
        return out

    def all(self) -> Iterator[MemoryRecord]:
        for type_ in FILES:
            yield from self.read(type_)

    def by_id(self, record_id: str) -> MemoryRecord | None:
        return next((r for r in self.all() if r.id == record_id), None)

    def check(self) -> list[str]:
        """Valida el conjunto completo. Devuelve la lista de problemas."""
        records = list(self.all())
        ids = {r.id for r in records}
        problems: list[str] = []
        seen: set[str] = set()
        for r in records:
            if r.id in seen:
                problems.append(f"{r.id}: id repetido entre tipos distintos")
            seen.add(r.id)
            for link in r.links:
                if link.target not in ids:
                    problems.append(
                        f"{r.id}: enlace '{link.rel}' apunta a '{link.target}', que no existe"
                    )
        return problems

    def stats(self) -> dict[str, int]:
        return {t: len(self.read(t)) for t in FILES}


def all_projects(root: Path | str) -> list[str]:
    """Proyectos con memoria en disco."""
    raiz = Path(root)
    if not raiz.exists():
        return []
    return sorted(d.name for d in raiz.iterdir() if d.is_dir())
