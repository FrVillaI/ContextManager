"""Comparacion léxico / semántico / híbrido (DEC-020).

Ejecuta las tres estrategias sobre el mismo banco anotado y las mismas metricas.
El pipeline no cambia entre modos: solo cambia de donde salen los candidatos.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from acm.hybrid import retrieve_hybrid  # noqa: E402
from acm.retrieval import Hit, retrieve  # noqa: E402
from acm.semantic import build_index  # noqa: E402
from acm.store import MemoryStore  # noqa: E402
from evalset import CASOS, CATEGORIAS, Caso  # noqa: E402

K = 8
PROJECT = "demo-tienda"


# --------------------------------------------------------------------------
# Metricas
# --------------------------------------------------------------------------

def precision_at(hits: list[Hit], esperados: frozenset[str], k: int) -> float:
    top = hits[:k]
    if not top:
        return 0.0
    return sum(h.record.id in esperados for h in top) / len(top)


def recall_at(hits: list[Hit], esperados: frozenset[str], k: int) -> float:
    if not esperados:
        return 1.0
    return len({h.record.id for h in hits[:k]} & esperados) / len(esperados)


def reciprocal_rank(hits: list[Hit], esperados: frozenset[str]) -> float:
    for i, hit in enumerate(hits, 1):
        if hit.record.id in esperados:
            return 1.0 / i
    return 0.0


def ndcg_at(hits: list[Hit], esperados: frozenset[str], k: int) -> float:
    """Ganancia acumulada descontada. Relevancia binaria: 1 si es esperado."""
    if not esperados:
        return 1.0
    dcg = sum(
        1.0 / math.log2(i + 1)
        for i, hit in enumerate(hits[:k], 1)
        if hit.record.id in esperados
    )
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(esperados), k) + 1))
    return dcg / ideal if ideal else 0.0


def es_precedente(hit: Hit) -> bool:
    """Un guardarrail nunca es precedente; un hallazgo semantico sin evidencia
    lexica tampoco se presenta como tal, pero SI cuenta como falso precedente si
    aparece en un dominio inexistente: el usuario lo vera igualmente."""
    return hit.record.type in {"bug", "solution", "change", "decision"}


@dataclass
class Resultado:
    nombre: str
    filas: dict[str, dict] = field(default_factory=dict)

    def agrega(self, categoria: str, **valores) -> None:
        acc = self.filas.setdefault(
            categoria, {"n": 0, "p3": 0.0, "p5": 0.0, "p8": 0.0,
                        "r5": 0.0, "r8": 0.0, "mrr": 0.0, "ndcg": 0.0, "falsos": 0}
        )
        acc["n"] += 1
        for clave, valor in valores.items():
            acc[clave] += valor

    def media(self, categoria: str, clave: str) -> float:
        fila = self.filas.get(categoria)
        if not fila or not fila["n"]:
            return 0.0
        return fila[clave] / fila["n"]

    def global_(self, clave: str) -> float:
        total = sum(f["n"] for c, f in self.filas.items() if c != "UNKNOWN_DOMAIN")
        suma = sum(f[clave] for c, f in self.filas.items() if c != "UNKNOWN_DOMAIN")
        return suma / total if total else 0.0

    @property
    def fpr(self) -> float:
        falsos = sum(f["falsos"] for f in self.filas.values())
        n = sum(f["n"] for f in self.filas.values())
        return falsos / n if n else 0.0

    @property
    def falsos_unknown(self) -> tuple[int, int]:
        fila = self.filas.get("UNKNOWN_DOMAIN", {"falsos": 0, "n": 0})
        return fila["falsos"], fila["n"]


def evaluar(nombre: str, buscar, casos: list[Caso]) -> Resultado:
    res = Resultado(nombre)
    for caso in casos:
        hits = buscar(caso)
        if caso.sin_precedente:
            falsos = 1 if any(es_precedente(h) for h in hits) else 0
            res.agrega(caso.categoria, falsos=falsos)
            continue
        res.agrega(
            caso.categoria,
            p3=precision_at(hits, caso.esperados, 3),
            p5=precision_at(hits, caso.esperados, 5),
            p8=precision_at(hits, caso.esperados, K),
            r5=recall_at(hits, caso.esperados, 5),
            r8=recall_at(hits, caso.esperados, K),
            mrr=reciprocal_rank(hits, caso.esperados),
            ndcg=ndcg_at(hits, caso.esperados, K),
        )
    return res


def tabla(resultados: list[Resultado]) -> None:
    print(f"\n{'':<16}", end="")
    for r in resultados:
        print(f"{r.nombre:>13}", end="")
    print()
    print("-" * (16 + 13 * len(resultados)))
    for clave, etiqueta in [
        ("p3", "Precision@3"), ("p5", "Precision@5"), ("p8", "Precision@8"),
        ("r5", "Recall@5"), ("r8", "Recall@8"),
        ("mrr", "MRR"), ("ndcg", "nDCG@8"),
    ]:
        print(f"{etiqueta:<16}", end="")
        for r in resultados:
            v = r.global_(clave)
            print(f"{v:>12.3f} " if clave in ("mrr", "ndcg") else f"{v:>12.1%} ", end="")
        print()
    print(f"{'False Preced.':<16}", end="")
    for r in resultados:
        f, n = r.falsos_unknown
        print(f"{f}/{n} ({f/n:.0%})".rjust(13), end="")
    print()


def por_categoria(resultados: list[Resultado], clave: str, etiqueta: str) -> None:
    print(f"\n{etiqueta} por categoria")
    print(f"{'':<16}", end="")
    for r in resultados:
        print(f"{r.nombre:>13}", end="")
    print()
    print("-" * (16 + 13 * len(resultados)))
    for cat in CATEGORIAS:
        if cat == "UNKNOWN_DOMAIN":
            continue
        print(f"{cat:<16}", end="")
        for r in resultados:
            print(f"{r.media(cat, clave):>12.3f} ", end="")
        print()


def main() -> int:
    store = MemoryStore(ROOT / "memory", PROJECT)
    records = list(store.all())
    print(f"corpus: {len(records)} registros | consultas: {len(CASOS)} | K = {K}")

    index = build_index(records, ROOT / "memory", PROJECT)
    print(f"indice semantico: {index.size} vectores")

    resultados = [
        evaluar("lexico", lambda c: retrieve(records, c.query, limit=K), CASOS),
        evaluar("semantico",
                lambda c: retrieve_hybrid(records, c.query, index, limit=K,
                                          semantic_only=True), CASOS),
        evaluar("hibrido",
                lambda c: retrieve_hybrid(records, c.query, index, limit=K), CASOS),
    ]

    tabla(resultados)
    por_categoria(resultados, "r8", "Recall@8")
    por_categoria(resultados, "ndcg", "nDCG@8")

    salida = ROOT / "bench_results" / "comparacion.json"
    salida.parent.mkdir(exist_ok=True)
    salida.write_text(json.dumps(
        {r.nombre: {"global": {k: r.global_(k) for k in
                               ("p3", "p5", "p8", "r5", "r8", "mrr", "ndcg")},
                    "fpr_unknown": r.falsos_unknown,
                    "por_categoria": r.filas} for r in resultados},
        indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nresultados en {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
