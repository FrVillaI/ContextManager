"""Analisis de intencion con el modelo local (DEC-012, DEC-013).

El modelo hace aqui lo unico que el benchmark demostro que hace bien: clasificar
la peticion y senalar que modulos toca. No propone relaciones ni decide
relevancia, y no puede inventar modulos porque solo se le permite elegir de un
vocabulario cerrado construido a partir de la memoria existente.

Se usa decodificacion restringida por esquema, que elimina la deriva de formato
observada en el benchmark.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import httpx

from .models import MemoryRecord

OLLAMA_CHAT = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL = "llama3.2:3b"

INTENTS = ["modify_feature", "add_feature", "fix_bug", "refactor", "question"]


@dataclass
class Intent:
    intent: str
    modules: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)
    error: str = ""

    @property
    def keyword_terms(self) -> set[str]:
        """Solo las palabras clave: son lexicas y precisas.

        Los modulos se dejan fuera a proposito y viajan aparte, porque son
        demasiado gruesos para decidir que entra en el contexto.
        """
        from .retrieval import tokenize

        out: set[str] = set()
        for item in self.keywords:
            out |= tokenize(item)
        return out


def module_vocabulary(records: list[MemoryRecord]) -> list[str]:
    """Vocabulario cerrado de modulos, tomado de la memoria ya existente."""
    return sorted({m for r in records for m in r.modules})


SYSTEM = (
    "Analizas peticiones de desarrollo de software y senalas que partes del "
    "proyecto tocan. No inventes modulos: elige solo de la lista dada. Si "
    "ninguno encaja, devuelve la lista vacia."
)

TEMPLATE = """Peticion del usuario:
{query}

Modulos disponibles en este proyecto:
{vocab}

Devuelve la intencion, los modulos afectados (solo de la lista) y las palabras
clave tecnicas de la peticion."""


def analyze(
    query: str,
    records: list[MemoryRecord],
    *,
    model: str = DEFAULT_MODEL,
    timeout: float = 120.0,
) -> Intent:
    vocab = module_vocabulary(records)

    schema = {
        "type": "object",
        "properties": {
            "intent": {"type": "string", "enum": INTENTS},
            "modules": {"type": "array", "items": {"type": "string", "enum": vocab}},
            "keywords": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["intent", "modules", "keywords"],
    }

    payload = {
        "model": model,
        "stream": False,
        "format": schema,
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": TEMPLATE.format(
                    query=query, vocab="\n".join(f"- {m}" for m in vocab)
                ),
            },
        ],
    }

    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            resp = client.post(OLLAMA_CHAT, json=payload)
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
        data = json.loads(content)
    except Exception as exc:  # noqa: BLE001
        # Que el modelo falle no puede tumbar la recuperacion: el solapamiento
        # lexico funciona igual sin sus terminos.
        return Intent(intent="question", error=str(exc)[:160])

    permitidos = set(vocab)
    return Intent(
        intent=str(data.get("intent", "question")),
        modules=[m for m in data.get("modules", []) if m in permitidos],
        keywords=[str(k) for k in data.get("keywords", [])][:12],
        raw=data,
    )
