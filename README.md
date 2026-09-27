# Context Manager

**Memoria de proyecto para desarrollo con IA.** Ejecuta localmente, recuerda las decisiones, los bugs
y las restricciones de tus proyectos, y entrega a Claude o GPT **solo el contexto relevante** para la
tarea que tienes delante.

No es un asistente de programación. Es la capa que hace que el asistente que ya usas no empiece de cero
cada conversación.

---

## El problema

Al programar con una IA de pago mediante prompts sueltos:

- el contexto de conversaciones anteriores se pierde;
- la IA desconoce decisiones que ya se tomaron;
- problemas ya resueltos reaparecen;
- hay que volver a explicar la arquitectura;
- se gastan tokens dando contexto repetitivo;
- la IA propone soluciones que en su día se descartaron;
- el conocimiento del proyecto queda disperso entre conversaciones.

El objetivo es poder decir simplemente:

> «Vamos a modificar la ventana de clientes para que los elementos del catalogo se muestren de dos en dos.
> Ten en cuenta los problemas que hemos tenido antes.»

y que el sistema recupere los bugs anteriores de esa zona, sus soluciones, las decisiones que aplican y
las restricciones que no se pueden romper — y nada más.

---

## Qué hace

```
                  MEMORIA CANÓNICA
                         │
                         ▼
                    TAREA NUEVA
                         │
                         ▼
                  RECUPERACIÓN          léxico + embeddings
                         │              fusionados con RRF
                         ▼
                  Context Builder
                         │
                         ▼
                    Claude / GPT ──────────► CAMBIO REAL
                                                  │
                                                  ▼
                                            OBSERVED      lo que dice git
                                                  ▼
                                            EXTRACTED     reglas deterministas
                                                  ▼
                                            PROPOSED      modelo local
                                                  ▼
                                            VERIFIED  ◄── una persona
                                                  │
                                                  ▼
                                          MEMORIA CANÓNICA
```

Dos mitades: **recuerda** lo que sabes del proyecto, y **aprende** observando el trabajo que haces.

---

## Principios de diseño

Son el resultado de medir, no de intuir. Cada uno salió de un experimento que contradijo una
expectativa (ver [`docs/RESULTADOS.md`](docs/RESULTADOS.md)).

| Principio | Por qué |
|---|---|
| **Las relaciones se computan, no se generan** | Los modelos locales inventaron aristas con un 13 % de precisión: 7 de cada 8 habrían sido falsas |
| **El modelo puede subir prioridad; no puede crear candidatos** | Sus módulos eran correctos pero tan gruesos que admitían todo lo etiquetado igual |
| **`PROPOSED ≠ MEMORIA`** | Con la evidencia correcta delante, el modelo aún distorsionó al comprimir |
| **Automatizar la captura no automatiza la confianza** | El hook observa solo; promocionar sigue siendo decisión de una persona |
| **Decir «no sé» es una respuesta válida** | Presentar reglas generales como experiencia previa es contaminación |

---

## Estado

**Arquitectura congelada** desde DEC-031. El ciclo funciona de extremo a extremo y está medido. Las
siguientes decisiones deben salir de fallos observados en uso real, no de anticipar problemas teóricos.

**31 decisiones** documentadas en [`DECISIONES.md`](DECISIONES.md), cada una con su contexto, su
motivo, sus alternativas descartadas y, cuando la hubo, la medición que la justificó.

### Resultados medidos

Sobre un corpus de 111 registros reales extraídos de un proyecto en producción, con 40 consultas
anotadas a mano y clasificadas por dificultad:

| Métrica | Léxico | Semántico | **Híbrido** |
|---|---|---|---|
| Recall@8 | 60,8 % | 46,6 % | **65,9 %** |
| MRR | 0,585 | 0,577 | **0,669** |
| nDCG@8 | 0,565 | 0,462 | **0,616** |
| Falsos precedentes | 1/6 | 0/6 | 1/6 |

La ganancia se concentra donde debía: los sinónimos duplican su recall y multiplican por 3,6 su nDCG,
sin que aumenten los falsos precedentes. Detalle completo en [`docs/RESULTADOS.md`](docs/RESULTADOS.md).

---

## Tecnologías

| Pieza | Qué es | Papel |
|---|---|---|
| **Python 3.13** | lenguaje | todo el sistema |
| **Ollama** + `llama3.2:3b` | modelo local | clasifica, extrae entidades, resume. Nunca decide relaciones |
| **`nomic-embed-text`** | embeddings, 768 dim | descubrimiento semántico de candidatos |
| **FalkorDB** (Docker) | base de datos de grafos | índice del grafo de memoria |
| **Graphiti** | framework de grafo temporal | capa sobre FalkorDB |
| **JSONL** | archivos de texto | **fuente de verdad** de la memoria |
| **Pydantic** | validación | esquema de la memoria |
| **Claude / GPT** | IA de pago | el razonamiento pesado, fuera del sistema |

Diseñado para hardware modesto: se desarrolló y midió en un i7-8750H con 16 GB de RAM y una GTX 1050 Ti
de 4 GB. **No hace falta GPU potente**: el modelo de 3B es suficiente para el papel que se le asigna.

---

## Requisitos

- **Python 3.13** — no 3.14: `graphiti-core` todavía no lo soporta
- **Ollama** con `llama3.2:3b` y `nomic-embed-text`
- **Docker** (solo si quieres el grafo; la recuperación funciona sin él)
- **Git**

---

## Instalación

```bash
git clone <tu-repo> context-manager
cd context-manager

py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Modelos locales:

```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

Motor de grafos (opcional):

```bash
docker compose up -d
```

### Tropiezos conocidos

| Síntoma | Causa | Solución |
|---|---|---|
| `ModuleNotFoundError: httpx` | `graphiti-core` lo importa sin declararlo | ya está fijado en `requirements.txt` |
| `openai.OpenAIError: Missing credentials` | Graphiti crea un reranker contra la API real de OpenAI | `src/acm/graph.py` lo apunta a Ollama |
| Ollama «conexión denegada» con el puerto abierto | proxy del sistema interceptando localhost | `NO_PROXY=127.0.0.1,localhost` |
| `llama runner process has terminated` | el modelo no cabe en memoria | usa un 3B, no un 7B, si tienes 4 GB de VRAM |

---

## Pruébalo en dos minutos

Sin conectar ningún repositorio tuyo:

```bash
python tools/seed_demo.py
```

Crea un proyecto ficticio con 14 registros. Ahora pregunta:

```bash
python ask.py "el carrito se vacia al perder la conexion" --project demo-tienda --no-llm --lexico
```

Recupera el bug correcto. Y lo más importante:

```bash
python ask.py "como integro los pagos con stripe" --project demo-tienda --no-llm --lexico
```

Responde que **no hay memoria relevante** y que lo trates como territorio nuevo, porque ese proyecto no
tiene nada sobre pagos. El sistema no inventa experiencia que no existe.

Cuando sí hay reglas del área afectada pero ningún precedente del problema, el contexto lo dice
explícitamente con un aviso **`SIN PRECEDENTES REGISTRADOS`** y separa las dos cosas: presentar reglas
generales como experiencia previa sería contaminación.

> **Nota:** con solo 14 registros la recuperación es deliberadamente conservadora y algunas consultas
> no devolverán nada aunque el registro exista. No es un fallo del demo: ver
> [Limitaciones conocidas](#limitaciones-conocidas).

---

## Uso con tu proyecto

### 1. Registrar el proyecto

```bash
python context_manager.py init C:\ruta\a\tu\repo --name MiProyecto
```

Detecta git, el stack (por presencia de `package.json`, `*.csproj`, `docker-compose.yml`…) y la
estructura de directorios. Todo es **evidencia observada**, nada lo infiere un modelo.

### 2. Sembrar memoria desde el historial

```bash
python tools/extract_from_git.py --project miproyecto --limit 95 --write
```

Extrae bugs y cambios de los mensajes de commit. Los commits sin cuerpo se marcan `INFERENCE`: el
asunto dice qué se tocó, no por qué.

### 3. Pedir contexto antes de trabajar

```bash
python ask.py "lo que vayas a hacer" --project miproyecto --stats
```

Produce un bloque de texto listo para pegar en Claude o GPT.

### 4. Aprender de lo que hiciste

```bash
python context_manager.py hook install --project miproyecto   # una sola vez
```

A partir de ahí, cada commit crea un `OBSERVED` automáticamente. El hook **nunca bloquea el commit**:
si el sistema está roto, avisa y deja pasar.

```bash
python context_manager.py session start  --project miproyecto --goal "..."
# ...trabajas normalmente con tu IA...
python context_manager.py session import --project miproyecto   # eliges la explicación
git commit -m "..."                                             # el hook observa
python learn.py propose --project miproyecto --all
python learn.py verify  --project miproyecto TASK-001           # [A] Aceptar [E] Editar [R] Rechazar
```

### 5. Ver si el ciclo se está alimentando

```bash
python context_manager.py status --project miproyecto
```

Embudo del ciclo, antigüedad de lo pendiente, tasa de verificación, cuánto corriges al modelo por
campo, sesiones cerradas sin justificación y estado del hook.

---

## Integración con tu IDE (VS Code, Antigravity, Orca)

En lugar de ejecutar `ask.py` y pegar el bloque a mano, puedes exponer el Context
Manager como **servidor MCP** para que el agente de tu editor pida el contexto por
sí mismo antes de tocar el código. Un solo servidor cubre **Visual Studio Code**,
**Google Antigravity** y **Orca** ([tryorca.com](https://tryorca.com/)) —y cualquier
otro cliente MCP— porque los tres hablan el mismo protocolo.

```bash
# 1. registra el repo (crea .context/project.json, que el servidor lee)
python context_manager.py init /ruta/a/tu/repo --name MiProyecto
# 2. apunta la config MCP del IDE al lanzador integrations/run-context-mcp.(sh|cmd)
```

El agente gana la herramienta `pedir_contexto` (y `buscar_memoria`,
`detalle_registro`, `listar_proyectos`, `estado_proyecto`). El servidor **solo
lee** la memoria: promocionar sigue siendo un paso humano por CLI. No añade
dependencias —usa solo la biblioteca estándar— y degrada a léxico si Ollama no
está.

Instrucciones completas por IDE en [`integrations/README.md`](integrations/README.md).

---

---

## Consumo de recursos

La IA local son dos piezas con relación coste-beneficio **opuesta**:

| Pieza | Coste | Beneficio medido |
|---|---|---|
| `llama3.2:3b` (intención) | 4–10 s por consulta, ~2 GB residentes | solo reordena candidatos |
| `nomic-embed-text` | ~0,3 s, ~300 MB | recall de sinónimos ×2, nDCG ×3,6 |

El modelo caro es el que menos aporta, así que en vez de un interruptor hay **tres modos**:

```bash
python context_manager.py ia estado
```

| Modo | Qué usa | Cuándo |
|---|---|---|
| `completo` | intención + embeddings | cuando no importa esperar |
| **`ahorro`** | solo embeddings | **por defecto**: conserva casi toda la calidad sin los 2 GB |
| `minimo` | solo léxico | sin Ollama en absoluto |

```bash
python context_manager.py ia ahorro
```

El modo es global, con anulación por proyecto (`--project`), y lo respetan `ask.py` y el servidor MCP
por igual. Eso último importa: **el IDE lanza el servidor MCP y no puede pasarle banderas**, así que
sin un ajuste persistente la integración intentaría siempre usar el modelo generativo.

Para recuperar la memoria que Ollama retiene tras la última llamada:

```bash
python context_manager.py ia descargar
```

> **El mayor ahorro no está aquí.** Ningún comando del flujo diario usa el grafo: `ask.py`, `learn.py`,
> `context_manager.py` y el servidor MCP leen JSONL y el índice vectorial directamente. Si no vas a
> ejecutar `tests/smoke_stack.py`, apaga Docker con `docker compose down` y recuperas los ~4 GB que
> WSL2 reserva.

## Estructura

```
├── ask.py                  consulta → bloque de contexto
├── learn.py                observe · propose · verify · stats
├── context_manager.py      init · session · hook · status
├── src/acm/
│   ├── models.py           esquema de memoria y procedencia
│   ├── store.py            persistencia JSONL, aislada por proyecto
│   ├── retrieval.py        recuperación léxica  ← CONGELADO
│   ├── semantic.py         embeddings e índice vectorial
│   ├── hybrid.py           fusión RRF           ← CONGELADO
│   ├── context.py          Context Builder
│   ├── intent.py           análisis de intención con el modelo local
│   ├── observe.py          OBSERVED → EXTRACTED → PROPOSED
│   ├── review.py           verificación editable y métricas de corrección
│   ├── events.py           evento de tarea y evidencias tipadas
│   ├── sessions.py         sesiones de desarrollo
│   ├── transcripts.py      lectura de transcripciones de agentes CLI
│   ├── projects.py         registro y aislamiento multiproyecto
│   └── hooks.py            hook post-commit
├── integrations/           servidor MCP para IDE (VS Code, Antigravity, Orca)
│   ├── mcp_server.py       servidor MCP stdio, solo biblioteca estándar
│   ├── run-context-mcp.sh  lanzador Linux/macOS
│   ├── run-context-mcp.cmd lanzador Windows
│   └── vscode/ antigravity/ orca/   plantillas de configuración por IDE
├── tests/                  banco de evaluación y comparación de estrategias
│   ├── evalset.py          19 consultas anotadas sobre el proyecto de ejemplo
│   └── compare_retrieval.py  léxico vs semántico vs híbrido
├── tools/
│   ├── seed_demo.py        proyecto de ejemplo, 14 registros
│   └── extract_from_git.py siembra memoria desde el historial
└── DECISIONES.md           las 31 decisiones, con sus mediciones
```

---

## Limitaciones conocidas

**Arranque en frío.** Los umbrales de especificidad están calibrados sobre un corpus de ~111
registros. Con menos de ~30, la recuperación es demasiado conservadora y rechaza aciertos legítimos:
un término que aparece en 3 registros no supera el umbral de rareza hasta que el corpus llega a 31.
Un proyecto nuevo pasa por esa zona hasta acumular memoria suficiente. Mitiga sembrando desde el
historial de git (paso 2).

**Sinónimos.** Aun con embeddings, el recall en consultas por sinónimo se queda en 0,300. Ayudan, no
resuelven. Es la categoría con más margen del sistema.

**Polisemia del español.** «tiempo real» casa con «solución real». Se dejó sin parchear a propósito:
arreglarlo con una lista de palabras sería ajustar al banco de pruebas.

**Vocabulario del extractor.** `tools/extract_from_git.py` tiene un diccionario de temas orientado al
proyecto piloto. Degrada con elegancia (genera menos etiquetas), pero conviene adaptarlo al dominio.

**Proporción de `INFERENCE`.** La extracción masiva desde git produce muchos registros sin explicación
confirmada. Viajan marcados y el Context Builder los presenta como no confirmados, pero pueden ser el
grueso del corpus.

---

## Lo que este sistema NO hace

- No escribe código.
- No llama a la IA de pago: genera el contexto para que lo pegues tú.
- No promociona nada a memoria sin que una persona lo verifique.
- No guarda conversaciones completas: solo la explicación del cambio.
- No deja que un modelo afirme relaciones entre registros.

---

## Documentación

| Documento | Contenido |
|---|---|
| [`DECISIONES.md`](DECISIONES.md) | Las 31 decisiones, con contexto, motivo, alternativas y mediciones. **La fuente de verdad** |
| [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) | Cómo encajan las piezas y por qué están separadas así |
| [`docs/RESULTADOS.md`](docs/RESULTADOS.md) | Los experimentos y sus números |
| [`docs/notas/`](docs/notas/) | Notas de diseño en bruto de las sesiones de trabajo |

---

## Créditos

Construido como sistema de memoria para desarrollo asistido por IA, validado sobre un proyecto real en
producción. El reparto de responsabilidades que lo sostiene:

```
Git                 ──  evidencia
Claude / GPT        ──  evidencia (justificación)
Reglas deterministas ─  relaciones
Ollama              ──  inferencia
Humano              ──  verificación
```

---

## Licencia

**MIT.** Uso, copia, modificación y distribución libres, incluso comercialmente. El software se
entrega *tal cual*, **sin garantía de ningún tipo**, y el autor **no se hace responsable** de ningún
daño derivado de su uso. Texto completo en [LICENSE](LICENSE).
