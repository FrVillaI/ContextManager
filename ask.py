"""Punto de entrada: peticion en lenguaje natural -> bloque de contexto.

    python ask.py "modificar la pantalla de clientes para mostrar dos por fila"

Con --no-llm se salta el analisis de intencion y usa solo solapamiento lexico,
que es util para comprobar cuanto aporta realmente el modelo local.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from acm.context import build  # noqa: E402
from acm.intent import Intent, analyze  # noqa: E402
from acm.hybrid import retrieve_hybrid  # noqa: E402
from acm.retrieval import retrieve  # noqa: E402
from acm.semantic import load_index  # noqa: E402
from acm.settings import MODOS, ollama_disponible, resolve  # noqa: E402
from acm.projects import read_context_file  # noqa: E402
from acm.store import MemoryStore, all_projects  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Construye contexto para Claude/GPT")
    parser.add_argument("query", help="la peticion, en lenguaje natural")
    parser.add_argument("--limit", type=int, default=8, help="maximo de registros")
    parser.add_argument("--no-llm", action="store_true", help="solo solapamiento lexico")
    parser.add_argument("--stats", action="store_true", help="muestra la reduccion lograda")
    parser.add_argument("--project", help="project_id; por defecto se deduce del cwd")
    parser.add_argument("--lexico", action="store_true",
                        help="solo solapamiento lexico, sin capa semantica")
    parser.add_argument("--modo", choices=sorted(MODOS),
                        help="anula el modo configurado solo para esta consulta")
    args = parser.parse_args()

    # El proyecto activo decide en que memoria se busca. Nunca se mezclan.
    pid = args.project
    if not pid:
        marca = read_context_file(Path.cwd())
        pid = marca["project_id"] if marca else None
    if not pid:
        disponibles = all_projects(ROOT / "memory")
        if len(disponibles) == 1:
            pid = disponibles[0]
        else:
            print(f"indica el proyecto con --project. Disponibles: "
                  f"{', '.join(disponibles) or 'ninguno'}", file=sys.stderr)
            return 1

    store = MemoryStore(ROOT / "memory", pid)
    records = list(store.all())
    if not records:
        print(f"el proyecto '{pid}' no tiene memoria todavia.", file=sys.stderr)

    # El modo decide que piezas de IA local se usan (DEC-032). Las banderas
    # antiguas siguen funcionando y mandan sobre el modo, para no romper guiones
    # ya escritos.
    modo = MODOS[args.modo] if args.modo else resolve(ROOT, pid)
    usa_intencion = modo.usa_intencion and not args.no_llm
    usa_embeddings = modo.usa_embeddings and not args.lexico

    # Si hace falta Ollama, se comprueba una vez y se recuerda: asi una consulta
    # con el servicio parado no paga el intento de conexion dos veces.
    if (usa_intencion or usa_embeddings) and not ollama_disponible(ROOT):
        print(f"[aviso] Ollama no responde: esta consulta usa solo solapamiento "
              f"lexico (modo configurado: {modo.nombre})", file=sys.stderr)
        usa_intencion = usa_embeddings = False

    t0 = time.perf_counter()
    if not usa_intencion:
        intent = Intent(intent="(sin analisis)")
    else:
        intent = analyze(args.query, records)
        if intent.error:
            print(f"[aviso] el modelo local fallo, sigo solo con solapamiento: "
                  f"{intent.error}", file=sys.stderr)

    index = load_index(ROOT / "memory", pid) if usa_embeddings else None
    if index is None:
        hits = retrieve(
            records, args.query,
            extra_terms=intent.keyword_terms,
            hint_modules=intent.modules,
            limit=args.limit,
        )
    else:
        hits = retrieve_hybrid(
            records, args.query, index,
            extra_terms=intent.keyword_terms,
            hint_modules=intent.modules,
            limit=args.limit,
        )
    context = build(args.query, hits, intent)
    elapsed = time.perf_counter() - t0

    print(context.text)

    if args.stats:
        total, pct = context.savings(records)
        print("\n" + "-" * 62, file=sys.stderr)
        print(f"proyecto             : {pid}", file=sys.stderr)
        print(f"modo                 : {modo.describe()}", file=sys.stderr)
        print(f"registros en memoria : {len(records)}", file=sys.stderr)
        print(f"registros enviados   : {len(hits)}", file=sys.stderr)
        print(f"memoria completa     : {total} caracteres", file=sys.stderr)
        print(f"contexto enviado     : {context.chars} caracteres", file=sys.stderr)
        print(f"reduccion            : {pct:.0f} %", file=sys.stderr)
        print(f"tiempo               : {elapsed:.1f}s", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
