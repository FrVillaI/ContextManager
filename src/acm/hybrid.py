"""Recuperacion hibrida: lexico + semantico fusionados con RRF (DEC-020).

Este modulo **compone**, no modifica: `retrieval.py` queda congelado como linea
base. Cambiar de estrategia es cambiar de funcion, no editar la anterior, asi
que la comparacion entre las tres siempre es honesta.

Regla de admision semantica
---------------------------
Las similitudes coseno se agolpan: una consulta sobre un dominio que el proyecto
no tiene alcanza 0,65, casi lo mismo que una consulta legitima. **Los embeddings
no tienen una señal natural de "aqui no hay nada"**, asi que un umbral absoluto
solo no vale. Se exige que el candidato destaque:

    similitud >= SIM_FLOOR   o   z-score sobre el corpus >= Z_FLOOR

Ambos umbrales estan calibrados sobre el banco de 40 consultas de `evalset.py`.
Es un ajuste a datos observados, no una constante universal: si el corpus cambia
mucho, hay que volver a medirlos.
"""

from __future__ import annotations

import statistics
from dataclasses import replace

from .models import MemoryRecord
from .retrieval import Hit, retrieve
from .semantic import SemanticIndex, _coseno, _normalizar, embed, rrf

#: Similitud a partir de la cual el candidato entra por si solo.
SIM_FLOOR = 0.68

#: Cuantas desviaciones tipicas sobre la mediana del corpus debe destacar.
Z_FLOOR = 2.4

#: Cuantos candidatos semanticos se consideran como maximo.
SEM_TOP_K = 10


def semantic_candidates(
    index: SemanticIndex,
    query: str,
    *,
    sim_floor: float = SIM_FLOOR,
    z_floor: float = Z_FLOOR,
    top_k: int = SEM_TOP_K,
) -> list[tuple[str, float]]:
    """Candidatos semanticos que destacan del fondo del corpus."""
    if not index.vectors:
        return []

    q = _normalizar(embed([query])[0])
    sims = {rid: _coseno(q, v) for rid, v in index.vectors.items()}
    valores = list(sims.values())
    mediana = statistics.median(valores)
    desviacion = statistics.pstdev(valores) or 1e-9

    admitidos = [
        (rid, s) for rid, s in sims.items()
        if s >= sim_floor or (s - mediana) / desviacion >= z_floor
    ]
    admitidos.sort(key=lambda p: -p[1])
    return admitidos[:top_k]


def retrieve_hybrid(
    records: list[MemoryRecord],
    query: str,
    index: SemanticIndex | None,
    *,
    extra_terms: set[str] | None = None,
    hint_modules: list[str] | None = None,
    limit: int = 8,
    semantic_only: bool = False,
) -> list[Hit]:
    """Fusiona la via lexica y la semantica por posicion (RRF).

    Se fusiona por posicion y no por puntuacion porque un score lexico y una
    similitud coseno no viven en la misma escala; ponderarlos exigiria inventar
    un factor de conversion arbitrario.
    """
    by_id = {r.id: r for r in records}

    lexicos: list[Hit] = [] if semantic_only else retrieve(
        records, query,
        extra_terms=extra_terms, hint_modules=hint_modules,
        limit=max(limit * 2, 16),
    )
    lex_ranking = [h.record.id for h in lexicos if h.direct]
    por_id = {h.record.id: h for h in lexicos}

    semanticos = semantic_candidates(index, query) if index else []
    sem_ranking = [rid for rid, _ in semanticos if rid in by_id]
    sem_sims = dict(semanticos)

    if not lex_ranking and not sem_ranking:
        # Se conservan los guardarrailes que la via lexica haya añadido: son
        # reglas del area, no precedentes. Regla 5 de DEC-020.
        return [h for h in lexicos if not h.direct][:limit]

    fusion = rrf([lex_ranking, sem_ranking])

    salida: list[Hit] = []
    for rid, puntos in sorted(fusion.items(), key=lambda p: -p[1]):
        if rid not in by_id:
            continue
        base = por_id.get(rid)
        if base is not None:
            # Descubierto por evidencia lexica. Que el vectorial coincida no
            # cambia su naturaleza: sigue siendo un hallazgo con evidencia.
            salida.append(replace(base, score=puntos * 1000))
        else:
            # Descubierto solo por similitud. Regla 3 de DEC-020: no se presenta
            # como precedente confirmado, se marca como hallazgo semantico.
            salida.append(Hit(
                record=by_id[rid],
                score=puntos * 1000,
                via=f"similitud semantica ({sem_sims.get(rid, 0):.2f}), sin evidencia lexica",
                seed="(embeddings)",
            ))
        if len(salida) >= limit:
            break

    # Guardarrailes lexicos que no entraron en la fusion.
    ya = {h.record.id for h in salida}
    for h in lexicos:
        if not h.direct and h.record.id not in ya and len(salida) < limit:
            salida.append(h)

    return salida
