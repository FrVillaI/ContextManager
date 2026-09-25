# Context Manager como extensión de tu IDE (MCP)

Esta carpeta convierte el Context Manager en un **servidor MCP** para que tu
editor con agente lo llame por sí mismo. En lugar de ejecutar `python ask.py`,
copiar el bloque y pegarlo en el chat, el agente del IDE pide el contexto solo,
antes de tocar el código, mediante la herramienta `pedir_contexto`.

Funciona en:

- **Visual Studio Code** (modo agente / GitHub Copilot)
- **Google Antigravity** (IDE y CLI)
- **Orca** ([tryorca.com](https://tryorca.com/))

y en cualquier otro cliente MCP (Cursor, Claude Desktop, Gemini CLI…), porque
todos hablan el mismo protocolo.

---

## Por qué MCP y no tres extensiones nativas

VS Code, Antigravity y Orca son clientes del **Model Context Protocol (MCP)**: el
estándar por el que un IDE con IA descubre y llama herramientas externas. Un solo
servidor MCP los cubre a los tres —y a los que vengan— en vez de mantener tres
extensiones nativas distintas.

El servidor es **`mcp_server.py`**, escrito solo con la biblioteca estándar de
Python. No añade dependencias al proyecto y no depende de la versión del SDK de
MCP. Reutiliza los módulos que ya existen (`acm.context`, `acm.retrieval`,
`acm.hybrid`, `acm.intent`…), así que se comporta **exactamente igual que
`ask.py`**.

---

## Qué expone

### Herramientas

| Herramienta | Qué hace |
|---|---|
| **`pedir_contexto`** | El flujo central. Recibe la tarea en lenguaje natural y devuelve el bloque de contexto listo (bugs previos, decisiones vigentes, restricciones, soluciones que ya funcionaron). Si no hay precedentes, lo dice en vez de inventarlos. |
| **`buscar_memoria`** | Como `pedir_contexto` pero devuelve los registros en JSON estructurado, sin montar el bloque de texto. |
| **`detalle_registro`** | Un registro concreto por su id (p. ej. `BUG-003`), con todos sus campos. |
| **`listar_proyectos`** | Los proyectos gestionados y cuántos registros tiene cada uno. |
| **`estado_proyecto`** | Salud de la memoria: registros por tipo y procedencia, cuántos están confirmados, integridad de los enlaces. |

### Prompt

- **`contexto_para_tarea`** — plantilla invocable desde el IDE que le dice al
  agente que pida contexto antes de empezar.

> **Solo lectura.** El servidor lee la memoria y construye contexto; **no asciende
> nada a memoria**. Aprender y verificar sigue siendo un paso humano
> (`learn.py verify`), tal como manda el diseño del sistema (DEC‑023). El ciclo de
> aprendizaje se sigue haciendo por CLI.

---

## Requisitos

Lo mismo que el Context Manager (ver el [README principal](../README.md)):

- Python 3.13 y las dependencias de `requirements.txt` instaladas, idealmente en
  un entorno virtual `.venv` dentro de la raíz del proyecto.
- Opcional, para el análisis de intención y la capa semántica: Ollama con
  `llama3.2:3b` y `nomic-embed-text`. **Si no están, el servidor degrada a
  solapamiento léxico automáticamente**, igual que `ask.py`.
- Al menos un proyecto con memoria. Para probar sin conectar nada tuyo:

  ```bash
  python tools/seed_demo.py
  ```

---

## Cómo lo prueba (sin IDE)

Para comprobar que el servidor responde, hay un pequeño arranque manual: lánzalo
y quedará esperando mensajes JSON‑RPC por la entrada estándar.

```bash
python integrations/mcp_server.py
```

Lo normal es no ejecutarlo a mano: lo lanza el IDE. Para eso están los
lanzadores.

---

## Los lanzadores

Los IDE necesitan **un comando** que arranque el servidor. En vez de pedirte que
pongas la ruta de Python y variables de entorno en cada configuración, usa uno de
estos, que ya resuelven el `.venv` y `CONTEXT_MANAGER_HOME`:

- `integrations/run-context-mcp.sh` — Linux y macOS
- `integrations/run-context-mcp.cmd` — Windows

En Linux/macOS, hazlo ejecutable una vez:

```bash
chmod +x integrations/run-context-mcp.sh
```

En todas las configuraciones de más abajo, **sustituye
`/ruta/absoluta/a/ContextManager`** por la ruta real de tu instalación. En
Windows, cambia además `run-context-mcp.sh` por `run-context-mcp.cmd` y usa
rutas de Windows, p. ej.:

```
C:\\Users\\tu-usuario\\ContextManager\\integrations\\run-context-mcp.cmd
```

---

## Variables de entorno

El servidor decide en qué memoria busca con el mismo criterio que `ask.py`. Se
puede ajustar con:

| Variable | Para qué |
|---|---|
| `CONTEXT_MANAGER_HOME` | Raíz de la instalación (donde vive `memory/`). Los lanzadores la ponen solos. |
| `CONTEXT_MANAGER_WORKSPACE` | Carpeta del repo en el que trabajas. El servidor lee ahí `.context/project.json` para deducir el proyecto. En VS Code se pasa `${workspaceFolder}`. |
| `CONTEXT_MANAGER_PROJECT` | `project_id` por defecto, cuando la llamada no lo indica y no hay `.context/project.json`. |

Orden de resolución del proyecto en cada llamada: `project` explícito →
`.context/project.json` del workspace → `CONTEXT_MANAGER_PROJECT` → único proyecto
en disco → error pidiendo que lo indiques.

---

## Visual Studio Code

VS Code lee la configuración MCP de `.vscode/mcp.json` (por workspace) o del
`settings.json` del usuario. Copia [`vscode/mcp.json`](vscode/mcp.json) a la
carpeta `.vscode/` del repositorio en el que trabajas y corrige la ruta:

```jsonc
{
  "servers": {
    "context-manager": {
      "type": "stdio",
      "command": "/ruta/absoluta/a/ContextManager/integrations/run-context-mcp.sh",
      "args": [],
      "env": { "CONTEXT_MANAGER_WORKSPACE": "${workspaceFolder}" }
    }
  }
}
```

`${workspaceFolder}` hace que el proyecto se deduzca solo desde el
`.context/project.json` del repo abierto (si lo has inicializado con
`python context_manager.py init`). Si no, añade `"CONTEXT_MANAGER_PROJECT"` al
bloque `env`.

Después: abre el chat en **modo agente**, comprueba que `context-manager` aparece
en la lista de herramientas y pídele algo como *«pide contexto para añadir
paginación al catálogo»*.

---

## Google Antigravity

Antigravity (IDE, versión 2.0 y CLI) comparte la configuración MCP en
`~/.gemini/config/mcp_config.json`. También puedes abrirla desde el IDE:
**Settings → Customizations → Open MCP Config**, o desde el panel del agente
(**… → Manage MCP Servers → View raw config**).

Añade el bloque de [`antigravity/mcp_config.json`](antigravity/mcp_config.json)
dentro de `mcpServers` (fusiónalo con lo que ya tengas):

```json
{
  "mcpServers": {
    "context-manager": {
      "command": "/ruta/absoluta/a/ContextManager/integrations/run-context-mcp.sh",
      "args": [],
      "env": { "CONTEXT_MANAGER_PROJECT": "mi-proyecto" }
    }
  }
}
```

Usa rutas absolutas para el comando y pon `CONTEXT_MANAGER_PROJECT` con el
`project_id` que quieras por defecto (`python context_manager.py list` te los
muestra). Recarga los servidores MCP desde el panel del agente.

---

## Orca (tryorca.com)

Orca es un cliente MCP que habla con servidores por **stdio**, trae tus propias
claves y no tiene telemetría. Regístralo desde los ajustes de MCP de Orca (o su
archivo de configuración de MCP), con el mismo bloque `mcpServers` de
[`orca/mcp.json`](orca/mcp.json):

```json
{
  "mcpServers": {
    "context-manager": {
      "command": "/ruta/absoluta/a/ContextManager/integrations/run-context-mcp.sh",
      "args": [],
      "env": { "CONTEXT_MANAGER_PROJECT": "mi-proyecto" }
    }
  }
}
```

La ubicación exacta del archivo/ajuste de MCP puede variar entre versiones de
Orca: búscala en su apartado de configuración de MCP y pega ahí este bloque
(formato `mcpServers` estándar, idéntico al de Claude Desktop o Cursor). El
comando y las variables de entorno son los mismos que para los otros IDE.

---

## El flujo de trabajo, ya integrado

1. **Registra el proyecto** una vez, para que el IDE deduzca cuál es:

   ```bash
   python context_manager.py init /ruta/a/tu/repo --name MiProyecto
   ```

   Esto crea `.context/project.json` en el repo, que el servidor lee.

2. **Siembra memoria** desde el historial de git (opcional pero recomendado, por
   el arranque en frío):

   ```bash
   python tools/extract_from_git.py --project miproyecto --limit 95 --write
   ```

3. **Trabaja en tu IDE.** El agente llama a `pedir_contexto` antes de cambiar
   nada y recibe solo los precedentes, decisiones y restricciones que aplican.

4. **Aprende de lo que hiciste** (sigue siendo por CLI, con verificación humana):

   ```bash
   python learn.py propose --project miproyecto --all
   python learn.py verify  --project miproyecto TASK-001
   ```

---

## Resolución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| El IDE no ve la herramienta | Ruta del comando incorrecta | Usa la ruta **absoluta** al lanzador; en Windows, el `.cmd`. |
| «No se pudo deducir el proyecto» | Sin `.context/project.json` ni variable | Pasa `project` en la llamada o define `CONTEXT_MANAGER_PROJECT`. |
| Contexto vacío en un proyecto nuevo | Arranque en frío (< ~30 registros) | Siembra desde git (paso 2). Es el comportamiento documentado, no un fallo. |
| Aviso «modelo de intención no disponible» | Ollama apagado | Es degradación esperada: sigue con léxico. Arranca Ollama para recuperar intención y semántica. |
| Nada funciona al arrancar | Dependencias sin instalar | Instala `requirements.txt`, mejor en `.venv`, y reinicia el servidor MCP desde el IDE. |

Las trazas del servidor van a **stderr** (nunca a stdout, que es el canal del
protocolo). Tu IDE suele mostrarlas en el registro/salida del servidor MCP.
