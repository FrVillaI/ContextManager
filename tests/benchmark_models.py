"""Benchmark de modelos locales para el rol de Context Manager (DEC-003, DEC-010).

Mide las cuatro metricas acordadas sobre los 16 registros reales sembrados desde
el proyecto demo-tienda, cuyas entidades y relaciones fueron extraidas y verificadas a mano
contra commits y archivos SQL. Ese conjunto es la verdad de referencia.

Deliberadamente NO se usa decodificacion restringida: la metrica 1 pregunta si el
modelo produce JSON valido por si solo, que es lo que discrimina entre candidatos.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from acm.models import MemoryRecord  # noqa: E402
from acm.store import MemoryStore  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "bench_results"

MODELS = [
    "qwen2.5:3b-instruct-q4_K_M",
    "llama3.2:3b",
    "phi3:mini",
    "qwen3.5:0.8b",
]

#: Vocabulario cerrado de relaciones que el modelo puede proponer. Cualquier
#: relacion fuera de esta lista cuenta como inventada.
RELATIONS = [
    "solucionado_con", "reaparicion_de", "depende_de", "relacionado_con",
    "parche_de", "deriva_de", "explica_criticidad_de",
]

TYPES = ["bug", "decision", "constraint", "solution", "project"]

PROMPT = """Eres un analizador de memoria de proyectos de software. Recibes un registro
y debes clasificarlo y extraer sus entidades.

Responde UNICAMENTE con un objeto JSON, sin texto antes ni despues, sin ```.

Formato exacto:
{{"type": "<uno de: {types}>",
 "modules": ["<modulo afectado>", ...],
 "relations": [{{"rel": "<una de: {rels}>", "target": "<ID de otro registro>"}}],
 "tags": ["<etiqueta>", ...]}}

Registros existentes que puedes referenciar en "relations":
{catalog}

REGISTRO A ANALIZAR
ID: {rid}
Titulo: {title}
Descripcion: {summary}
Archivos tocados: {files}
"""


@dataclass
class RecordResult:
    rid: str
    parsed: bool
    seconds: float
    type_ok: bool = False
    modules_hit: int = 0
    modules_total: int = 0
    rel_correct: int = 0
    rel_invented: int = 0
    rel_total: int = 0
    error: str = ""


@dataclass
class ModelResult:
    model: str
    records: list[RecordResult] = field(default_factory=list)
    load_error: str = ""

    @property
    def n(self) -> int:
        return len(self.records)

    @property
    def json_rate(self) -> float:
        return 100.0 * sum(r.parsed for r in self.records) / max(self.n, 1)

    @property
    def type_rate(self) -> float:
        ok = [r for r in self.records if r.parsed]
        return 100.0 * sum(r.type_ok for r in ok) / max(len(ok), 1)

    @property
    def coverage(self) -> float:
        hit = sum(r.modules_hit for r in self.records)
        total = sum(r.modules_total for r in self.records)
        return 100.0 * hit / max(total, 1)

    @property
    def rel_precision(self) -> float:
        """Aristas correctas sobre aristas propuestas. Castiga inventar."""
        proposed = sum(r.rel_correct + r.rel_invented for r in self.records)
        return 100.0 * sum(r.rel_correct for r in self.records) / max(proposed, 1)

    @property
    def rel_recall(self) -> float:
        total = sum(r.rel_total for r in self.records)
        return 100.0 * sum(r.rel_correct for r in self.records) / max(total, 1)

    @property
    def invented(self) -> int:
        return sum(r.rel_invented for r in self.records)

    @property
    def median_seconds(self) -> float:
        times = sorted(r.seconds for r in self.records)
        if not times:
            return 0.0
        mid = len(times) // 2
        return times[mid] if len(times) % 2 else (times[mid - 1] + times[mid]) / 2


def loose_match(candidate: str, truth: str) -> bool:
    """Comparacion indulgente: 'ExercisesController' cuenta para
    'backend/ExercisesController'. Se compara por trozos normalizados."""
    c = re.sub(r"[^a-z0-9]+", " ", candidate.lower()).split()
    t = re.sub(r"[^a-z0-9]+", " ", truth.lower()).split()
    if not c or not t:
        return False
    return bool(set(c) & set(t))


def extract_json(text: str) -> dict | None:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Un unico reintento barato: quedarse con el primer objeto equilibrado.
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        depth += (ch == "{") - (ch == "}")
        if depth == 0:
            try:
                return json.loads(text[start : i + 1])
            except json.JSONDecodeError:
                return None
    return None


def score(record: MemoryRecord, data: dict) -> tuple[bool, int, int, int, int, int]:
    type_ok = str(data.get("type", "")).strip().lower() == record.type

    truth_modules = record.modules
    got_modules = [str(m) for m in data.get("modules", []) if isinstance(m, (str, int))]
    hit = sum(1 for t in truth_modules if any(loose_match(g, t) for g in got_modules))

    truth_rels = {(link.rel, link.target) for link in record.links}
    correct = invented = 0
    for item in data.get("relations", []) or []:
        if not isinstance(item, dict):
            invented += 1
            continue
        rel = str(item.get("rel", "")).strip().lower()
        target = str(item.get("target", "")).strip().upper()
        if (rel, target) in truth_rels:
            correct += 1
        else:
            invented += 1

    return type_ok, hit, len(truth_modules), correct, invented, len(truth_rels)


async def run_model(client, model: str, records: list[MemoryRecord], catalog: str) -> ModelResult:
    result = ModelResult(model=model)
    print(f"\n### {model}", flush=True)

    for record in records:
        prompt = PROMPT.format(
            types=", ".join(TYPES),
            rels=", ".join(RELATIONS),
            catalog=catalog,
            rid=record.id,
            title=record.title,
            summary=record.summary,
            files=", ".join(record.files) or "(ninguno)",
        )
        t0 = time.perf_counter()
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=600,
            )
            elapsed = time.perf_counter() - t0
            text = resp.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - t0
            msg = str(exc)[:120]
            print(f"  {record.id}  ERROR  {msg}", flush=True)
            result.records.append(RecordResult(record.id, False, elapsed, error=msg))
            if "terminated" in msg or "memory" in msg.lower():
                result.load_error = msg
                break
            continue

        data = extract_json(text)
        if data is None:
            print(f"  {record.id}  JSON invalido  ({elapsed:.1f}s)", flush=True)
            result.records.append(RecordResult(record.id, False, elapsed, error="json"))
            continue

        type_ok, hit, mtotal, correct, invented, rtotal = score(record, data)
        print(
            f"  {record.id}  ok  tipo={'si' if type_ok else 'NO'} "
            f"mod={hit}/{mtotal} rel={correct}ok/{invented}inv  ({elapsed:.1f}s)",
            flush=True,
        )
        result.records.append(
            RecordResult(record.id, True, elapsed, type_ok, hit, mtotal,
                         correct, invented, rtotal)
        )

    return result


async def main() -> int:
    from openai import AsyncOpenAI

    store = MemoryStore(ROOT / "memory")
    records = sorted(store.all(), key=lambda r: r.id)
    catalog = "\n".join(f"  {r.id}: {r.title[:70]}" for r in records)
    print(f"Registros de referencia: {len(records)}")

    client = AsyncOpenAI(api_key="ollama", base_url="http://127.0.0.1:11434/v1")

    results: list[ModelResult] = []
    for model in MODELS:
        results.append(await run_model(client, model, records, catalog))

    OUT_DIR.mkdir(exist_ok=True)
    payload = [
        {
            "model": r.model,
            "n": r.n,
            "json_rate": round(r.json_rate, 1),
            "type_rate": round(r.type_rate, 1),
            "coverage": round(r.coverage, 1),
            "rel_precision": round(r.rel_precision, 1),
            "rel_recall": round(r.rel_recall, 1),
            "invented": r.invented,
            "median_seconds": round(r.median_seconds, 1),
            "load_error": r.load_error,
            "records": [vars(rec) for rec in r.records],
        }
        for r in results
    ]
    (OUT_DIR / "benchmark.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("\n" + "=" * 78)
    print(f"{'modelo':<30} {'JSON':>6} {'tipo':>6} {'mods':>6} {'rel-P':>6} {'inv':>5} {'seg':>6}")
    print("-" * 78)
    for r in results:
        print(
            f"{r.model:<30} {r.json_rate:>5.0f}% {r.type_rate:>5.0f}% "
            f"{r.coverage:>5.0f}% {r.rel_precision:>5.0f}% {r.invented:>5} "
            f"{r.median_seconds:>5.1f}s"
        )
    print("=" * 78)
    print(f"\nResultados en {OUT_DIR / 'benchmark.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
