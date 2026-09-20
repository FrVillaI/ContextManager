"""Recuperacion por solapamiento (DEC-013).

El benchmark de DEC-010 dejo claro que el modelo local no puede proponer aristas:
13 % de precision, una relacion falsa por registro. Asi que aqui no interviene
ningun modelo. Las relaciones y la relevancia salen de coincidencias verificables
entre los campos `files`, `modules`, `tags` y el texto de los registros.

Dos operaciones distintas viven en este modulo:

- `derive_edges`  : que registros estan relacionados entre si, y por que evidencia.
- `retrieve`      : que registros son relevantes para una peticion concreta.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field

from .models import MemoryRecord

# --------------------------------------------------------------------------
# Normalizacion
# --------------------------------------------------------------------------

#: Palabras vacias en español e ingles que no aportan senal de recuperacion.
STOPWORDS: frozenset[str] = frozenset("""
a al algo alguna algunas alguno algunos ante antes como con contra cual cuando
de del desde donde dos el ella ellas ellos en entre era eran es esa esas ese eso
esos esta estan estas este esto estos ha han hasta hay la las le les lo los mas
me mi mis mucho muy no nos o os otra otras otro otros para pero poco por porque
que quien se sea ser si sin sobre solo son su sus también tanto te tiene todo
todos tu tus un una uno unos ver vamos y ya
and are but for from into not the this that with when where which will
""".split())

#: Extensiones y fragmentos de ruta que aparecen en casi todos los archivos y por
#: tanto no discriminan nada.
PATH_NOISE: frozenset[str] = frozenset(
    "ts tsx js jsx cs sql md py src app lib docs screens components services "
    "hooks store types controllers".split()
)


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def tokenize(text: str) -> set[str]:
    """Trocea texto libre en terminos comparables.

    Parte tambien camelCase y rutas, para que 'apiClient.ts' y 'api client'
    se encuentren.
    """
    text = strip_accents(text)
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)  # camelCase -> camel Case
    words = re.split(r"[^A-Za-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


def path_tokens(paths: list[str]) -> set[str]:
    """Tokens significativos de una lista de rutas o modulos."""
    return {t for p in paths for t in tokenize(p)} - PATH_NOISE


def split_path_tokens(paths: list[str]) -> dict[str, set[str]]:
    """Descompone rutas en los cuatro grados de señal de DEC-017.

        ruta exacta  >  token del nombre  >  directorio inmediato  >  ancestro

    Cuanto mas arriba esta un segmento en el arbol, a mas archivos pertenece y
    menos discrimina: 'src' o 'web' son casi etiquetas de proyecto, mientras que
    'apiClient' identifica una unidad concreta de codigo.
    """
    exactas: set[str] = set()
    hojas: set[str] = set()
    padres: set[str] = set()
    ancestros: set[str] = set()

    for p in paths:
        normal = p.replace("\\", "/").lower()
        exactas.add(normal)
        exactas.add(normal.rsplit("/", 1)[-1])   # basename completo con extension
        partes = re.split(r"[/\\]", p)
        hojas |= tokenize(partes[-1])
        if len(partes) >= 2:
            padres |= tokenize(partes[-2])
        for parte in partes[:-2]:
            ancestros |= tokenize(parte)

    hojas -= PATH_NOISE
    padres = (padres - PATH_NOISE) - hojas
    ancestros = (ancestros - PATH_NOISE) - hojas - padres
    return {
        "file_exact": exactas,
        "files": hojas,
        "file_dirs": padres,
        "file_ancestors": ancestros,
    }


# --------------------------------------------------------------------------
# Aristas derivadas
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class DerivedEdge:
    """Relacion deducida de evidencia, nunca de inferencia semantica."""

    source: str
    target: str
    rel: str
    weight: float
    evidence: tuple[str, ...]

    def describe(self) -> str:
        muestra = ", ".join(self.evidence[:3])
        extra = f" (+{len(self.evidence) - 3})" if len(self.evidence) > 3 else ""
        return f"{self.rel}: {muestra}{extra}"


#: Peso de cada tipo de evidencia. Compartir un archivo concreto es una senal
#: mucho mas fuerte que compartir una etiqueta.
EDGE_RULES: dict[str, float] = {
    "comparte_archivo": 3.0,
    "comparte_modulo": 2.0,
    "mismo_commit": 2.5,
    "comparte_etiqueta": 1.0,
}


#: Un archivo o modulo presente en mas de esta fraccion del corpus deja de ser
#: evidencia de relacion. `docs/PROGRESS.md` lo toca casi cada commit: que dos
#: registros lo compartan no dice absolutamente nada sobre si tienen que ver.
UBIQUITY_LIMIT = 0.12


def _rarity(records: list[MemoryRecord], attr: str) -> dict[str, float]:
    """Cuanto vale compartir cada archivo o modulo, segun lo raro que sea."""
    n = max(len(records), 1)
    df: dict[str, int] = defaultdict(int)
    for record in records:
        for item in set(getattr(record, attr)):
            df[item] += 1
    pesos: dict[str, float] = {}
    for item, c in df.items():
        if c / n > UBIQUITY_LIMIT:
            pesos[item] = 0.0          # ubicuo: no es evidencia de nada
        else:
            pesos[item] = math.log(n / c) / math.log(n)
    return pesos


def derive_edges(records: list[MemoryRecord], min_weight: float = 1.0) -> list[DerivedEdge]:
    """Deduce relaciones entre registros a partir de coincidencias verificables.

    No sustituye a los enlaces curados de `record.links`: los complementa. Los
    curados son afirmaciones; estos son indicios con su evidencia adjunta.
    """
    edges: list[DerivedEdge] = []
    by_id = {r.id: r for r in records}
    ids = sorted(by_id)
    rareza_archivo = _rarity(records, "files")
    rareza_modulo = _rarity(records, "modules")

    for i, a_id in enumerate(ids):
        for b_id in ids[i + 1:]:
            a, b = by_id[a_id], by_id[b_id]
            if a.project_id != b.project_id:
                continue

            found: list[tuple[str, float, tuple[str, ...]]] = []

            shared_files = {f for f in set(a.files) & set(b.files)
                            if rareza_archivo.get(f, 0.0) > 0}
            if shared_files:
                peso = sum(rareza_archivo[f] for f in shared_files)
                found.append(("comparte_archivo",
                              EDGE_RULES["comparte_archivo"] * peso,
                              tuple(sorted(shared_files))))

            shared_modules = {m for m in set(a.modules) & set(b.modules)
                              if rareza_modulo.get(m, 0.0) > 0}
            if shared_modules:
                peso = sum(rareza_modulo[m] for m in shared_modules)
                found.append(("comparte_modulo",
                              EDGE_RULES["comparte_modulo"] * peso,
                              tuple(sorted(shared_modules))))

            if (a.source.kind == b.source.kind == "git_commit"
                    and a.source.ref == b.source.ref):
                found.append(("mismo_commit", EDGE_RULES["mismo_commit"],
                              (a.source.ref,)))

            shared_tags = set(a.tags) & set(b.tags)
            if len(shared_tags) >= 2:
                found.append(("comparte_etiqueta",
                              EDGE_RULES["comparte_etiqueta"] * len(shared_tags),
                              tuple(sorted(shared_tags))))

            for rel, weight, evidence in found:
                if weight >= min_weight:
                    edges.append(DerivedEdge(a_id, b_id, rel, weight, evidence))

    return sorted(edges, key=lambda e: -e.weight)


def neighbours(edges: list[DerivedEdge]) -> dict[str, list[DerivedEdge]]:
    """Indice bidireccional de aristas derivadas por id de registro."""
    index: dict[str, list[DerivedEdge]] = defaultdict(list)
    for edge in edges:
        index[edge.source].append(edge)
        index[edge.target].append(
            DerivedEdge(edge.target, edge.source, edge.rel, edge.weight, edge.evidence)
        )
    return index


# --------------------------------------------------------------------------
# Recuperacion
# --------------------------------------------------------------------------

#: Cuanto vale cada tipo de coincidencia con la peticion del usuario.
FIELD_WEIGHTS: dict[str, float] = {
    # Jerarquia de señal en rutas (DEC-017), de mas fuerte a mas debil.
    "file_exact": 6.0,        # la ruta o el nombre de archivo completo
    "files": 4.0,             # un token del nombre del archivo
    "file_dirs": 1.2,         # directorio inmediato
    "file_ancestors": 0.5,    # directorio ancestro: casi una etiqueta de proyecto
    "modules": 3.0,
    "tags": 2.5,
    "title": 1.5,
    "summary": 0.6,
}

#: Cuanta puntuacion conserva un registro traido por una relacion en vez de por
#: coincidencia directa. Por debajo de 0.5 para que un vecino nunca desplace a
#: una coincidencia propia.
HOP_DECAY = 0.45

#: Puntuacion minima para considerar que un registro es relevante. Una unica
#: palabra coincidiendo en el resumen (0.6) es ruido: asi entraba ADR-001 en una
#: consulta sobre paginacion, porque el usuario escribio "ten en cuenta" y el
#: registro hablaba de "activar cuentas".
MIN_SCORE = 1.4

#: Una semilla solo expande si es comparable a la mejor coincidencia. Evita que
#: un registro marginal arrastre a sus vecinos al contexto.
SEED_RATIO = 0.35

#: Cuantos vecinos *derivados* puede aportar como maximo una sola semilla. Sin
#: este tope, un registro bien puntuado llenaba el contexto con su vecindario.
#: Los enlaces curados no cuentan aqui: son afirmaciones del equipo, no indicios.
MAX_NEIGHBOURS_PER_SEED = 2

#: Campos cuya coincidencia es evidencia por si sola: identifican codigo o tema
#: concretos, no vocabulario general.
CAMPOS_FUERTES = frozenset({"file_exact", "files", "modules", "tags"})

#: Rareza minima que debe tener algun termino coincidente para que el registro
#: cuente como precedente. Sin esto, una consulta sobre un dominio que el
#: proyecto no tiene ('chat en tiempo real con websockets') encuentra registros
#: por palabras corrientes del resumen y los presenta como experiencia previa.
IDF_FLOOR = 2.3

#: Umbral mas bajo para etiquetas y modulos. Estar en una etiqueta es una
#: afirmacion tematica sobre el registro, no una aparicion incidental como la de
#: 'cliente' dentro de una ruta de archivo, asi que exige menos rareza.
IDF_TOPICAL = 1.6

#: Corte relativo al mejor resultado. Sirve para devolver 3 registros cuando solo
#: hay 3 buenos, en vez de rellenar hasta el limite con relleno. Un contexto que
#: se rellena para llegar a un cupo es exactamente lo que este proyecto evita.
CUTOFF_RATIO = 0.22


@dataclass
class Hit:
    record: MemoryRecord
    score: float
    matched: dict[str, list[str]] = field(default_factory=dict)
    via: str = ""          # vacio = coincidencia directa
    seed: str = ""         # de que registro vino, si fue por relacion

    @property
    def direct(self) -> bool:
        return not self.via

    def why(self) -> str:
        if self.via:
            return f"traido desde {self.seed} por {self.via}"
        partes = [f"{campo}={'/'.join(v)}" for campo, v in self.matched.items() if v]
        return "; ".join(partes) or "coincidencia debil"


def record_tokens(record: MemoryRecord) -> dict[str, set[str]]:
    """Todos los campos comparables de un registro, ya troceados."""
    return {
        **split_path_tokens(record.files),
        "modules": path_tokens(record.modules),
        # Las etiquetas son atomicas: 'solucion-real' no contiene 'real'.
        # Trocearlas creaba tokens fantasma que casaban con 'tiempo real'.
        "tags": {strip_accents(t.strip().lower()) for t in record.tags},
        "title": tokenize(record.title),
        "summary": tokenize(record.summary),
    }


def build_idf(records: list[MemoryRecord]) -> dict[str, float]:
    """Peso inverso de frecuencia documental sobre la memoria completa.

    Sin esto, un termino como 'web' —que pertenece a media memoria— vale lo
    mismo que 'apiClient', que identifica dos registros. El efecto crece con el
    corpus: cuanto mas memoria haya, mejor discrimina.
    """
    n = len(records)
    df: dict[str, int] = defaultdict(int)
    for record in records:
        vistos: set[str] = set()
        for campo, tokens in record_tokens(record).items():
            if campo != "file_exact":
                vistos |= tokens
        for token in vistos:
            df[token] += 1
    # Suavizado: nunca cero, pero un termino ubicuo se queda cerca del minimo.
    return {t: math.log((n + 1) / (c + 1)) + 0.25 for t, c in df.items()}


def _es_especifica(matched: dict[str, list[str]], idf: dict[str, float]) -> bool:
    """Decide si la coincidencia constituye precedente, o es casualidad.

    Un unico termino en comun no es un precedente por raro que sea: que un
    checklist legal mencione 'facturacion' no lo convierte en experiencia previa
    sobre cobrar con Stripe. Un precedente exige que el registro trate **del
    mismo problema**, y eso se manifiesta de tres formas:

    1. la peticion cita una ruta literal del registro;
    2. cubre dos o mas terminos distintos, uno de ellos raro;
    3. el termino raro esta en etiquetas, modulos o nombre de archivo, es decir,
       identifica el tema del registro y no una palabra suelta de su resumen.
    """
    if matched.get("file_exact"):
        return True

    raros = {
        t for tokens in matched.values() for t in tokens
        if idf.get(t, 0.0) >= IDF_FLOOR
    }
    distintos = {t for tokens in matched.values() for t in tokens}
    if raros and len(distintos) >= 2:
        return True

    # Un unico termino basta solo si es el *tema* declarado del registro.
    tematicos = {t for c in ("tags", "modules") for t in matched.get(c, [])}
    return any(idf.get(t, 0.0) >= IDF_TOPICAL for t in tematicos)


def _score_record(
    record: MemoryRecord,
    terms: set[str],
    raw_query: str = "",
    idf: dict[str, float] | None = None,
) -> tuple[float, dict[str, list[str]]]:
    """Puntua un registro frente a los terminos de la peticion.

    Cada termino de la consulta aporta **una sola vez**, al peso del campo mas
    fuerte donde aparezca. Es deliberado: contar un mismo termino tres veces por
    estar en etiquetas, titulo y resumen premiaba la redundancia y producia
    empates masivos entre registros que solo compartian una palabra. Asi, cubrir
    tres terminos distintos de la peticion siempre gana a repetir uno.
    """
    matched: dict[str, list[str]] = {}
    crudo = raw_query.replace("\\", "/").lower()
    pesos = idf or {}

    campos = record_tokens(record)

    # Coincidencia literal de ruta: se comprueba contra la peticion cruda.
    score = 0.0
    exactas = {t for t in campos.pop("file_exact") if crudo and t in crudo}
    if exactas:
        matched["file_exact"] = sorted(exactas)
        score += FIELD_WEIGHTS["file_exact"] * len(exactas)

    # Para cada termino, el campo mas fuerte en el que aparece.
    mejor_campo: dict[str, str] = {}
    for campo, tokens in campos.items():
        for token in tokens & terms:
            actual = mejor_campo.get(token)
            if actual is None or FIELD_WEIGHTS[campo] > FIELD_WEIGHTS[actual]:
                mejor_campo[token] = campo

    for token, campo in mejor_campo.items():
        matched.setdefault(campo, []).append(token)
        score += FIELD_WEIGHTS[campo] * pesos.get(token, 1.0)

    for campo in matched:
        matched[campo].sort()

    # Cobertura de la peticion: un registro que toca tres terminos distintos es
    # mas pertinente que uno que toca uno, mas alla de la suma de sus pesos.
    if terms:
        cobertura = len(mejor_campo) / len(terms)
        score *= 1.0 + cobertura

    return score, matched


def retrieve(
    records: list[MemoryRecord],
    query: str,
    *,
    extra_terms: set[str] | None = None,
    hint_modules: list[str] | None = None,
    limit: int = 8,
    expand: bool = True,
) -> list[Hit]:
    """Devuelve los registros relevantes para una peticion, ordenados.

    El modelo local entra por dos puertas distintas, deliberadamente asimetricas:

    - `extra_terms`: sus palabras clave. Son terminos lexicos precisos, asi que
      cuentan igual que los de la peticion.
    - `hint_modules`: los modulos que ha senalado. Son demasiado gruesos para
      decidir pertenencia — 'mobile' admitiria todo lo etiquetado 'mobile' — asi
      que **no admiten registros**, solo reordenan. La unica excepcion son las
      restricciones: si la tarea toca un modulo, sus restricciones deben verse
      siempre, porque para eso existen.
    """
    terms = tokenize(query) | (extra_terms or set())
    if not terms:
        return []

    modulos = set(hint_modules or [])
    idf = build_idf(records)

    hits: dict[str, Hit] = {}
    for record in records:
        score, matched = _score_record(record, terms, query, idf)

        tocado = bool(modulos & set(record.modules))
        if tocado and score > 0:
            score *= 1.25  # el modelo confirma la zona: sube en el orden

        if score >= MIN_SCORE and _es_especifica(matched, idf):
            hits[record.id] = Hit(record, score, matched)
        elif tocado and record.type == "constraint":
            # Guardarail: entra por ser una regla del modulo afectado, no por
            # parecerse a la peticion. Se marca como tal.
            hits[record.id] = Hit(
                record,
                MIN_SCORE * 0.9,
                matched,
                via=f"restriccion vigente en {', '.join(sorted(modulos & set(record.modules)))}",
                seed="(analisis de intencion)",
            )

    if expand and hits:
        by_id = {r.id: r for r in records}
        derived = neighbours(derive_edges(records))
        # Solo las mejores semillas expanden, o el grafo arrastra medio proyecto.
        # Solo expanden las coincidencias directas. Una restriccion que entro
        # como guardarrail no es prueba de que el tema sea relevante, y si
        # sembrara, arrastraria a sus vecinos al contexto sin motivo.
        directos = [h for h in hits.values() if h.direct]
        mejor = max((h.score for h in directos), default=0.0)
        seeds = [
            h for h in sorted(directos, key=lambda h: -h.score)[:3]
            if h.score >= mejor * SEED_RATIO
        ]

        for seed in seeds:
            # Enlaces curados: afirmaciones explicitas del equipo. Entran todos.
            curados = [(l.target, f"enlace '{l.rel}'", 1.0) for l in seed.record.links]
            # Aristas derivadas de evidencia compartida: solo indicios, van con tope.
            indicios = sorted(
                ((e.target, e.describe(), min(e.weight / 6.0, 1.0))
                 for e in derived.get(seed.record.id, [])),
                key=lambda v: -v[2],
            )[:MAX_NEIGHBOURS_PER_SEED]

            for target_id, motivo, fuerza in [*curados, *indicios]:
                if target_id in hits or target_id not in by_id:
                    continue
                hits[target_id] = Hit(
                    record=by_id[target_id],
                    score=seed.score * HOP_DECAY * fuerza,
                    via=motivo,
                    seed=seed.record.id,
                )

    ordenados = sorted(hits.values(), key=lambda h: (-h.score, h.record.id))
    if not ordenados:
        return []

    # Corte relativo: se devuelve lo que compite con el mejor resultado, no un
    # cupo fijo. Los guardarrailes se conservan aunque puntuen bajo, porque no
    # compiten por relevancia sino por ser reglas del area afectada.
    techo = max(h.score for h in ordenados if h.direct) if any(
        h.direct for h in ordenados) else ordenados[0].score
    corte = techo * CUTOFF_RATIO
    filtrados = [
        h for h in ordenados
        if h.score >= corte or h.record.type == "constraint"
    ]
    return filtrados[:limit]
