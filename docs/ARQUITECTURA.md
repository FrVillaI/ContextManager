# Arquitectura

Este documento explica **cómo encajan las piezas y por qué están separadas así**. Las decisiones
concretas, con sus alternativas descartadas, están en [`DECISIONES.md`](../DECISIONES.md).

---

## El principio que lo ordena todo

Cada componente responde a una pregunta distinta, y ninguno invade el papel de otro:

```
┌──────────────────────────────────┐
│ Git                              │
│ "¿Cuál es el código real?"       │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│ Memoria (JSONL + grafo)          │
│ "¿Qué sabemos del proyecto?"     │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│ Modelo local                     │
│ "¿Qué contexto hace falta?"      │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│ Claude / GPT                     │
│ "¿Cómo resuelvo esta tarea?"     │
└──────────────────────────────────┘
```

De ahí sale la regla que atraviesa el sistema entero:

> **El modelo puede aumentar prioridad; no puede crear candidatos canónicos.**

---

## Las dos mitades

### Recuperación — qué sabemos

```
                     CONSULTA
                        │
             ┌──────────┴──────────┐
             ▼                     ▼
         LÉXICO                EMBEDDINGS
       (congelado)           (descubrimiento)
             │                     │
      candidatos A           candidatos B
             │                     │
             └──────────┬──────────┘
                        ▼
                      RRF              fusión por posición,
                        │              no por puntuación
                        ▼
                 CANDIDATE SET
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
        Evidencia léxica    Módulos del modelo
                            (solo reordenan)
              └─────────┬─────────┘
                        ▼
                    RANKING
                        │
                        ▼
          Precedentes  ·  Guardarraíles
```

### Aprendizaje — qué acabamos de descubrir

```
   SESIÓN DE DESARROLLO
          │
   ┌──────┼──────┬────────────┐
   ▼      ▼      ▼            ▼
  Git  Commit  Rationale    Tests
          └──────┼────────────┘
                 ▼
             TaskEvent
                 │
            ┌────┴────┐
            ▼         ▼
       EVIDENCIA  INFERENCIA
            └────┬────┘
                 ▼
          [A] [E] [R]   ← una persona
                 ▼
             VERIFIED
```

---

## Decisiones estructurales

### La memoria son archivos, el grafo es un índice

La fuente de verdad son archivos **JSONL versionados en git**, uno por tipo de memoria. La base de
datos de grafos es un **índice reconstruible**.

Migrar de máquina es `git clone` + reconstruir. Cambiar de motor de grafos deja de ser una migración y
pasa a ser una reindexación. Un grafo corrupto deja de ser pérdida de datos. Y la memoria queda
**legible y auditable por una persona**, que es imprescindible para revisar procedencia.

### El aislamiento entre proyectos es físico

Cada proyecto vive en `memory/<project_id>/`, y el almacén pertenece siempre a un proyecto. Una
consulta sobre un proyecto **no puede** alcanzar un registro de otro porque ni siquiera lee ese
directorio. Además el almacén rechaza escribir un registro ajeno.

Un filtro `WHERE project_id = ?` se puede olvidar aplicar. Un directorio distinto, no.

La identidad real de un registro es `project_id + id`: dos proyectos pueden tener cada uno su `BUG-001`
sin colisionar.

### La procedencia es obligatoria

```python
class Provenance(str, Enum):
    FACT       # confirmado contra el código, el repo o una persona
    INFERENCE  # deducido por un modelo, sin confirmar
    PROPOSAL   # propuesta que aún no se ha implementado
    DECISION   # decisión aceptada explícitamente
    RESOLVED   # problema confirmado como solucionado
```

`provenance` y `source` **no tienen valor por defecto**. Es imposible crear memoria sin declarar de
dónde sale: la disciplina la impone el tipo, no la buena voluntad.

Solo `{FACT, DECISION, RESOLVED}` puede presentarse a la IA de pago como afirmación. El resto viaja
marcado.

### `decision` y `constraint` se separan por función

Un mismo hecho produce ambas cosas:

```
DECISION   — qué se decidió y por qué      →  precedente histórico
    │ deriva_en
    ▼
CONSTRAINT — qué no debe violarse           →  guardarraíl
```

Los cuatro modelos del benchmark fallaron en los mismos tres registros intentando elegir entre las dos
categorías. Tenían parte de razón: la diferencia no está en el contenido, sino en el uso. Por eso no se
fuerza la elección.

Eso permite tratarlas distinto en la recuperación: las restricciones del módulo afectado se muestran
siempre; las decisiones solo entran por evidencia.

### La escalera de confianza

```
OBSERVED     lo que dice git. Verificable, no opinable
    ↓
EXTRACTED    estructura derivada por regla fija
    ↓
PROPOSED     interpretación del modelo local
    ↓
VERIFIED     confirmado por una persona
```

Solo `VERIFIED` entra en la memoria canónica. Lo anterior vive en `memory/<project_id>/pending/` y no
participa en ninguna recuperación — otra vez, separación física.

Al verificar se conservan **las dos versiones**:

```json
"proposal":     { "title": "…", "generated_by": "llama3.2:3b" },
"verification": { "title": "…", "verified_by": "human",
                  "corrected_fields": ["summary"] }
```

Eso da la traza completa —qué creyó la IA, qué corrigió la persona, qué entró en memoria— y permite
medir cuánto se equivoca el modelo al comprimir.

---

## Por qué las relaciones no las propone el modelo

Es la decisión más importante del sistema, y salió de una medición:

| Modelo | Precisión de relaciones | Inventadas |
|---|---|---|
| `llama3.2:3b` | 13 % | 14 en 16 registros |
| `qwen2.5:3b` | 11 % | 16 en 16 registros |
| `phi3:mini` | 7 % | 14 en 16 registros |

Aproximadamente **una relación falsa por registro**. Aceptarlas significaría que siete de cada ocho
aristas del grafo serían falsas: no una memoria degradada, sino una memoria activamente engañosa, cuyo
daño se agrava porque esas aristas se recuperarían como contexto de tareas futuras.

Las relaciones salen, por este orden:

1. **Fuentes deterministas** — archivos y módulos compartidos, cercanía en el historial, referencias
   explícitas por identificador.
2. **Declaración de una persona**, que entra como hecho.
3. Si alguna vez el modelo sugiere relaciones, entran como `PROPOSAL` y no se indexan sin confirmar.

Al derivar aristas se pesa la **rareza**: un archivo que toca casi cada commit no es evidencia de que
dos registros tengan relación.

---

## Por qué la fusión es por posición

Un score léxico y una similitud coseno no viven en la misma escala. Ponderarlos entre sí exigiría
inventar un factor de conversión arbitrario. **RRF (Reciprocal Rank Fusion)** solo necesita saber quién
va antes.

### El problema que hubo que resolver

Los embeddings **no tienen señal natural de «aquí no hay nada»**. Medido sobre 40 consultas:

| Categoría | Similitud máxima | z-score |
|---|---|---|
| Consultas legítimas | 0,581 – 0,742 | 1,57 – 3,61 |
| Dominios inexistentes | 0,588 – 0,667 | 1,45 – 2,21 |

Las distribuciones se solapan. Ningún umbral absoluto las separa. Por eso un candidato semántico se
admite solo si **destaca del fondo del corpus**: `similitud ≥ 0,68` **o** `z-score ≥ 2,4`.

Esos umbrales están calibrados sobre ese corpus. **No son constantes universales**: si el corpus cambia
mucho, hay que volver a medirlos.

---

## Qué hace exactamente el modelo local

Lo que el benchmark demostró que hace bien, y nada más:

| Tarea | ¿Lo hace? | Medido |
|---|---|---|
| Producir JSON válido | sí | 100 % |
| Clasificar el tipo de registro | aceptable | 81 % |
| Extraer módulos afectados | aceptable | 55 % |
| Generar palabras clave de búsqueda | sí | — |
| Resumir un cambio | con supervisión | distorsiona al comprimir |
| **Proponer relaciones** | **no** | **13 % de precisión** |
| **Decidir qué es relevante** | **no** | sus módulos son demasiado gruesos |

Un detalle que conviene recordar: en una prueba el modelo declaró **«confianza alta»** mientras su
propio resumen admitía *«no se proporciona más información»*. Por eso el campo de confianza declarada
**se guarda pero no se usa** para decidir promociones.

---

## Código congelado

`src/acm/retrieval.py` y `src/acm/hybrid.py` están **congelados** salvo recalibración de umbrales
(DEC-022). `hybrid.py` **compone** sobre `retrieval.py` en lugar de modificarlo: cambiar de estrategia
es cambiar de función, no editar la anterior, de modo que comparar las tres siempre es honesto.
