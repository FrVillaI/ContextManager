"""Recuperacion semantica como via de descubrimiento (DEC-020).

Los embeddings entran por la misma puerta que las palabras clave del modelo
local: **pueden proponer candidatos, no pueden afirmar nada**. En concreto:

1. añaden candidatos al conjunto;
2. una similitud alta NO crea una arista del grafo;
3. un resultado vectorial no se presenta automaticamente como precedente;
4. los candidatos semanticos pasan por la misma clasificacion que el resto;
5. si nada supera el umbral final, se sigue respondiendo SIN PRECEDENTES.

El indice se guarda por proyecto en `memory/<project_id>/.vectors.json`, junto a
la huella del contenido de cada registro para saber cuando hay que recalcularlo.
El vector es un indice reconstruible, igual que el grafo: la fuente de verdad
sigue siendo el JSONL (DEC-002).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

from .models import MemoryRecord

OLLAMA_EMBED = os.getenv("ACM_OLLAMA_EMBED", "http://127.0.0.1:11434/api/embed")
EMBED_MODEL = "nomic-embed-text"
INDEX_FILE = ".vectors.json"


def _texto(record: MemoryRecord) -> str:
    """Lo que se vectoriza de un registro."""
    partes = [record.title, record.summary]
    if record.tags:
        partes.append(" ".join(record.tags))
    if record.modules:
        partes.append(" ".join(record.modules))
    return "\n".join(p for p in partes if p)[:2000]


def _huella(record: MemoryRecord) -> str:
    return hashlib.sha1(_texto(record).encode("utf-8")).hexdigest()[:16]


def embed(textos: list[str], *, model: str = EMBED_MODEL, timeout: float = 300.0) -> list[list[float]]:
    """Pide embeddings a Ollama. Lanza si falla: el llamante decide que hacer."""
    with httpx.Client(timeout=timeout, trust_env=False) as client:
        resp = client.post(OLLAMA_EMBED, json={"model": model, "input": textos})
        resp.raise_for_status()
        return resp.json()["embeddings"]


def _normalizar(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _coseno(a: list[float], b: list[float]) -> float:
    """Ambos vectores llegan normalizados, asi que basta el producto escalar."""
    return sum(x * y for x, y in zip(a, b))


@dataclass
class SemanticIndex:
    project_id: str
    vectors: dict[str, list[float]]
    fingerprints: dict[str, str]
    model: str = EMBED_MODEL

    @property
    def size(self) -> int:
        return len(self.vectors)

    def search(self, query: str, *, top_k: int = 12) -> list[tuple[str, float]]:
        """Devuelve (record_id, similitud) ordenado. Sin umbral: eso lo decide
        quien fusiona, porque una similitud coseno no es evidencia por si sola."""
        if not self.vectors:
            return []
        q = _normalizar(embed([query])[0])
        puntuados = [(rid, _coseno(q, v)) for rid, v in self.vectors.items()]
        puntuados.sort(key=lambda p: -p[1])
        return puntuados[:top_k]


def index_path(memory_root: Path | str, project_id: str) -> Path:
    return Path(memory_root) / project_id / INDEX_FILE


def build_index(
    records: list[MemoryRecord],
    memory_root: Path | str,
    project_id: str,
    *,
    batch: int = 16,
    verbose: bool = False,
) -> SemanticIndex:
    """Construye o actualiza el indice. Solo recalcula lo que cambio."""
    destino = index_path(memory_root, project_id)
    vectors: dict[str, list[float]] = {}
    fingerprints: dict[str, str] = {}

    if destino.exists():
        datos = json.loads(destino.read_text(encoding="utf-8"))
        if datos.get("model") == EMBED_MODEL:
            vectors = datos.get("vectors", {})
            fingerprints = datos.get("fingerprints", {})

    pendientes = [r for r in records if fingerprints.get(r.id) != _huella(r)]
    vigentes = {r.id for r in records}
    for obsoleto in set(vectors) - vigentes:
        vectors.pop(obsoleto, None)
        fingerprints.pop(obsoleto, None)

    if verbose and pendientes:
        print(f"  vectorizando {len(pendientes)} de {len(records)} registros...")

    for i in range(0, len(pendientes), batch):
        lote = pendientes[i:i + batch]
        salida = embed([_texto(r) for r in lote])
        for record, vector in zip(lote, salida):
            vectors[record.id] = _normalizar(vector)
            fingerprints[record.id] = _huella(record)
        if verbose:
            print(f"    {min(i + batch, len(pendientes))}/{len(pendientes)}", flush=True)

    destino.write_text(
        json.dumps(
            {"model": EMBED_MODEL, "vectors": vectors, "fingerprints": fingerprints},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return SemanticIndex(project_id, vectors, fingerprints)


def load_index(memory_root: Path | str, project_id: str) -> SemanticIndex | None:
    destino = index_path(memory_root, project_id)
    if not destino.exists():
        return None
    datos = json.loads(destino.read_text(encoding="utf-8"))
    return SemanticIndex(
        project_id, datos.get("vectors", {}), datos.get("fingerprints", {}),
        datos.get("model", EMBED_MODEL),
    )


# --------------------------------------------------------------------------
# Fusion
# --------------------------------------------------------------------------

#: Constante clasica de RRF. Amortigua el peso de las primeras posiciones para
#: que una lista no domine a la otra solo por tener puntuaciones mas altas.
RRF_K = 60


def rrf(listas: list[list[str]], *, k: int = RRF_K) -> dict[str, float]:
    """Reciprocal Rank Fusion.

    Se fusiona por **posicion**, no por puntuacion. Es deliberado: un score
    lexico y una similitud coseno no viven en la misma escala, y ponderarlos
    entre si exigiria inventar un factor de conversion arbitrario. RRF solo
    necesita saber quien va antes.
    """
    puntos: dict[str, float] = {}
    for lista in listas:
        for posicion, rid in enumerate(lista, 1):
            puntos[rid] = puntos.get(rid, 0.0) + 1.0 / (k + posicion)
    return puntos
