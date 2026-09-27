# Registro de Decisiones — AI Context Manager Local

> **Regla permanente del proyecto:** toda decisión técnica se documenta aquí antes o en el mismo momento
> en que se aplica. Ninguna decisión vive solo en la conversación. Si una decisión se revierte, no se
> borra: se marca como `SUPERSEDED` y se enlaza la que la reemplaza.

**Formato de cada entrada**

| Campo | Significado |
|---|---|
| `Estado` | `PROPUESTA` · `ACEPTADA` · `SUPERSEDED` · `RECHAZADA` |
| `Contexto` | Qué problema obligó a decidir |
| `Decisión` | Qué se eligió, en una frase |
| `Motivo` | Por qué esa y no las otras |
| `Consecuencias` | Qué obliga o impide hacia adelante |
| `Alternativas` | Qué se descartó y por qué |

> Nota: estos `DEC-xxx` son decisiones **sobre el sistema que estamos construyendo**. No confundir con
> los `ADR-xxx` que el sistema almacenará en Graphiti como memoria **de los proyectos gestionados**.

---

## Índice

31 decisiones. `SUPERSEDED` significa que fue reemplazada: no se borra, se conserva con el
motivo por el que cayó.

| # | Decisión | Estado |
|---|---|---|
| [DEC-001](#dec-001) | Backend de grafo para Graphiti: FalkorDB Lite embebido | `SUPERSEDED` |
| [DEC-002](#dec-002) | La memoria es portable por exportación, no por la base de datos | `ACEPTADA` |
| [DEC-003](#dec-003) | LLM de ingesta: 100% local, pero con medición previa obligatoria | `ACEPTADA` |
| [DEC-004](#dec-004) | Salida hacia la IA de pago: generación de prompt, no llamada por API | `ACEPTADA` |
| [DEC-005](#dec-005) | Proyecto piloto: el proyecto piloto | `ACEPTADA` |
| [DEC-006](#dec-006) | Entorno de ejecución: Python 3.13 aislado | `ACEPTADA` |
| [DEC-007](#dec-007) | Backend de grafo: Neo4j Community Server | `SUPERSEDED` |
| [DEC-008](#dec-008) | Backend de grafo: Docker Desktop + FalkorDB | `ACEPTADA` |
| [DEC-009](#dec-009) | Esquema de la memoria: envoltura común con procedencia obligatoria | `ACEPTADA` |
| [DEC-010](#dec-010) | Métricas del benchmark de modelos locales | `PROPUESTA` |
| [DEC-011](#dec-011) | Presupuesto de RAM: WSL2 limitado a 4 GB | `ACEPTADA` |
| [DEC-012](#dec-012) | Modelo local del Context Manager: `llama3.2:3b` | `ACEPTADA` |
| [DEC-013](#dec-013) | Las relaciones del grafo no se infieren con el modelo local | `ACEPTADA` |
| [DEC-014](#dec-014) | `decision` y `constraint` se separan por función, no por contenido | `ACEPTADA` |
| [DEC-015](#dec-015) | El modelo local entra en la recuperación por dos puertas asimétricas | `ACEPTADA` |
| [DEC-016](#dec-016) | La métrica principal de Fase 1 es la precisión de recuperación, no la reducción de contexto | `ACEPTADA` |
| [DEC-017](#dec-017) | Jerarquía de señal en la coincidencia de rutas | `ACEPTADA` |
| [DEC-018](#dec-018) | Un Context Manager, múltiples proyectos aislados | `ACEPTADA` |
| [DEC-019](#dec-019) | Línea base medida de la recuperación | `ACEPTADA` |
| [DEC-020](#dec-020) | La recuperación semántica entra como descubrimiento, no como evidencia | `ACEPTADA` |
| [DEC-021](#dec-021) | La recuperación híbrida es la estrategia oficial de descubrimiento | `ACEPTADA` |
| [DEC-022](#dec-022) | Se cierra la etapa experimental de recuperación | `ACEPTADA` |
| [DEC-023](#dec-023) | Escalera de confianza para la observación post-tarea | `ACEPTADA` |
| [DEC-024](#dec-024) | El ciclo completo, verificado de extremo a extremo | `ACEPTADA` |
| [DEC-025](#dec-025) | La justificación de la tarea es evidencia de primera clase | `ACEPTADA` |
| [DEC-026](#dec-026) | Verificación editable de propuestas | `ACEPTADA` |
| [DEC-027](#dec-027) | Hook de git post-commit hacia OBSERVED | `ACEPTADA` |
| [DEC-028](#dec-028) | Interpretación de las métricas de corrección | `ACEPTADA` |
| [DEC-029](#dec-029) | Captura de sesión, no captura de Claude | `ACEPTADA` |
| [DEC-030](#dec-030) | Adaptador de CLI: leer la transcripción, no envolver la herramienta | `ACEPTADA` |
| [DEC-031](#dec-031) | Congelación arquitectónica y fase de uso real | `ACEPTADA` |

> Las anclas de esta tabla dependen del renderizador. Si un enlace no salta, busca el `DEC-xxx` con
> la búsqueda del navegador.

---

---

# Entorno verificado y receta de replicación

> Esta sección es el estado real comprobado del equipo, no lo que debería ser. Sirve para levantar el
> sistema desde cero en otra máquina. Última verificación: **2026-08-20**.

## Versiones exactas en uso

| Pieza | Versión | Nota |
|---|---|---|
| SO | Windows 11 Home Single Language 10.0.26200 | |
| CPU / RAM / GPU | i7-8750H · 16 GB DDR4 · GTX 1050 Ti 4 GB VRAM | el 7B Q4 no cabe en VRAM |
| Python del proyecto | **3.13.15** en `.venv` | el 3.14.4 del sistema queda intacto |
| `graphiti-core` | 0.29.3 | |
| `falkordb` (cliente) | 1.7.1 | |
| `httpx` | 0.28.1 | dependencia no declarada por graphiti-core |
| `pydantic` | 2.13.4 | |
| Ollama | 0.22.0 | |
| WSL | 2.7.12.0 · kernel 6.18.33.2-2 | |
| Docker Engine | 29.7.2 | |
| Imagen del grafo | `falkordb/falkordb:latest` | contenedor `acm-falkordb` |

## Pasos para replicar

0. `projects.json` y `memory/` **no viajan en el repositorio**: contienen rutas absolutas y
   memoria de proyectos privados. Ver `projects.example.json` y `tools/seed_demo.py`.
1. Instalar **Python 3.13** (no 3.14: `graphiti-core` no lo soporta) y crear el entorno:
   `py -3.13 -m venv .venv`
2. `.venv\Scripts\python.exe -m pip install -r requirements.txt`
3. Instalar **Ollama** y descargar los modelos del banco de pruebas (ver DEC-010).
4. Instalar **WSL2** (`wsl --install`, requiere administrador y reinicio) y **Docker Desktop**.
5. Copiar `.wslconfig` al perfil del usuario **antes** del primer arranque de Docker (ver DEC-011).
6. `docker compose up -d` para levantar FalkorDB.
7. Reconstruir la memoria desde los `JSONL` versionados (DEC-002). Sembrado inicial:
   `.venv\Scripts\python.exe tests/seed_piloto.py`

## Tropiezos ya resueltos (no repetirlos)

| Síntoma | Causa real | Solución |
|---|---|---|
| `pip install graphiti-core[falkordblite]` falla al construir | `redislite` no soporta win32 | No existe FalkorDB embebido en Windows. Ver DEC-001 |
| `ollama` responde "conexión denegada" pero el puerto 11434 escucha | proxy del sistema interceptando localhost | Usar `--noproxy '*'` en curl, o `NO_PROXY=127.0.0.1,localhost` |
| `docker` no aparece en el PATH | la sesión de terminal es anterior a la instalación | Usar la ruta completa o reabrir la terminal |
| `error getting credentials: docker-credential-desktop not found` | mismo PATH heredado | Anteponer al PATH la carpeta `resources` + `bin` dentro de `C:/Program Files/Docker/Docker` |
| `Invoke-RestMethod -NoProxy` da error de parámetro | `-NoProxy` no existe en PowerShell 5.1 | Usar `curl --noproxy` |
| Ollama deja de responder sin motivo aparente | el equipo se reinició | `ollama serve` no se relanza solo si no está como servicio |
| `ModuleNotFoundError: No module named 'httpx'` | `graphiti-core` 0.29.3 importa `httpx` pero **no lo declara** como dependencia, y `openai` 3.3.1 ya migró a `httpx2` | Instalar `httpx` de forma explícita; está fijado en `requirements.txt` |
| `openai.OpenAIError: Missing credentials` al construir `Graphiti` | si no se pasa `cross_encoder`, Graphiti instancia por defecto un reranker contra la API real de OpenAI | Pasar `OpenAIRerankerClient` apuntado a Ollama, como hace `src/acm/graph.py` |
| `llama runner process has terminated` | el modelo no cabe en memoria | Ver la medición de DEC-010: el 7B Q4 no arranca en este equipo |

---

## DEC-001 — Backend de grafo para Graphiti: FalkorDB Lite embebido

- **Estado:** SUPERSEDED por [DEC-007](#dec-007--backend-de-grafo-neo4j-community-server) el 2026-08-20
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario

> **Por qué cayó:** `falkordblite` **no soporta Windows**. Depende de `redislite`, cuyo build falla con
> `The redislite module is not supported on the 'win32' platform`. El error aparece al resolver las
> dependencias de compilación, antes de instalar nada, así que la opción es inviable en este equipo.
> Fallo de análisis propio: verifiqué la compatibilidad de versiones de Python de `falkordblite` pero
> no la de sistema operativo.

### Contexto
Graphiti necesita una base de datos de grafos. El equipo no tiene Docker instalado. Los drivers
soportados por `graphiti-core` 0.29.3 son Neo4j, FalkorDB, Kuzu (deprecado, upstream sin mantenimiento)
y Amazon Neptune. Requisito explícito del usuario: poder **migrar entre portátiles** y poder
**levantar el servicio más adelante** reutilizando lo ya configurado.

### Decisión
Se usa **FalkorDB Lite embebido** (`graphiti-core[falkordblite]`), que levanta el motor dentro del
propio proceso Python y persiste en un archivo local, sin servidor ni Docker.

### Motivo
- **Coste de memoria casi nulo.** En un equipo de 16 GB donde el modelo local no cabe entero en los
  4 GB de VRAM y tirará de RAM y CPU, regalar 1–2 GB a una JVM (Neo4j) o al backend WSL2 de Docker
  Desktop es caro. Lite consume decenas de MB.
- **Ruta de crecimiento sin reescritura.** Lite es el mismo motor que FalkorDB servidor y su API
  refleja la del cliente estándar. Levantar el servicio más adelante es cambiar la cadena de conexión
  de socket local a TCP: el driver de Graphiti y el código de la aplicación no cambian.
- **Cero instalación fuera de Python.** Entra por `pip`, no añade dependencias de sistema.

### Consecuencias
- Fija Python 3.12 o superior como mínimo (ver DEC-006).
- Durante el PoC no hay navegador visual del grafo; la inspección se hace por consulta Cypher desde
  Python y, sobre todo, leyendo los `JSONL` de DEC-002. Si se necesita la vista visual, se levanta el
  servidor FalkorDB y se apunta ahí sin tocar código.

### Alternativas descartadas
- **Neo4j Desktop:** el más maduro y su navegador visual es genuinamente útil, pero cuesta 1–2 GB de
  RAM permanentes que compiten con la inferencia local.
- **Docker + FalkorDB:** lo más cercano a producción, pero exige instalar Docker Desktop y su reserva
  de memoria sin aportar nada que Lite no dé ya en esta fase.
- **Kuzu:** descartado por estar deprecado en `graphiti-core` y sin mantenimiento upstream.

---

## DEC-002 — La memoria es portable por exportación, no por la base de datos

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario

### Contexto
La pregunta "¿cómo migro entre portátiles?" se responde mal si se responde eligiendo base de datos.
Ninguna de las opciones permite copiar datos entre motores distintos: cambiar de FalkorDB a Neo4j
implicaría reconstruir el grafo, no copiar un archivo.

### Decisión
La **fuente de verdad de la memoria** son archivos `JSONL` versionados en git, uno por tipo de memoria
(`bugs.jsonl`, `decisions.jsonl`, `constraints.jsonl`, `solutions.jsonl`, `changes.jsonl`,
`project.jsonl`). La base de datos de grafos se trata como un **índice reconstruible**, no como
almacenamiento primario. Debe existir siempre el comando `rebuild` que regenera el grafo completo
desde los `JSONL`.

### Motivo
- Migrar de portátil = `git clone` + `rebuild`. Sin dumps, sin binarios, sin versiones de motor.
- Cambiar de motor de grafos deja de ser una migración y pasa a ser un `rebuild`.
- La memoria queda **legible y auditable por humanos**, requisito implícito de la sección 15 de la
  especificación (validar procedencia `FACT`/`INFERENCE`/`PROPOSAL`).
- Un grafo corrupto o un experimento fallido deja de ser pérdida de datos.
- El historial de git sobre los `JSONL` da gratis la evolución de la memoria en el tiempo.

### Consecuencias
- Toda escritura en memoria pasa primero por el `JSONL` y luego indexa en el grafo. Nunca al revés.
- El grafo puede borrarse en cualquier momento sin pérdida.
- Obliga a definir un esquema estable de los registros `JSONL` (ver DEC-009).

### Alternativas descartadas
- **Dump nativo del motor** (`neo4j-admin dump`, RDB de FalkorDB): ata la memoria a un motor y a una
  versión concreta; ilegible para humanos; inútil para revisar procedencia.

---

## DEC-003 — LLM de ingesta: 100% local, pero con medición previa obligatoria

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario

### Contexto
Graphiti usa un LLM de forma intensiva para extraer entidades y relaciones con salida estructurada.
Es la operación más exigente del sistema y la más frágil en modelos pequeños. Hardware: GTX 1050 Ti
con 4 GB de VRAM. Un modelo 7B Q4 (~4.7 GB) no entra completo en VRAM; un 3B Q4 (~2 GB) sí.

### Decisión
La ingesta se hace **100% local con Ollama**. Antes de fijar el modelo, la Fase 1 incluye un
**benchmark obligatorio**: ingerir el mismo conjunto de 5 bugs y 5 decisiones con 2–3 modelos locales
distintos y comparar calidad del grafo resultante, validez del JSON y tiempo por registro. El modelo
se elige con datos medidos, no por intuición.

### Motivo
Soberanía total del dato y coste cero, que es el propósito declarado del proyecto. El riesgo de
calidad es real pero acotado: la ingesta es poco frecuente y su salida es auditable en los `JSONL`
antes de indexarse.

### Consecuencias
- La Fase 1 no se declara superada hasta tener la tabla de resultados del benchmark.
- Se necesitan métricas definidas antes de medir (ver DEC-010).
- Si ningún modelo local alcanza calidad aceptable, se reabre esta decisión de forma explícita como
  `SUPERSEDED`, no de forma silenciosa.

### Alternativas descartadas
- **Híbrido (API de pago para ingesta, local para contexto):** más fiable y barato en la práctica,
  pero rompe el objetivo de control local y añade dependencia de una API key.

---

## DEC-004 — Salida hacia la IA de pago: generación de prompt, no llamada por API

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario

### Contexto
La Fase 4 debe entregar el contexto construido a Claude/GPT. Puede hacerse por API o generando un
bloque de texto para pegar manualmente.

### Decisión
El sistema **genera el bloque de contexto** y lo deja disponible (archivo y/o portapapeles) para
pegarlo en Claude Code o en la web. No se llama a ninguna API de pago.

### Motivo
- Coste adicional cero: aprovecha la suscripción existente.
- El contexto queda **visible e inspeccionable antes de enviarse**, que es exactamente lo que hay que
  validar en el PoC (sección 22, paso 10 de la especificación).
- Elimina el manejo de API keys del alcance inicial.

### Consecuencias
- El ciclo post-tarea (Fase 5) no puede ser automático de extremo a extremo: arrancará desde
  `git diff` a petición del usuario, no desde la respuesta del modelo.
- La salida debe ser texto plano copiable, con formato estable y legible.

---

## DEC-005 — Proyecto piloto: el proyecto piloto

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20

### Contexto
Se evaluaron dos proyectos reales como piloto para cargar memoria:
`<ruta-del-repositorio>` y `Documents\Proyectos\Pokemon-living_dex\PKHeX_API`.

### Decisión
El proyecto piloto es **el proyecto piloto**.

### Motivo
- **PKHeX_API no es un repositorio git** (no tiene `.git`), por lo que no puede alimentar la Fase 5,
  que depende de `git diff` como fuente de conocimiento nuevo. Eso lo descarta por sí solo.
- el proyecto piloto tiene 166 commits en `main` y documentación densa: `API_SPEC.md`, `CONTEXT.md`,
  `DATA_MODELS.md`, `SEGURIDAD.md`, `PROGRESS.md`, `STACK.md`, 31 migraciones de esquema numeradas y
  varios `fix_politicas_*.sql` sucesivos.
- Esos `fix_politicas_*.sql` repetidos son evidencia de **bugs recurrentes reales** sobre políticas RLS, que
  es precisamente la clase de problema que este sistema debe recordar para no repetir.
- Es el proyecto que la propia especificación usa como ejemplo (ventana de clientes, elementos del catalogo) y sus
  restricciones de ejemplo ("no eliminar política RLS") son literales de este repositorio.

### Consecuencias
- El sistema tendrá acceso de **solo lectura** al repositorio del proyecto piloto. Nunca escribe en él.
- La memoria inicial se extrae de `docs/` y del historial de commits, con validación humana antes de
  aceptarse como `FACT`.

---

## DEC-006 — Entorno de ejecución: Python 3.13 aislado

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Decidido por:** consecuencia directa de DEC-001

### Contexto
El equipo tiene únicamente **Python 3.14.4** instalado. `graphiti-core` 0.29.3 declara
`>=3.10,<4` pero su soporte real llega hasta **3.13**. `falkordblite` exige **3.12 o superior**.

### Decisión
Instalar **Python 3.13** y trabajar siempre dentro de un entorno virtual dedicado del proyecto.
No se toca ni se degrada la instalación 3.14 existente.

### Motivo
La intersección de requisitos (`>=3.12` por falkordblite, `<=3.13` por graphiti-core) deja 3.12 y 3.13
como únicas versiones válidas. 3.13 es la más nueva de las dos.

### Consecuencias
- Paso de instalación obligatorio antes de la Fase 1.
- La versión de Python queda fijada en el archivo de dependencias del proyecto.

---

## DEC-007 — Backend de grafo: Neo4j Community Server

- **Estado:** SUPERSEDED por DEC-008 el 2026-08-20
- **Fecha:** 2026-08-20
- **Reemplaza a:** DEC-001

> **Por qué cayó:** el usuario prefirió asumir el coste de instalar Docker para tener desde el inicio
> la misma infraestructura que usaría en producción, en lugar de un motor elegido por conveniencia
> local. Decisión de preferencia, no de viabilidad: Neo4j era técnicamente viable.

### Contexto
Tras descartarse FalkorDB Lite por incompatibilidad con Windows, el espacio de opciones quedó así en
este equipo concreto:

| Opción | Viabilidad |
|---|---|
| FalkorDB Lite embebido | **Imposible.** `redislite` no soporta win32 |
| Docker + FalkorDB | Exige instalar Docker Desktop y **WSL2, que no está instalado** (implica reinicio) |
| Kuzu embebido | Deprecado en `graphiti-core`, upstream sin mantenimiento |
| Neo4j Community Server | **Viable y nativo en Windows** |

Además se confirmó que el equipo ya tiene **Java 21.0.10 LTS** instalado, que es exactamente lo que
exigen las versiones actuales de Neo4j.

### Decisión
Se usa **Neo4j Community Server** en distribución ZIP, ejecutado localmente y con el heap y la caché
de página ajustados a la baja para limitar su consumo de memoria.

### Motivo
- **Es la única opción nativa de Windows que no exige cambios invasivos en el sistema.** Docker
  requeriría instalar WSL2 y reiniciar; el ZIP de Neo4j solo se descomprime en una carpeta.
- **Coste de instalación real: cero.** El motivo por el que se descartó Neo4j en DEC-001 fue su peso,
  pero Java 21 ya estaba presente, así que no añade dependencias de sistema.
- **Es el driver mejor soportado de `graphiti-core`.** El paquete `neo4j` viene como dependencia por
  defecto, no como extra opcional; es la ruta más probada del proyecto.
- **Recupera lo que se perdía con Lite:** Neo4j Browser permite inspeccionar el grafo visualmente
  durante el PoC, que es justo lo que hay que validar en la Fase 1.
- La distribución ZIP es más ligera y más scriptable que Neo4j Desktop, que es una aplicación Electron
  con gestión por interfaz gráfica.

### Consecuencias
- Consumo de RAM de 1–1,5 GB con la configuración ajustada. Es el precio aceptado y hay que vigilarlo
  cuando el modelo local esté cargado a la vez.
- Neo4j debe estar arrancado para indexar o consultar. No es un proceso empotrado.
- El riesgo de esta elección está acotado por **DEC-002**: la memoria vive en los `JSONL`, así que
  cambiar de motor más adelante es un `rebuild`, no una migración.

### Alternativas descartadas
- **Docker + FalkorDB:** más cercano a producción, pero exige WSL2 y reinicio del equipo. Se reevaluará
  si el proyecto se vuelve parte estable del flujo de trabajo.
- **Neo4j Desktop:** misma base de datos, pero añade una capa Electron y gestión por GUI que estorba
  para automatizar arranque y parada.
- **Kuzu:** deprecado.

---

## DEC-008 — Backend de grafo: Docker Desktop + FalkorDB

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario
- **Reemplaza a:** DEC-007

### Contexto
Descartado FalkorDB Lite por incompatibilidad con Windows (DEC-001) y propuesto Neo4j como única
opción nativa sin cambios invasivos (DEC-007), el usuario optó explícitamente por instalar Docker.

### Decisión
El motor de grafos es **FalkorDB ejecutándose en un contenedor Docker**, sobre Docker Desktop con
backend WSL2.

### Motivo
- La infraestructura del PoC pasa a ser **idéntica a la de un despliegue real**: mismo motor, misma
  versión, misma forma de arrancarlo. No hay que reelegir motor más adelante.
- El estado del motor queda en un volumen Docker y su arranque queda descrito en un
  `docker-compose.yml` versionable, que es en sí mismo documentación ejecutable.
- FalkorDB en contenedor es ligero; el coste de memoria real lo impone Docker Desktop y su WSL2, no
  la base de datos.
- Evita la JVM de Neo4j.

### Consecuencias
- **Requiere privilegios de administrador y reinicio del equipo.** La sesión de trabajo actual no está
  elevada, así que la instalación de WSL2 y Docker Desktop la ejecuta el usuario manualmente.
- Docker Desktop debe estar arrancado para indexar o consultar. Añade un proceso pesado permanente en
  un equipo de 16 GB; hay que vigilar la memoria cuando el modelo local esté cargado a la vez.
- Se recomienda limitar la memoria de WSL2 mediante un archivo `.wslconfig` para que no compita con
  Ollama.
- El trabajo que no depende del motor (esquema de memoria, extracción desdel proyecto piloto, benchmark de
  modelos locales) avanza en paralelo y no queda bloqueado por esta instalación.

### Verificado en el equipo
- `HypervisorPresent = True`: la virtualización está disponible, no hace falta tocar la BIOS.
- WSL2 no instalado; Docker no instalado; sesión sin elevación.

### Alternativas descartadas
- **Neo4j Community Server (DEC-007):** viable y sin instalación adicional al haber ya Java 21, pero
  el usuario prefirió la ruta equivalente a producción.

---

## DEC-009 — Esquema de la memoria: envoltura común con procedencia obligatoria

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20

### Contexto
DEC-002 fija los `JSONL` como fuente de verdad, lo que obliga a un esquema estable. La sección 15 de
la especificación exige además distinguir `FACT`, `INFERENCE`, `PROPOSAL`, `DECISION` y `RESOLVED`.

### Decisión
Todos los tipos de memoria comparten una **envoltura única** (`MemoryRecord` en `src/acm/models.py`)
con `id`, `type`, `project`, `title`, `provenance`, `source`, `created_at`, `summary`, `modules`,
`files`, `links`, `tags` y un `body` libre por tipo. Dos campos son obligatorios y no admiten valor
por defecto: **`provenance`** y **`source`**.

### Motivo
- Que `provenance` y `source` no tengan valor por defecto hace **imposible crear memoria sin declarar
  de dónde sale**. La disciplina queda impuesta por el tipo, no por la buena voluntad de quien escribe.
- Una envoltura común permite que el Context Builder trate todos los tipos con el mismo código.
- `links` con `rel` libre reproduce el grafo de la sección 6 sin cerrar el vocabulario de relaciones
  antes de saber cuáles hacen falta.

### Consecuencias
- Se define el conjunto `TRUSTED = {FACT, DECISION, RESOLVED}`. Lo que no está ahí viaja al contexto
  **marcado con su procedencia** o no viaja. Una `PROPOSAL` nunca se presenta como afirmación.
- `MemoryStore.check()` valida que todo enlace apunte a un id existente, evitando grafos rotos.

---

## DEC-010 — Métricas del benchmark de modelos locales

- **Estado:** ACEPTADA · el benchmark se ejecutó y de él salieron DEC-012 y DEC-013
- **Fecha:** 2026-08-20

### Contexto
DEC-003 exige medir antes de fijar el modelo local, pero medir sin criterio definido de antemano
invita a justificar la elección a posteriori.

### Decisión
El benchmark de la Fase 1 mide cuatro cosas sobre el mismo conjunto sembrado de 16 registros reales:

1. **JSON válido** — porcentaje de extracciones que parsean sin reparación. Es eliminatorio: un
   modelo por debajo del 90% no sirve como motor de ingesta.
2. **Cobertura de entidades** — cuántos de los módulos y archivos ya conocidos del registro recupera.
3. **Precisión de relaciones** — aristas correctas frente a aristas inventadas. Una relación falsa es
   peor que una ausente, porque contamina la memoria.
4. **Tiempo por registro** — segundos de reloj, con el modelo ya cargado.

### Consecuencias
- La Fase 1 no se declara superada sin la tabla de estas cuatro métricas para cada modelo probado.
- El conjunto sembrado sirve de referencia porque sus entidades y relaciones fueron extraídas y
  verificadas a mano contra commits y archivos SQL del repositorio.

### Primera medición (2026-08-20) — antes del benchmark completo

Prueba de arranque de cada modelo, con Docker levantado y WSL2 ocupando su límite de 4 GB:

| Modelo | Resultado | Tiempo |
|---|---|---|
| `qwen2.5:7b-instruct-q4_K_M` | **`llama runner process has terminated`** — no arranca | — |
| `qwen2.5:3b-instruct-q4_K_M` | responde correctamente | 6 s en frío, 0,2 s en caliente |
| `llama3.2:3b` | responde correctamente | 7 s en frío |
| `nomic-embed-text` | 768 dimensiones | 2,2 s |

**Lectura:** con 15,9 GB totales, `vmmemWSL` reteniendo 3,9 GB y solo **4,4 GB libres**, un modelo de
4,7 GB no tiene sitio ni en VRAM ni en RAM. El 7B queda **eliminado mientras coexistan Docker y Ollama
en esta máquina**. No es un fallo del modelo: es el presupuesto de memoria de DEC-011 haciendo su
trabajo. Refuerza la consideración de Linux anotada en DEC-011, donde el coste de WSL2 desaparecería.

### Benchmark completo (2026-08-20)

64 extracciones: 4 modelos x los 16 registros de referencia, sin decodificación restringida.

| Modelo | JSON válido | Tipo correcto | Cobertura módulos | Precisión relaciones | Inventadas | Mediana |
|---|---|---|---|---|---|---|
| `llama3.2:3b` | **100 %** | 81 % | **55 %** | 13 % | 14 | 2,7 s |
| `qwen2.5:3b-instruct-q4_K_M` | **100 %** | 81 % | 42 % | 11 % | 16 | 2,6 s |
| `phi3:mini` | 88 % | 79 % | 48 % | 7 % | 14 | 4,3 s |
| `qwen3.5:0.8b` | **0 %** | — | — | — | — | 16,2 s |

### Pendiente
Ninguno. Las decisiones que se derivan de esta medición están en DEC-012 y DEC-013.

---

## DEC-011 — Presupuesto de RAM: WSL2 limitado a 4 GB

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario

### Contexto
DEC-008 introdujo Docker Desktop, que por defecto permite a WSL2 reservar hasta la mitad de la RAM
del equipo. En 16 GB eso son 8 GB que competirían con Ollama. El objetivo declarado del usuario es
**usar este entorno y a la vez seguir programando y probando en la misma laptop**, no dedicarla al
sistema.

### Decisión
Se fija un `%USERPROFILE%\.wslconfig` con `memory=4GB`, `processors=4` y `swap=2GB`. El archivo se creó
antes del primer arranque de Docker Desktop para que el límite aplicara desde el inicio.

### Motivo
- 4 GB bastan para FalkorDB, que es ligero; el peso real de WSL2 es el propio subsistema, no la BD.
- Dejar 4 de los 12 hilos a WSL preserva capacidad de CPU para la inferencia local, que en este equipo
  no cabe entera en VRAM y depende de la CPU.
- Es un límite, no una reserva: WSL2 no ocupa 4 GB si no los necesita.

### Consecuencias
- Los cambios en `.wslconfig` exigen `wsl --shutdown` y volver a arrancar Docker Desktop.
- Si FalkorDB llega a necesitar más memoria al crecer el grafo, hay que subir este techo de forma
  explícita y dejarlo anotado aquí.

### Consideración registrada, sin decidir
El usuario planteó **migrar el equipo a Linux como último recurso** si la RAM resulta insuficiente.
No es una decisión tomada y no condiciona el diseño actual, pero se anota porque cambiaría dos cosas:
desaparecería el coste de WSL2 (Docker sería nativo) y volvería a estar disponible **FalkorDB Lite
embebido**, que fue descartado en DEC-001 solo por ser incompatible con Windows. Si esa migración
llega a plantearse en serio, DEC-001 debe reabrirse.

---

## DEC-012 — Modelo local del Context Manager: `llama3.2:3b`

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Cumple:** el requisito de medición previa de DEC-003

### Contexto
Medición de DEC-010 sobre 64 extracciones reales.

### Decisión
El modelo local por defecto es **`llama3.2:3b`**. `qwen2.5:3b-instruct-q4_K_M` queda como suplente.

### Motivo
- Empata en lo eliminatorio: **100 % de JSON válido**, igual que qwen2.5:3b.
- Gana en lo que los separa: **55 % de cobertura de módulos frente a 42 %**, con el mismo coste de
  tiempo (2,7 s frente a 2,6 s de mediana).
- Inventa algo menos que qwen2.5:3b (14 relaciones falsas frente a 16), aunque ninguno de los dos es
  aceptable en esa métrica: ver DEC-013.

### Alternativas descartadas
- **`phi3:mini`:** falla el criterio eliminatorio con 88 % de JSON válido, y además es 1,6 veces más
  lento. Un modelo que rompe el formato una de cada ocho veces obliga a lógica de reparación en el
  camino crítico.
- **`qwen3.5:0.8b`: eliminado sin discusión.** 0 % de JSON válido en 16 de 16 intentos y una mediana
  de 16,2 s, seis veces más lento que modelos que sí funcionan. Es el resultado más limpio del
  benchmark: por debajo de cierto tamaño el modelo no sirve para este rol a ningún precio.
- **7B:** no arranca en este equipo. Ver la primera medición de DEC-010.

---

## DEC-013 — Las relaciones del grafo no se infieren con el modelo local

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20

### Contexto
La métrica 3 de DEC-010 dice literalmente que una relación falsa es peor que una ausente, porque
contamina la memoria. La medición fue demoledora:

| Modelo | Precisión de relaciones | Relaciones inventadas |
|---|---|---|
| `llama3.2:3b` | 13 % | 14 en 16 registros |
| `qwen2.5:3b` | 11 % | 16 en 16 registros |
| `phi3:mini` | 7 % | 14 en 16 registros |

Aproximadamente **una relación falsa por registro procesado**. Inspeccionando las respuestas aparecen
dos causas distintas: relaciones genuinamente fabricadas, y **deriva de esquema** — el modelo ignora
el formato `{rel, target}` que se le indica y se inventa los nombres de campo, por ejemplo
`relation_type` y `dependent_module`.

### Decisión
El modelo local **no propone aristas del grafo**. Las relaciones proceden, por este orden:

1. **Fuentes deterministas** — coincidencia de archivos y módulos entre registros, cercanía en el
   historial de git, referencias explícitas por identificador en el texto.
2. **Declaración del usuario**, que entra directamente como `FACT`.
3. Si en algún momento se permite que el modelo sugiera relaciones, entran **obligatoriamente como
   `PROPOSAL`** y jamás se indexan hasta que alguien las confirme.

El modelo local se queda con lo que sí hace bien: clasificar el tipo de registro y extraer módulos y
archivos afectados.

### Motivo
Con 13 % de precisión, aceptar las relaciones del modelo significaría que **siete de cada ocho aristas
del grafo serían falsas**. Eso no es una memoria degradada: es una memoria activamente engañosa, que
haría al sistema peor que no tener nada. Y el daño se agrava con el tiempo, porque las aristas falsas
se recuperarían como contexto para tareas futuras.

### Consecuencias
- El Context Builder debe apoyarse en solapamiento de archivos y módulos para relacionar registros, no
  en inferencia semántica del modelo local.
- La calidad del grafo pasa a depender de la calidad de los campos `files` y `modules`, donde el modelo
  sí alcanza 55 %. Refuerza la importancia de la métrica 2.
- En producción hay que activar **decodificación restringida** (`json_schema`), que el benchmark evitó
  a propósito para medir la fiabilidad real del modelo. Eso elimina la deriva de esquema, pero **no
  arregla las relaciones fabricadas**: un esquema válido con contenido falso sigue siendo falso.

---

## DEC-014 — `decision` y `constraint` se separan por función, no por contenido

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario

### Contexto
Los cuatro modelos fallaron en **exactamente los mismos tres registros**: ADR-001, ADR-002 y ADR-003.
Todos los clasificaron como `constraint` en lugar de `decision`. Un fallo idéntico en modelos de
familias distintas no es un fallo de los modelos.

Y tienen parte de razón. "Toda operación privilegiada pasa por el backend propio" es a la vez una
decisión que alguien tomó y una restricción que nadie debe violar. La diferencia no está en el
contenido de la frase, sino en **qué se hace con ella**: una decisión explica el porqué de lo que ya
existe; una restricción prohíbe algo en el futuro.

### Decisión
No se fuerza a que un hecho pertenezca a una sola categoría. Un mismo hecho **produce ambas cosas**,
enlazadas y con roles distintos:

```
DECISION  — qué se decidió y por qué
    │
    │ deriva_en
    ▼
CONSTRAINT — qué no debe violar ninguna implementación futura
```

Ejemplo real del proyecto piloto:

```
DECISION (ADR-001):
  Las operaciones privilegiadas pasan por el backend propio.
  Motivo: evitar exponer credenciales y centralizar autorización.
        ↓ deriva_en
CONSTRAINT (CONSTRAINT-001):
  El cliente no puede ejecutar directamente operaciones privilegiadas.
```

La relación es bidireccional en el vocabulario: `deriva_en` de la decisión hacia la restricción,
`deriva_de` en sentido inverso.

### Motivo
Los dos tipos responden a preguntas distintas y se usan en momentos distintos de la recuperación:

| Tipo | Pregunta que responde | Papel en el contexto |
|---|---|---|
| `decision` | ¿por qué el sistema está así? | precedente histórico |
| `constraint` | ¿qué no debo romper? | guardarraíl |

Esa diferencia de papel ya está implementada en DEC-015: las restricciones entran como guardarraíl del
módulo afectado aunque no coincidan léxicamente, mientras que las decisiones solo entran por
evidencia. Mantener ambas entidades no es redundancia: es lo que permite ese tratamiento distinto.

### Consecuencias
- La clasificación automática entre estos dos tipos deja de ser un problema a resolver: si un hecho es
  ambos, se registran ambos. El fallo unánime de los cuatro modelos del benchmark deja de importar.
- Al sembrar memoria hay que preguntarse por separado *qué se decidió* y *qué queda prohibido*.

---

## DEC-015 — El modelo local entra en la recuperación por dos puertas asimétricas

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Implementa:** DEC-013

### Contexto
Al conectar el analizador de intención con la recuperación por solapamiento, medimos la consulta del
enunciado del proyecto con y sin modelo local:

| Variante | Registros | Reducción | Tiempo | Calidad |
|---|---|---|---|---|
| Solo solapamiento léxico | 4 | 47 % | 0,0 s | los 4 precedentes exactos |
| Con módulos del modelo | 8 | 24 % | 5,3 s | 4 correctos + 4 de relleno |

El modelo devolvía `modules: ["web", "mobile"]`. Son correctos pero **tan gruesos que admitían todo lo
etiquetado así**, incluidas decisiones sobre `clave privilegiada` que no tienen nada que ver con cambiar cómo
se muestran unos elementos del catalogo. Sus `keywords` en cambio (`elementos del catalogo`, `ventana_de_clientes`) eran
precisas y útiles.

### Decisión
Las dos salidas del modelo se tratan de forma distinta, a propósito:

- **`keywords`** → términos de búsqueda normales, al mismo peso que los de la petición. Son léxicos y
  específicos.
- **`modules`** → **no admiten registros**, solo reordenan (factor 1,25 sobre lo ya encontrado). La
  única excepción son las **restricciones**: si la tarea toca un módulo, sus restricciones se muestran
  siempre, porque para eso existen. Entran marcadas como guardarraíl, no como precedente.

### Motivo
Es DEC-013 llevada un paso más allá. Allí se decidió que el modelo no propone aristas; aquí se decide
que tampoco decide pertenencia. Su papel es **afinar el orden y aportar vocabulario**, nunca abrir la
puerta del contexto. Lo que entra, entra por evidencia.

### Consecuencias y ajustes derivados
Tres correcciones adicionales salieron de probar esto:

1. **Umbral mínimo de relevancia** (`MIN_SCORE`). Una sola palabra coincidiendo en un resumen es ruido:
   así entraba ADR-001 en una consulta sobre paginación porque el usuario escribió *"ten en cuenta"* y
   el registro hablaba de *"activar cuentas"*.
2. **Nombre de archivo y carpeta pesan distinto.** `apiClient` identifica un archivo; `propietario` en
   `screens/propietario/...` solo dice dónde vive. Tratarlos igual hacía que cualquier consulta que
   mencionara a un propietario arrastrara archivos sin relación.
3. **Solo las coincidencias directas siembran la expansión.** Una restricción admitida como
   guardarraíl no es prueba de que el tema sea relevante; cuando sembraba, arrastraba a sus vecinos por
   los enlaces curados y el contexto se llenaba de decisiones ajenas a la tarea.

### Comportamiento cuando no hay nada
Si ninguna coincidencia directa supera el umbral, el contexto lo dice explícitamente: *"sin precedentes
registrados"*. Presentar reglas generales del área como si fueran experiencia acumulada sobre el
problema sería exactamente la contaminación que DEC-013 intenta evitar. Verificado con una consulta
sobre facturación con Stripe, tema que este proyecto no tiene: el sistema no inventa precedentes.

---

## DEC-016 — La métrica principal de Fase 1 es la precisión de recuperación, no la reducción de contexto

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario, que amplió la propuesta original

### Contexto
La sección 20 de la especificación dice que el éxito se mide por reducción de contexto. Medido hoy:

| Consulta | Registros enviados | Reducción |
|---|---|---|
| Política DELETE en colecciones asignadas | 4 de 16 | 60 % |
| Ventana de clientes, dos elementos del catalogo | 7 de 16 | 26 % |

### Problema
Con 16 registros el denominador es minúsculo, y las restricciones —que son verbosas y se incluyen casi
siempre— dominan el resultado. Un 26 % no significa que el sistema filtre mal: significa que **la
memoria completa todavía cabe en un prompt**, y por tanto no hay nada que reducir.

### Decisión
El porcentaje de reducción **deja de ser el indicador principal** hasta disponer de una memoria del
orden de **100 registros o más**. No se abandona la métrica: se aparca porque hoy no mide nada.

En su lugar se miden cuatro cosas:

| Métrica | Qué responde |
|---|---|
| `Precision@K` | de lo que envié, ¿cuánto era realmente aplicable? |
| `Recall@K` | de lo que debía encontrar, ¿cuánto encontré? |
| `MRR` | ¿el precedente más importante sale arriba o enterrado? |
| **`False Precedent Rate`** | ¿cuántas veces presenté experiencia que no existe? |

### False Precedent Rate

```
False Precedent Rate =
   consultas donde se presentó experiencia irrelevante
   ───────────────────────────────────────────────────
                 total de consultas
```

Es la métrica propia de este proyecto y mide exactamente el fallo detectado con la consulta sobre
facturación con Stripe, un tema que el proyecto piloto no tiene.

**Es correcto** responder:

> Sin precedentes registrados sobre Stripe. Las siguientes restricciones pertenecen al área afectada,
> pero no constituyen experiencia previa sobre Stripe.

**Es contaminación semántica** responder:

> Estos registros son relevantes para tu problema de Stripe.

### Criterio explícito

```
DOMINIO DESCONOCIDO / SIN PRECEDENTE
        ↓
No fabricar precedente
        ↓
Separar claramente:
    ├── experiencia histórica
    └── guardarraíles generales
```

### Motivo
Con 16 registros el denominador de la reducción es minúsculo y las restricciones —verbosas y
presentes casi siempre por diseño— lo distorsionan. Un 26 % no indica mal filtrado: indica que la
memoria completa todavía cabe en un prompt, así que no hay nada que reducir. Medir lo que no
discrimina invita a optimizar en la dirección equivocada.

### Consecuencias
- Hace falta un **conjunto de consultas con respuesta esperada** para poder medir. Sin verdad de
  referencia no hay Precision ni Recall.
- Hace falta **ampliar la memoria sembrada** desde el historial real del proyecto piloto hasta que aparezcan
  los problemas de escala, ruido y ranking. Con 16 registros no existen.
- La reducción de contexto se retomará como indicador cuando el corpus lo justifique.

### Criterio de cierre de la Fase 1
El sistema debe demostrar tres comportamientos:

1. Recupera los precedentes correctos.
2. No introduce precedentes falsos.
3. Cuando no sabe, lo dice explícitamente.

---

## DEC-017 — Jerarquía de señal en la coincidencia de rutas

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario
- **Refina:** DEC-015

### Contexto
DEC-015 introdujo la distinción entre el nombre del archivo y su carpeta, con dos niveles. El usuario
señaló que la señal tiene en realidad cuatro grados de fuerza.

### Decisión

```
coincidencia exacta de ruta   >   token del nombre de archivo
                              >   directorio inmediato
                              >   directorio ancestro
```

Coincidir con `web/lib/apiClient.ts` completo es una señal mucho más fuerte que coincidir con
`apiClient`, que a su vez es más fuerte que coincidir con `lib`, que a su vez es más fuerte que
coincidir con `web`.

### Motivo
Cuanto más arriba está un segmento en el árbol, a más archivos pertenece y menos discrimina. Un
ancestro como `src` o `web` es casi una etiqueta de proyecto; el nombre del archivo identifica una
unidad concreta de código.

---

## DEC-018 — Un Context Manager, múltiples proyectos aislados

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario

### Contexto
Hasta DEC-017 el sistema trataba al proyecto piloto como si fuera *el* proyecto. El usuario señaló el
riesgo: si se sigue así, añadir un proyecto nuevo obligaría a levantar otra instancia entera del
Context Manager en lugar de ser una operación de inicialización.

### Decisión
el proyecto piloto es **un inquilino del sistema, no una dependencia del sistema**.

```
                 CONTEXT MANAGER
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
    el proyecto piloto    BackupCenter    Proyecto nuevo
         │              │              │
       memoria        memoria        memoria
         └──────────────┼──────────────┘
                        ▼
                    FalkorDB
```

Cuatro consecuencias concretas:

**1. La identidad de un registro es `project_id + id`.** Cada proyecto puede tener su propio `BUG-001`
sin colisionar. `MemoryRecord.uid` devuelve `piloto/BUG-001`.

**2. El aislamiento es físico, no un filtro.** La memoria vive en `memory/<project_id>/`, y
`MemoryStore` pertenece siempre a un proyecto. Una consulta sobre BackupCenter **no puede** alcanzar un
bug del proyecto piloto porque ni siquiera lee ese directorio. Además el almacén rechaza escribir un
registro de otro proyecto. Un filtro se puede olvidar aplicar; un directorio distinto, no.

**3. `.context/project.json` identifica, no almacena.** Dentro del repositorio gestionado se escribe
solo identidad y configuración. La memoria real vive en el espacio del Context Manager y, indexada, en
el grafo:

```json
{
  "project_id": "piloto",
  "repository": "C:/.../el proyecto piloto",
  "context_manager_version": "1.0",
  "memory_namespace": "piloto"
}
```

**4. `init` convierte cualquier repositorio en proyecto gestionado**, registrando únicamente evidencia
observada: qué archivos existen (`package.json`, `*.csproj`, `docker-compose.yml`), qué directorios
hay, si hay git y cuál es el remoto. Nada de esto lo infiere el modelo, en cumplimiento de DEC-013.

### Verificado
```
python context_manager.py init <ruta>
python ask.py "..." --project <id>
```
Se inicializaron dos repositorios reales. La misma consulta devuelve los precedentes del proyecto piloto en
un caso y «no hay memoria relevante» en el otro. El almacén rechazó un registro de proyecto ajeno.

### Consecuencias
- La frecuencia documental (IDF) se calcula **por proyecto**: lo que es común en un proyecto puede ser
  raro en otro.
- Las aristas derivadas nunca cruzan proyectos.
- `ask.py` deduce el proyecto activo del `.context/project.json` del directorio actual, o se indica con
  `--project`.

---

## DEC-019 — Línea base medida de la recuperación

- **Estado:** ACEPTADA como referencia
- **Fecha:** 2026-08-20
- **Cumple:** el criterio de medición de DEC-016

### Corpus
111 registros del proyecto piloto: 16 curados a mano y 95 extraídos del historial de git de forma
determinista. De los extraídos, 63 quedaron marcados `INFERENCE` por no traer cuerpo de commit — un
asunto suelto dice qué se tocó, no por qué.

### Resultados sobre 12 consultas anotadas

| Métrica | Valor |
|---|---|
| `Precision@8` | 28,9 % |
| `Recall@8` | **94,4 %** |
| `MRR` | **0,764** |
| `False Precedent Rate` | **8,3 %** (1 de 12) |

### Lectura honesta
- **Recall y MRR son buenos.** El precedente correcto casi siempre aparece, y casi siempre arriba.
- **`Precision@8` está topada por construcción.** Si una consulta tiene 3 precedentes correctos, la
  precisión máxima a K=8 es del 38 %. El número mide sobre todo el tamaño de K, no la calidad.
- **El FPR restante es un caso de polisemia del español**, no un fallo de diseño: el término `real`
  hace que *"chat en tiempo real"* case con *"solución real"* y con *"IP real"*. Añadir `real` a las
  palabras vacías arreglaría la métrica ajustando al caso de prueba, que es el sobreajuste que este
  proyecto intenta evitar.

### Lo que la medición dejó al descubierto

Dos fallos con la misma raíz, y no se arreglan con más ajuste de pesos:

| Consulta | Registro | Por qué falla |
|---|---|---|
| «las colecciones no se guardan sin **conexión**» | BUG-122, etiquetado `offline` | sinónimo no cubierto |
| «chat en tiempo **real**» | SOL-002, etiqueta `solucion-real` | polisemia |

**El emparejamiento léxico determinista tiene un techo semántico.** Es exactamente el punto donde
entran los embeddings, que ya están instalados (`nomic-embed-text`, 768 dimensiones) y sin usar para
recuperación. Bajo la disciplina de DEC-013 y DEC-015, los embeddings entrarían por la puerta de
`keywords`: **pueden descubrir candidatos, no afirmar relaciones**.

### Correcciones aplicadas durante la medición
1. Frecuencia documental en las aristas: `docs/PROGRESS.md` lo toca casi cada commit, así que
   compartirlo no es evidencia de nada. Una sola semilla llegaba a arrastrar siete registros ajenos.
2. Cada término de la consulta puntúa **una vez**, al peso del campo más fuerte. Contar `elementos del catalogo`
   tres veces por estar en etiquetas, título y resumen premiaba la redundancia y producía empates
   masivos. Este cambio solo subió el MRR de 0,53 a 0,74.
3. Etiquetas atómicas: `solucion-real` no contiene `real`. Trocearlas creaba tokens fantasma.
4. Los enlaces curados quedan exentos del tope de vecinos: son afirmaciones del equipo, no indicios.
5. Un solo término en común no basta para reclamar precedente, salvo que sea el tema declarado del
   registro (etiqueta o módulo). Que un checklist legal mencione «facturación» no lo convierte en
   experiencia previa sobre cobrar con Stripe.

---

## DEC-020 — La recuperación semántica entra como descubrimiento, no como evidencia

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario

### Contexto
DEC-019 dejó al descubierto el techo semántico del emparejamiento léxico: *«sin conexión»* no encuentra
`offline`, y *«tiempo real»* casa con `solucion-real`. El primero es un problema semántico legítimo; el
segundo demuestra por qué no hay que seguir parcheando pesos ni palabras vacías.

### Decisión
Los embeddings entran por la misma puerta que las palabras clave del modelo local. Cinco reglas:

1. Pueden **añadir candidatos**.
2. Una coincidencia semántica **no crea una arista** del grafo.
3. Un resultado vectorial **no se presenta automáticamente como precedente**: se marca como hallazgo
   semántico sin evidencia léxica.
4. Los candidatos semánticos pasan por la **misma clasificación**: precedente, guardarraíl o
   irrelevante.
5. Si nada supera el umbral final, se sigue respondiendo **`SIN PRECEDENTES REGISTRADOS`**.

La regla general que unifica DEC-015 y esta: **el modelo puede aumentar prioridad; no puede crear
candidatos canónicos.**

### Fusión por posición, no por puntuación
Se usa **RRF (Reciprocal Rank Fusion)**. Un score léxico y una similitud coseno no viven en la misma
escala; ponderarlos entre sí exigiría inventar un factor de conversión arbitrario. RRF solo necesita
saber quién va antes.

### El problema que hubo que resolver para cumplir la regla 5
Los embeddings **no tienen señal natural de "aquí no hay nada"**. Medido sobre las 40 consultas:

| Categoría | Similitud máxima | z-score |
|---|---|---|
| Consultas legítimas (sinónimos) | 0,581 – 0,742 | 1,57 – 3,61 |
| Dominios inexistentes | 0,588 – 0,667 | 1,45 – 2,21 |

**Las distribuciones se solapan.** Una consulta sobre Stripe alcanza 0,653, más que varias consultas
legítimas. Ningún umbral absoluto las separa. Se admite un candidato solo si **destaca del fondo del
corpus**: `similitud >= 0,68` **o** `z-score >= 2,4`. Ambos valores están calibrados sobre este banco;
son un ajuste a datos observados, no constantes universales.

### Congelación del baseline
`retrieval.py` queda **congelado**. La vía híbrida vive en `hybrid.py` y **compone** en lugar de
modificar: cambiar de estrategia es cambiar de función, no editar la anterior, de modo que la
comparación entre las tres siempre es honesta.

---

## DEC-021 — La recuperación híbrida es la estrategia oficial de descubrimiento

- **Estado:** ACEPTADA · formalizada por el usuario
- **Fecha:** 2026-08-20

> **Enunciado oficial.** La recuperación híbrida léxico-semántica es la estrategia oficial de
> *discovery*. RRF fusiona ambas fuentes; la vía semántica puede descubrir candidatos pero **nunca
> establece relaciones ni convierte similitud en precedente**. Los umbrales actuales son parámetros
> calibrados del corpus y deben recalibrarse al cambiar significativamente el corpus.
- **Criterio de aceptación fijado por el usuario:** *«si el híbrido mejora los casos de sinónimos sin
  aumentar significativamente los falsos precedentes, hay evidencia para aceptar la capa semántica»*

### Medición
Banco ampliado a **40 consultas** clasificadas por tipo de dificultad, sobre 111 registros, K = 8.

| Métrica | léxico | semántico | **híbrido** |
|---|---|---|---|
| Precision@3 | 39,7 % | 38,2 % | **40,2 %** |
| Precision@5 | 31,4 % | 33,0 % | 31,3 % |
| Precision@8 | 26,4 % | **31,6 %** | 27,9 % |
| Recall@5 | 57,1 % | 44,1 % | **59,3 %** |
| Recall@8 | 60,8 % | 46,6 % | **65,9 %** |
| MRR | 0,585 | 0,577 | **0,669** |
| nDCG@8 | 0,565 | 0,462 | **0,616** |
| Falsos precedentes | 1/6 | **0/6** | 1/6 |

### Recall@8 por categoría — donde está la respuesta

| Categoría | léxico | semántico | híbrido |
|---|---|---|---|
| EXACT_MATCH | **0,917** | 0,637 | 0,881 |
| **SYNONYM** | 0,150 | 0,300 | **0,300** |
| **POLYSEMY** | 0,400 | 0,200 | **0,600** |
| CROSS_MODULE | **0,867** | 0,583 | 0,817 |

Y en nDCG@8, que mide además el orden:

| Categoría | léxico | híbrido |
|---|---|---|
| SYNONYM | 0,078 | **0,281** (×3,6) |
| POLYSEMY | 0,400 | **0,526** |
| EXACT_MATCH | 0,894 | 0,832 |
| CROSS_MODULE | 0,783 | 0,771 |

### Decisión
Se adopta el **híbrido** como recuperación por defecto. `ask.py --lexico` conserva el baseline.

### Motivo
**El criterio de aceptación se cumple exactamente.** Los sinónimos duplican su recall y multiplican por
3,6 su nDCG, y los falsos precedentes **no aumentan**: 1 de 6 en ambos, y el que queda proviene de la
vía léxica, no de la semántica. La vía semántica sola tiene 0 falsos precedentes.

El desglose por categoría fue decisivo: la media global apenas se mueve, pero esconde que la mejora se
concentra justo donde se predijo que haría falta. Sin esa clasificación, el híbrido habría parecido un
cambio marginal.

### Coste y consecuencias
- Indexar 111 registros: **8,4 s**. Solo se recalcula lo que cambia.
- El índice vectorial vive en `memory/<project_id>/.vectors.json` y es **reconstruible**, igual que el
  grafo. La fuente de verdad sigue siendo el JSONL (DEC-002).
- **EXACT_MATCH y CROSS_MODULE pierden algo** (0,917 → 0,881 y 0,867 → 0,817): la vía semántica diluye
  ligeramente los casos donde la léxica ya acertaba. Es el precio, y es menor que la ganancia.
- **Los sinónimos siguen en 0,300 de recall.** Los embeddings ayudan, no resuelven. Queda margen.

### Aviso sobre la comparación con DEC-019
La línea base pasó de `Recall@8 = 94,4 %` a `60,8 %`. **No es una regresión**: el banco pasó de 12
consultas a 40, deliberadamente más difíciles, con categorías de sinónimos y polisemia que antes no
existían. Los dos números no son comparables entre sí, solo dentro de su propio banco.

---

## DEC-022 — Se cierra la etapa experimental de recuperación

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario

### Decisión
No se optimiza más la recuperación. En concreto, **no se intenta llevar `SYNONYM` de 0,300 a 0,500
ajustando pesos**. `retrieval.py` y `hybrid.py` quedan congelados salvo por recalibración de umbrales
cuando cambie el corpus.

### Motivo
Ya hay evidencia de que el problema restante es semántico, no de ranking. Seguir ajustando contra 40
consultas sería exactamente lo que este proyecto detectó y evitó antes: **optimizar contra el banco de
pruebas en vez de contra el problema**.

### Cambio de prioridad
El trabajo pasa de *cómo recuerda* a **cómo aprende**. Hoy toda la memoria entró por siembra manual o
por extracción del historial de git. El sistema todavía no aprende de observar el trabajo en curso, que
es la sección 14 de la especificación original y la mitad que falta del bucle.

---

## DEC-023 — Escalera de confianza para la observación post-tarea

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario

### Contexto
El riesgo del ciclo post-tarea es repetir el error que DEC-013 evitó en las relaciones: convertir en
memoria confiable lo que solo es una suposición. Un commit que dice `fix cosas` no debe convertirse
automáticamente en `SOLUTION: se solucionó X`, porque ese commit no explica nada.

### Decisión
La observación tiene cuatro niveles, y **solo el último entra en la memoria canónica**:

```
OBSERVED     evidencia bruta del repositorio
    ↓        3 archivos modificados, 2 módulos tocados, commit abc123
EXTRACTED    estructura derivada de esa evidencia por regla fija
    ↓        modules=[mobile/useExercises], relacionado con BUG-002 por archivo compartido
PROPOSED     interpretación del modelo local
    ↓        "parece relacionado con paginación"
VERIFIED     confirmado por una persona
             "sí, era el bug de paginación"
```

### Regla
La memoria canónica vive en `memory/<project_id>/`. Todo lo que produce el observador aterriza antes
en `memory/<project_id>/pending/`, y **solo pasa a canónica cuando alguien lo confirma**. La separación
es física, igual que el aislamiento entre proyectos de DEC-018: un registro pendiente no puede
contaminar una recuperación porque no está en el directorio que se lee.

### Motivo
Es la misma filosofía que ya funcionó en DEC-013 y DEC-015, aplicada al otro extremo del ciclo:
**la IA puede proponer; la evidencia determina qué se convierte en memoria confiable.**

### Consecuencias
- `OBSERVED` y `EXTRACTED` son deterministas y verificables contra el repositorio.
- `PROPOSED` lleva siempre marca del modelo que lo generó.
- Las relaciones con memoria existente se derivan por solapamiento de archivos, no por inferencia
  semántica: DEC-013 sigue vigente también aquí.
- Nada se promociona solo por el paso del tiempo ni por acumulación de indicios.

---

## DEC-024 — El ciclo completo, verificado de extremo a extremo

- **Estado:** ACEPTADA como referencia
- **Fecha:** 2026-08-20
- **Implementa:** DEC-023 y la sección 14 de la especificación original

### El bucle
```
memoria → tarea → recuperación → Claude/GPT → cambio real
                                                    │
                                                    ▼
                                              OBSERVACIÓN
                                                    │
                                              VERIFICACIÓN
                                                    │
                                                    ▼
                                            memoria canónica
                                                    │
                                                    └──→ siguiente tarea
```

### Verificado sobre dos commits reales del proyecto piloto

**Commit con explicación** (`d4e5f6a`, el de la paginación):

```
[OBSERVED ] 6 archivos, +57/-14
[EXTRACTED] modulos: mobile/useExercises, mobile/apiClient, web/apiClient...
            relacionado con BUG-002 (comparte useExercises.ts),
                            SOL-002 (comparte apiClient.ts)
[PROPOSED ] change: "Mejora en la paginacion de la catalogo de elementos"
[PENDIENTE] PEND-001, provenance PROPOSAL
```

Las relaciones con `BUG-002` y `SOL-002` **no las infirió el modelo**: salen de archivos compartidos con
la memoria existente. DEC-013 sigue vigente en este extremo del ciclo.

**Commit sin explicación** (`c9d0e1f`, *«fix agrupacion»*):

```
[PROPOSED ] "Agrupacion de codigo"  —  provenance INFERENCE, no PROPOSAL
   Aviso: el commit no explica nada, la propuesta se basa solo en
   nombres de archivo. Revisala con cuidado antes de verificar.
```

El sistema **degradó la procedencia por sí solo** al detectar que el mensaje no explicaba nada. Es
exactamente el caso que motivó DEC-023: un `fix cosas` no puede convertirse en `SOLUTION: se solucionó X`.

**Cierre del ciclo:** `PEND-001` verificado → `CHG-141` en memoria canónica (`VERIFIED` / `FACT`), con
trazabilidad completa (`desde: PEND-001`, `propuesto_por: llama3.2:3b`). `PEND-002` descartado.
Inmediatamente después, `CHG-141` aparece en segunda posición al consultar por la paginación de la
biblioteca. **El sistema aprendió algo y lo usó.**

### Hallazgo: la autoconfianza del modelo no sirve como señal

En el commit sin explicación, el modelo declaró **«confianza alta»** mientras su propio resumen admitía
que *«no se proporciona más información»*. Se contradijo a sí mismo en la misma respuesta.

Por eso el campo `confianza_declarada` se **guarda pero no se usa** para decidir promociones. La
promoción depende de dos cosas verificables —si el mensaje del commit explica algo, y si una persona lo
confirma— nunca de lo seguro que diga estar el modelo.

### Aislamiento verificado
Los registros pendientes viven en `memory/<project_id>/pending/` y **no aparecen en ninguna
recuperación**: comprobado que la memoria canónica no ve ningún `PEND-`. La separación es física, igual
que entre proyectos (DEC-018).

### Lo que aún no hace
- No observa automáticamente: hay que ejecutar `learn.py observe`. No hay disparador por hook de git.
- No lee la respuesta de Claude/GPT, solo el cambio en el repositorio. La justificación que dio la IA
  de pago se pierde, y suele ser la mejor explicación disponible.
- La verificación es un comando, no una conversación. Aceptar o rechazar entero, sin poder corregir el
  título o el resumen propuestos.

---

## DEC-025 — La justificación de la tarea es evidencia de primera clase

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario

### Decisión
El Context Manager acepta opcionalmente la explicación proporcionada por una IA externa, el
desarrollador, un pull request o una herramienta, junto al diff y los metadatos de git. Esa información
se incorpora como **evidencia del evento** y puede mejorar la propuesta `PROPOSED`, pero **nunca puede
promocionar una memoria a `VERIFIED` por sí sola**. La procedencia de cada fragmento se conserva
individualmente.

### Modelo general, no un parche
No se implementó como una bandera `--rationale` aislada, sino como un **evento de tarea con
evidencias**, para no rediseñar el esquema al añadir fuentes nuevas:

```
                    TASK EVENT
                        │
       ┌────────────────┼────────────────┐
       ▼                ▼                ▼
   Git diff       Commit message      Rationale
   (git)             (git)         (external_llm)
       └────────────────┼────────────────┘
                        ▼
                    OBSERVED → EXTRACTED → PROPOSED → VERIFIED
```

Cada fragmento lleva `kind`, `origin`, `provider`, `model`, `content` y `meta` propios. Añadir salida
de terminal, resultados de tests, descripción de PR o issue es **añadir una fila a una tabla**, no
tocar el modelo. Ya están declarados los tipos `terminal`, `test_results`, `pull_request`, `issue` y
`user_note`.

### Evidencia separada de inferencia
La distinción es explícita en el almacenamiento y en la interfaz:

```
EVIDENCE                          INFERENCE
├── git_commit                    ├── tipo
├── git_diff                      ├── titulo
├── rationale (external_llm)      ├── resumen
├── test_results                  └── confianza_declarada
└── user_note
```

Que el modelo diga *«esto corresponde a BUG-002»* es inferencia. Que ambos toquen
`useExercises.ts` es evidencia. **Solo lo segundo genera relación**, como exige DEC-013.

### Qué decide la procedencia
`has_explanation` es cierto cuando **alguna** evidencia explica de verdad el trabajo, venga de donde
venga. Una justificación de la IA externa cuenta igual que un mensaje de commit detallado.

- Con explicación → `PROPOSAL`
- Sin explicación → `INFERENCE`, con aviso explícito al revisar

### Medido sobre el mismo commit
`c9d0e1f`, cuyo mensaje entero es *«fix agrupacion»*:

| | sin justificación | con justificación de Claude |
|---|---|---|
| Evidencia que explica | ninguna | `external_llm:rationale/anthropic/claude-opus` |
| Procedencia | `INFERENCE` | `PROPOSAL` |
| Título propuesto | «Agrupación de código» | «Agrupación de clientes en colecciones del propietario» |
| Resumen | *«se realizaron cambios en varios archivos para mejorar la agrupación y organización del código»* | *«se mejoró la agrupación de clientes en las colecciones del propietario… sin incluir asignaciones creadas desde planificación»* |
| Etiquetas | refactorización, mejora de código | agrupacion, clientes, colecciones, propietario |

El primero es contenido cero. El segundo recoge incluso el filtro por microciclo, un detalle que no
aparece en ningún nombre de archivo.

### Advertencia que la medición dejó clara
El resumen con justificación dice *«mostrar el número exacto de clientes»*, cuando el cambio real fue
devolver **la lista** de clientes. **El modelo distorsionó al comprimir, aun teniendo buena
evidencia.** Refuerza que `VERIFIED` exija una persona, y es el argumento principal de DEC-026: hoy
solo se puede aceptar o rechazar entero, sin poder corregir esa frase.

### Verificado de extremo a extremo
`TASK-001` (sin justificación) descartado. `TASK-002` verificado → `CHG-142` en memoria canónica, con
`evidencia_que_explicaba` registrado en el propio registro.

---

## DEC-026 — Verificación editable de propuestas

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario

### Enunciado
> La salida del modelo **nunca es memoria canónica**, aunque esté respaldada por evidencia correcta.
> Toda propuesta puede ser aceptada, editada o rechazada; la versión editada conserva el vínculo con la
> propuesta original, y solo la versión verificada alimenta futuras recuperaciones.

### Contexto
`CHG-142` lo demostró experimentalmente: con la justificación de Claude delante, el modelo resumió
*«mostrar el número exacto de clientes»* cuando el cambio devolvía **la lista** de clientes. La
evidencia era correcta; **la compresión la estropeó**. No basta con mejorar el retrieval ni con dar más
contexto al 3B: hay que hacer editable la última milla antes de canonicalizar.

### Decisión
```
PROPOSED
    ↓
┌─────────────────────────────┐
│ Revisión humana             │
│  [A] Aceptar                │
│  [E] Editar                 │
│  [R] Rechazar               │
└──────────────┬──────────────┘
               ▼
           VERIFIED  →  memoria canónica
```

**Editar no vuelve a pasar por el modelo.** Lo que escribe la persona es lo que queda.

### Las dos versiones se conservan, nunca se sobrescriben
```json
"proposal":     { "title": "...", "summary": "...",
                  "generated_by": "llama3.2:3b",
                  "confidence_declared": "alta" },
"verification": { "title": "...", "summary": "...",
                  "verified_by": "human", "verified_at": "...",
                  "corrected_fields": ["summary"],
                  "accepted_as_is": false }
```

Eso da la traza completa: **¿qué creyó la IA? ¿qué corrigió la persona? ¿qué entró en memoria?**

### Métricas nuevas
- **Proposal Correction Rate** = propuestas modificadas / propuestas verificadas.
- **Field Correction Rate**, por campo, porque 1 de 100 propuestas corregidas no es lo mismo que 100
  de 100 con un solo campo menor tocado.

Primera medición, sobre 3 propuestas verificadas —indicativa, no concluyente:

```
Proposal Correction Rate   67%  (2 de 3)

Field Correction Rate
  type         33%
  title        33%
  summary      33%
  tags         33%
  modules       0%
  related       0%
```

**Señal temprana que merece seguimiento:** `modules` y `related` están en 0 %. Son los campos que
produce la capa determinista, y no necesitaron corrección ni una vez. Todo lo corregido —tipo, título,
resumen, etiquetas— lo genera el modelo. Con 3 muestras no prueba nada, pero apunta en la dirección que
sostiene toda la arquitectura: **lo determinista acierta, lo inferido hay que revisarlo.**

### Verificado
`CHG-142` rehecho con el flujo nuevo: el resumen impreciso corregido a mano, con la propuesta original
del modelo guardada al lado. `CHG-143` corregido en tipo, título y etiquetas. `CHG-144` aceptado tal
cual, sin tocar nada.

### Reparto de responsabilidades que esto consolida
```
Git                 ── evidencia
Claude/GPT          ── evidencia
Ollama              ── inferencia
Regla determinista  ── relación
Humano              ── verificación
```

---

## DEC-027 — Hook de git post-commit hacia OBSERVED

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario

### Decisión
Un hook `post-commit` crea el evento `OBSERVED` en `pending/` automáticamente. Su alcance es
deliberadamente mínimo.

**Lo que el hook NO hace, y no debe hacer nunca:**
llamar a Claude o GPT · ejecutar el modelo local · tocar la memoria canónica · verificar nada
automáticamente · inventar relaciones · **bloquear el commit**.

### El hook es fail-safe
Es la propiedad más importante de esta decisión. La memoria es una herramienta auxiliar del
desarrollo; **no puede convertirse en un punto único de fallo del repositorio**. Si el Context Manager
está roto, el commit sigue adelante con un aviso.

Verificado saboteando la instalación a propósito:

```
[Context Manager] WARNING: no se pudo registrar OBSERVED.
[Context Manager] El commit no fue bloqueado.
[master e1f2a3b] test: comprobar que un fallo no bloquea el commit
 1 file changed, 1 insertion(+)
codigo de salida de git commit: 0
```

El script termina siempre en `exit 0`, y comprueba que el intérprete exista antes de invocarlo.

### `observe` separado de `propose`
El hook **no ejecuta el modelo local**. Registrar lo que pasó es instantáneo; interpretarlo puede
esperar:

```
git commit → post-commit → learn.py observe → OBSERVED + EXTRACTED → pending/
                                                                        │
        cuando convenga, incluso en segundo plano:                      ▼
        learn.py propose --project P --all  ────────────────────→   PROPOSED
```

Commit real cronometrado con el hook instalado: **939 ms**, casi todo arranque de Python.

Además tiene una ventaja que no era el objetivo pero resultó valiosa: **la justificación puede llegar
después del commit**. Verificado en el repositorio de prueba — el hook registró el commit sin
explicación, y más tarde `propose --rationale` produjo *«Añadió cache en memoria para evitar recalcular
versión…»* apoyado en `external_llm:rationale/anthropic/claude-opus`.

### La evidencia es opcional y acumulativa
```
solo git                      →  funciona
git + rationale               →  propuesta claramente mejor
git + rationale + tests       →  mejor evidencia todavía
```
El sistema no depende de ninguna herramienta concreta.

### Instalación
```
python context_manager.py hook install   --project <id>
python context_manager.py hook status    --project <id>
python context_manager.py hook uninstall --project <id>
```

El instalador **no pisa un hook ajeno** sin `--force`, y marca los suyos con
`# managed-by: ai-context-manager` para poder distinguirlos. En Windows genera rutas estilo POSIX,
porque git ejecuta los hooks con `sh`.

### No instalado en el proyecto piloto
Se probó en un repositorio de usar y tirar. Un hook dispara en cada commit futuro y eso afecta al flujo
de trabajo diario, así que la instalación en un repositorio real la decide el usuario.

---

## DEC-028 — Interpretación de las métricas de corrección

- **Estado:** ACEPTADA como criterio
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario

### Criterio
El `67 %` de Proposal Correction Rate medido sobre **3 muestras no es una tasa de error real**. Lo
valioso de DEC-026 no es ese número: es que ya existe el mecanismo para medirlo.

### Hipótesis a validar, no conclusión
La observación de que `modules` y `related` están en 0 % de corrección se conserva como **hipótesis de
arquitectura**. Si tras 30–50 tareas verificadas apareciera algo del orden de:

```
modules correction     2%        title correction     35%
related correction     1%        summary correction   48%
                                 type correction      21%
                                 tags correction      29%
```

entonces habría evidencia de que **las relaciones estructurales deben computarse, no generarse** — lo
que sería una validación empírica de DEC-013, y no simplemente una observación sobre `llama3.2:3b`.

### Consecuencia
No se saca ninguna conclusión ni se cambia ninguna decisión hasta llegar a esa cantidad de tareas
verificadas.

---

## DEC-029 — Captura de sesión, no captura de Claude

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario

### Principio central
> **Automatizar la captura no significa automatizar la confianza.**
>
> El hook puede observar automáticamente. La justificación puede capturarse automáticamente. Ollama
> puede proponer automáticamente. Pero la memoria canónica sigue necesitando **evidencia +
> verificación**.

### Decisión
El sistema no se diseña alrededor de Claude. La abstracción es la **sesión de desarrollo**, y la
justificación es un fragmento de evidencia con su origen declarado:

```
                 SESIÓN DE DESARROLLO
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
         Git          Rationale       Tests
          └──────────────┼──────────────┘
                         ▼
                     TaskEvent  →  PROPOSED
```

El origen se guarda tal cual (`claude`, `gpt`, `cursor`, `copilot`, `gemini`, `human`, `terminal`,
`ci`) y **no condiciona ninguna lógica**. El Context Manager no necesita saber quién produjo la
explicación.

### Correlación temporal, no causal
El hook sabe qué commit ocurrió, pero no qué conversación lo produjo. Intentar deducirlo sería el mismo
error que inventar relaciones. Por eso el sistema registra una nota explícita:

> *«Este commit (f2a3b4c) ocurrió durante SESSION-001, abierta el… La justificación adjunta es anterior
> a él. Es correlación temporal, no una afirmación de que la causara.»*

Se sabe que el rationale **existía antes**. No se afirma que fuera la causa.

### Qué NO se guarda
La conversación completa **no entra en memoria**. Guardarla convertiría el sistema en un almacén gigante
de conversaciones, que es lo que la sección 18 de la especificación descartaba explícitamente. Solo
entra el **rationale**: la explicación del cambio. Si se quiere conservar la conversación para
auditoría, `session attach --transcript` guarda **solo su ruta como referencia**, y nunca se carga como
evidencia.

### Interfaz
```
context_manager.py session start  --project P --goal "..."
context_manager.py session attach --project P --rationale F --source claude
context_manager.py session attach --project P --transcript F   (solo auditoría)
context_manager.py session end    --project P
context_manager.py session show|list --project P
```
Las sesiones viven en `.context/sessions/` del repositorio gestionado. Solo puede haber una abierta.

### Verificado de extremo a extremo
En un repositorio de prueba, sin pasar `--rationale` en ningún momento del commit:

```
1. session start --goal "poner un tope al cache..."
2. session attach --rationale ... --source claude
3. git commit -m "fix: tope al cache"
     [Context Manager] OBSERVED creado: TASK-001
4. learn.py show →  [explica] external_llm:rationale/anthropic/claude-opus
                    [explica] tool:user_note (correlación temporal)
5. learn.py propose  →  PROPOSED
6. learn.py verify --title ... --summary ...  →  CHG-201 (VERIFIED)
     campos corregidos: type, title, summary, tags
```

La justificación entró **sola** en el evento. Y aun así, la propuesta del modelo necesitó corrección en
cuatro campos: la captura se automatizó, la confianza no.

### Ruta de integración, en orden de robustez
1. **Explícita** (implementada): `session start` / `attach`. No es totalmente automática, pero es
   robusta y no depende de ninguna herramienta.
2. **Adaptador de CLI**: capturar prompt y respuesta desde Claude Code u otro agente. Mejora la
   automatización sin volverse dependencia obligatoria.
3. **Integración con IDE**: conversación, archivos y terminal. Mucho más potente y mucho más trabajo.

---

## DEC-030 — Adaptador de CLI: leer la transcripción, no envolver la herramienta

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Corrige el diseño propuesto inicialmente**

### El diseño obvio no funciona
La propuesta inicial era `context-manager run claude`: interponerse entre el usuario y la herramienta
para capturar la interacción. **Es frágil por construcción.** Claude Code y la mayoría de agentes
modernos son **TUI a pantalla completa**, no herramientas de línea: un envoltorio captura secuencias
ANSI, movimientos de cursor y redibujados, no texto. En Windows además no existe `pty`. Y aunque
funcionara, se interpondría en la herramienta que el usuario necesita usar con fluidez.

### Lo que se descubrió al mirar
Claude Code **ya escribe una transcripción JSONL estructurada** por sesión en
`~/.claude/projects/<slug>/<uuid>.jsonl`, con `timestamp`, `cwd`, `gitBranch`, `sessionId` y los
mensajes separados por rol.

### Decisión
El adaptador **lee esa transcripción**. No envuelve nada, no se interpone, y funciona
retroactivamente sobre sesiones ya terminadas.

```
context_manager.py session import --project P [--file F] [--take 1,3] [--todo]
```

### El slug no se calcula, se comprueba
El nombre de la carpeta depende de cómo se lanzó la herramienta y **no es estable**: en este mismo
equipo conviven `C--Users-...` y `c--Users-...` para rutas equivalentes. En vez de adivinarlo, se leen
las transcripciones y se compara el campo `cwd` que llevan dentro. Es evidencia, no deducción — la
misma disciplina de siempre.

### Candidatos, no memoria
La extracción es determinista y conservadora:

- solo mensajes del asistente, nunca llamadas a herramientas;
- por debajo de 200 caracteres se descarta (no explica nada);
- se puntúan por señales léxicas de trabajo hecho (*porque*, *la causa*, *descarté*, *en vez de*…);
- se filtran por la ventana temporal de la sesión abierta, con `--todo` como escape.

**La herramienta propone; la persona elige.** Ninguna se convierte en rationale sin selección explícita.

### Verificado sobre datos reales
Se detectaron **9 transcripciones reales** de sesiones en el proyecto piloto. De la más rica (39 fragmentos),
los mejor puntuados incluían material genuinamente valioso:

> *«Verifiqué el código y encontré la causa raíz. El bloqueo no está protegiendo lo que crees…»*

### Limitación honesta, y por qué no se parchea
El puntuador también sube fragmentos que son **conversación, no explicación de trabajo**:

> *«Sí, entendiste bien — pero el matiz importa…»*

Comparten el mismo vocabulario causal. Distinguirlos exigiría un modelo interpretando, que es
exactamente lo que este proyecto mantiene fuera del camino crítico. **Por eso el diseño no intenta
acertar: ordena candidatos y deja que la persona elija.** El puntuador ahorra lectura, no decide.

### La conversación no entra en memoria
Solo los fragmentos seleccionados se convierten en `rationale`. La transcripción completa se guarda
como `transcript_ref` para auditoría y **nunca se carga como evidencia** (DEC-029).

### Lo que este adaptador NO hace
No modifica git · no llama al modelo local · no convierte nada en memoria automáticamente · no se
interpone en la herramienta · no depende de que Claude Code esté corriendo.

### Estado del ciclo
Con esto la captura deja de ser una necesidad y pasa a ser una cuestión de fricción:

```
antes:  «necesitamos capturar el rationale para cerrar el ciclo»
ahora:  «el ciclo ya está cerrado; esto reduce lo que cuesta alimentarlo»
```

---

## DEC-031 — Congelación arquitectónica y fase de uso real

- **Estado:** ACEPTADA
- **Fecha:** 2026-08-20
- **Decidido por:** el usuario

### Decisión
**Se congelan las decisiones arquitectónicas grandes.** No hay DEC-032 planificada. Las siguientes
decisiones deben salir de **fallos observados usando el sistema en desarrollo real**, no de anticipar
otro problema teórico.

### Motivo
El riesgo principal dejó de ser técnico. El circuito funciona de extremo a extremo y está medido. El
riesgo que queda es de uso:

> ¿La arquitectura que funciona en pruebas se alimenta de forma sostenible mientras se programa todos
> los días?

Eso no lo contesta ningún test.

### Qué observar
1. Cuántas veces se selecciona realmente un rationale, y cuánto cuesta hacerlo.
2. Cuántos `OBSERVED` terminan en `VERIFIED`, y cuántos se quedan pendientes para siempre.
3. Si la correlación sesión → commit sigue siendo útil en tareas con **varios commits**.
4. Si una misma sesión acaba generando cambios de **temas distintos**.
5. Si el hook introduce fricción real en el flujo diario.

### Instrumentación
Se añadió `context_manager.py status --project P`, que responde a esas preguntas con datos en vez de
impresiones: embudo del ciclo, antigüedad de lo pendiente, tasa de verificación, corrección por campo,
sesiones con más de un commit, sesiones cerradas sin rationale, y estado del hook.

Es lo único que se construyó en esta fase, y a propósito: **medir el uso no es añadir arquitectura.**

### Estado medido al congelar
```
EMBUDO           pendientes 0 · verificados 3 · tasa 100 %
PROPUESTAS       Proposal Correction Rate 67 % (indicativo, DEC-028)
MEMORIA          115 registros
PROCEDENCIA      FACT 27 · RESOLVED 18 · DECISION 7 · INFERENCE 63
HOOK             SIN INSTALAR
```

### Un dato que conviene vigilar desde el primer día
**63 de 115 registros son `INFERENCE`** — más de la mitad de la memoria canónica. Vienen de la
extracción masiva del historial de git, donde el commit no traía cuerpo que explicara nada. Viajan
marcados y el Context Builder los presenta como no confirmados, así que el sistema es honesto sobre
ellos. Pero son el grueso del corpus, y el uso real dirá si esa proporción estorba o si simplemente
refleja que el proyecto tenía muchos commits sin explicación.

No se toca ahora. Es exactamente el tipo de cosa que debe decidirse con uso, no con teoría.

**La pregunta correcta no es «¿63 es demasiado?»**, sino **¿los `INFERENCE` contaminan de verdad las
tareas futuras?** Señales concretas que habría que ver durante el uso real:

- los primeros resultados son con frecuencia `INFERENCE` poco útiles;
- hay que ignorarlos una y otra vez;
- las decisiones y soluciones verificadas quedan enterradas debajo;
- un `INFERENCE` acaba influyendo en una propuesta incorrecta;
- o, al contrario, resultan útiles como antecedente aunque no estén confirmados.

Solo con alguna de esas señales repetida habría evidencia para abrir una decisión. Ya hay dos
protecciones activas mientras tanto: conservan su procedencia, y el Context Builder los presenta
marcados como no confirmados.

### El hook queda sin instalar
La activación en el proyecto piloto la decide el usuario:

```
python context_manager.py hook install --project piloto
```

---

## DEC-032 — Tres modos de IA local, no un interruptor

- **Estado:** ACEPTADA
- **Fecha:** 2026-09-26
- **Decidido por:** el usuario
- **Origen:** primera decisión posterior a la congelación de DEC-031, motivada por una necesidad de uso
  real (ahorrar recursos) y no por un problema teórico

### Contexto
Al integrar el servidor MCP surgió la necesidad de poder apagar la IA local para ahorrar recursos. La
petición inicial era un interruptor de encendido y apagado.

### Por qué un interruptor binario era la forma equivocada
La «IA local» son **dos piezas con relación coste-beneficio opuesta**:

| Pieza | Coste | Beneficio medido |
|---|---|---|
| `llama3.2:3b` (intención) | 4–10 s por consulta, ~2 GB residentes | solo reordena: DEC-015 le quitó el poder de admitir candidatos por ser demasiado grueso |
| `nomic-embed-text` | ~0,3 s, ~300 MB, índice ya calculado | recall de sinónimos ×2, nDCG ×3,6 |

**El modelo caro es el que menos aporta.** Un interruptor único obliga a tirar los dos juntos.

### Decisión
Tres modos, con el intermedio por defecto:

```
completo   intención + embeddings      máxima calidad, máximo coste
ahorro     solo embeddings             ← por defecto
minimo     solo léxico                 no necesita Ollama en absoluto
```

**Alcance:** ajuste global con anulación por proyecto. Precedencia:
`ACM_MODO` (entorno) → anulación del proyecto → global → `ahorro`.

### Por qué persistente y no banderas
El servidor MCP **no puede recibir banderas**: lo lanza el IDE. Sin un ajuste en disco, la extensión
intentaría siempre usar el modelo generativo aunque no se quisiera. Las banderas antiguas
(`--no-llm`, `--lexico`) siguen funcionando y restringen sobre el modo, para no romper guiones ya
escritos.

### Tres detalles que hacen que el ahorro sea real
1. **Salud recordada.** Sin ella, cada invocación de la CLI paga el intento de conexión. Con el
   servicio parado el fallo es inmediato, pero con uno colgado se espera el tiempo completo cada vez.
   Se recuerda 30 s en disco, porque un proceso de CLI vive un instante.
2. **Descarga explícita.** Dejar de llamar al modelo no lo baja: Ollama lo mantiene cargado unos
   minutos. `ia descargar` lo libera de verdad con `keep_alive: 0`.
3. **El modo viaja en la respuesta.** Un modo reducido devuelve menos, y callarlo sería devolver menos
   en silencio. El bloque de contexto del MCP empieza declarando con qué modo se construyó.

### Hallazgo colateral, y probablemente el mayor ahorro
Ninguna pieza del flujo diario usa el grafo:

```
ask.py · learn.py · context_manager.py · mcp_server.py  →  0 referencias a FalkorDB
```

Solo lo usan `graph.py` y su prueba de humo. La recuperación lee JSONL y `.vectors.json`
directamente. **Los 4 GB que WSL2 reserva para Docker no sirven para nada en el uso normal**, y
apagarlo ahorra más que cualquiera de estos modos sin escribir una línea de código.

### Interfaz
```
python context_manager.py ia estado      [--project P]
python context_manager.py ia ahorro      [--project P]
python context_manager.py ia completo | minimo
python context_manager.py ia reiniciar   --project P    (quita la anulación)
python context_manager.py ia descargar                  (libera la RAM de Ollama)
```
