"""Conexion a Graphiti sobre FalkorDB, con Ollama como motor local.

El grafo es un *indice reconstruible* (DEC-002): esta capa nunca es la fuente de
verdad. Todo lo que entra aqui viene de los JSONL de `MemoryStore`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from graphiti_core import Graphiti
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

#: El endpoint compatible con OpenAI que expone Ollama.
OLLAMA_BASE_URL = os.getenv("ACM_OLLAMA_URL", "http://127.0.0.1:11434/v1")

#: Ollama no valida la clave, pero el cliente de OpenAI exige que exista.
OLLAMA_API_KEY = "ollama"

#: Modelo de embeddings. 768 dimensiones.
EMBED_MODEL = "nomic-embed-text"
EMBED_DIM = 768


@dataclass(frozen=True)
class GraphConfig:
    """Parametros de conexion. Ver DEC-008 y DEC-010."""

    model: str = os.getenv("ACM_MODEL", "qwen2.5:3b-instruct-q4_K_M")
    host: str = "127.0.0.1"
    port: int = 6379
    database: str = "acm"
    #: Ollama soporta json_schema en su endpoint compatible; si un modelo
    #: concreto falla, bajar a 'json_object' para ese modelo.
    structured_output_mode: str = "json_schema"


def build_graphiti(config: GraphConfig | None = None) -> Graphiti:
    """Crea una instancia de Graphiti apuntando a FalkorDB y a Ollama."""
    cfg = config or GraphConfig()

    llm_config = LLMConfig(
        api_key=OLLAMA_API_KEY,
        model=cfg.model,
        small_model=cfg.model,
        base_url=OLLAMA_BASE_URL,
    )

    llm = OpenAIGenericClient(
        config=llm_config,
        structured_output_mode=cfg.structured_output_mode,  # type: ignore[arg-type]
    )

    # Sin esto, Graphiti instancia por defecto un reranker contra la API real de
    # OpenAI y falla por falta de credenciales.
    reranker = OpenAIRerankerClient(config=llm_config)

    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=OLLAMA_API_KEY,
            embedding_model=EMBED_MODEL,
            embedding_dim=EMBED_DIM,
            base_url=OLLAMA_BASE_URL,
        )
    )

    driver = FalkorDriver(host=cfg.host, port=cfg.port, database=cfg.database)

    return Graphiti(
        graph_driver=driver,
        llm_client=llm,
        embedder=embedder,
        cross_encoder=reranker,
    )
