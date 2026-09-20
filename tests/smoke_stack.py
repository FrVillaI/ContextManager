"""Prueba de humo del stack completo: Ollama + FalkorDB + Graphiti.

Comprueba cada pieza por separado antes de intentar la ingesta, para que un
fallo diga exactamente que componente lo causo.
"""

import asyncio
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from acm.graph import EMBED_MODEL, GraphConfig, build_graphiti  # noqa: E402
from acm.store import MemoryStore  # noqa: E402


def step(n: int, text: str) -> None:
    print(f"\n[{n}] {text}")


async def main() -> int:
    cfg = GraphConfig()

    step(1, "Memoria JSONL (fuente de verdad)")
    store = MemoryStore(Path(__file__).resolve().parents[1] / "memory", "demo-tienda")
    stats = store.stats()
    problems = store.check()
    print(f"    registros: {stats}")
    print(f"    integridad: {'OK' if not problems else problems}")
    if problems:
        return 1

    step(2, "FalkorDB alcanzable")
    from falkordb import FalkorDB

    db = FalkorDB(host=cfg.host, port=cfg.port)
    graph = db.select_graph(cfg.database)
    graph.query("RETURN 1")
    print(f"    conectado a {cfg.host}:{cfg.port}, grafo '{cfg.database}'")

    step(3, f"Embeddings con {EMBED_MODEL}")
    from acm.graph import OLLAMA_API_KEY, OLLAMA_BASE_URL
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=OLLAMA_API_KEY, base_url=OLLAMA_BASE_URL)
    t0 = time.perf_counter()
    emb = await client.embeddings.create(model=EMBED_MODEL, input="prueba de embeddings")
    dim = len(emb.data[0].embedding)
    print(f"    dimensiones: {dim}  ({time.perf_counter() - t0:.1f}s)")

    step(4, f"Generacion con {cfg.model}")
    t0 = time.perf_counter()
    chat = await client.chat.completions.create(
        model=cfg.model,
        messages=[{"role": "user", "content": "Responde unicamente: OK"}],
        max_tokens=10,
    )
    print(f"    respuesta: {chat.choices[0].message.content!r}  ({time.perf_counter() - t0:.1f}s)")

    step(5, "Indices y restricciones de Graphiti sobre FalkorDB")
    graphiti = build_graphiti(cfg)
    t0 = time.perf_counter()
    await graphiti.build_indices_and_constraints()
    print(f"    creados ({time.perf_counter() - t0:.1f}s)")
    await graphiti.close()

    print("\nStack operativo de extremo a extremo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
