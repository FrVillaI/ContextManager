"""Context Manager — gestion de proyectos (DEC-018).

    python context_manager.py init <ruta-del-repositorio> [--name NOMBRE]
    python context_manager.py list
    python context_manager.py show <project_id>

`init` convierte cualquier repositorio en un proyecto gestionado. Todo lo que
registra es **evidencia observada** —archivos que existen, directorios que
existen, git que esta o no esta— nunca una inferencia del modelo.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from acm.models import MemoryRecord, Provenance, Source, SourceKind  # noqa: E402
from acm.projects import (  # noqa: E402
    Project, Registry, git_remote, inspect, read_context_file, slugify,
    write_context_file,
)
from acm.store import MemoryStore, all_projects  # noqa: E402
from datetime import datetime  # noqa: E402

MEMORY = ROOT / "memory"


def cmd_init(args: argparse.Namespace) -> int:
    repo = Path(args.path).resolve()
    if not repo.is_dir():
        print(f"no existe el directorio {repo}", file=sys.stderr)
        return 1

    existente = read_context_file(repo)
    if existente and not args.force:
        print(f"este repositorio ya es el proyecto '{existente['project_id']}'.")
        print("usa --force para reinicializarlo.")
        return 1

    nombre = args.name or repo.name
    pid = slugify(nombre)

    # --- Paso 1: identificar -------------------------------------------------
    stack, directorios, tiene_git = inspect(repo)
    remoto = git_remote(repo) if tiene_git else ""

    print(f"Proyecto : {nombre}")
    print(f"Id       : {pid}")
    print(f"Ruta     : {repo}")
    print(f"Git      : {'detectado' if tiene_git else 'NO detectado'}"
          f"{f' ({remoto})' if remoto else ''}")
    print(f"Stack    : {', '.join(stack) or '(nada reconocible)'}")
    print(f"Carpetas : {', '.join(directorios) or '(ninguna)'}")

    if args.dry_run:
        print("\n(simulacion: no se ha escrito nada)")
        return 0

    # --- Paso 2: registrar ---------------------------------------------------
    proyecto = Project(
        project_id=pid, name=nombre, repository=str(repo),
        stack=stack, directories=directorios,
    )
    Registry(ROOT).add(proyecto)
    destino = write_context_file(repo, proyecto)

    # --- Paso 3: memoria base ------------------------------------------------
    # Un unico registro de tipo `project` con lo observado. Nada mas: la memoria
    # de un proyecto nuevo empieza vacia y la construye el desarrollo.
    store = MemoryStore(MEMORY, pid)
    if not store.read("project"):
        store.append(MemoryRecord(
            id="PROJECT-001", type="project",
            project_id=pid, project=nombre,
            title=f"{nombre} — estructura observada al inicializar",
            provenance=Provenance.FACT,
            source=Source(kind=SourceKind.FILE, ref=str(repo),
                          detail="inspeccion del arbol de directorios"),
            created_at=proyecto.created_at,
            summary=(
                f"Stack detectado por presencia de archivos: "
                f"{', '.join(stack) or 'ninguno reconocible'}. "
                f"Directorios de primer nivel: {', '.join(directorios) or 'ninguno'}."
            ),
            modules=directorios[:8],
            tags=["estructura", "inicializacion"],
            body={"git": tiene_git, "remote": remoto, "stack": stack},
        ))

    print(f"\nRegistrado en   {Registry(ROOT).path.name}")
    print(f"Identidad en    {destino}")
    print(f"Memoria en      memory/{pid}/  ({sum(store.stats().values())} registro)")
    print("\nLa memoria de este proyecto empieza vacia. La construye el desarrollo.")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    registro = Registry(ROOT).load()
    con_memoria = set(all_projects(MEMORY))
    if not registro and not con_memoria:
        print("no hay proyectos registrados. Usa 'init <ruta>'.")
        return 0

    print(f"{'project_id':<20} {'registros':>9}  repositorio")
    print("-" * 74)
    for pid in sorted(set(registro) | con_memoria):
        p = registro.get(pid)
        n = sum(MemoryStore(MEMORY, pid).stats().values()) if pid in con_memoria else 0
        repo = p.repository if p else "(sin registrar en projects.json)"
        print(f"{pid:<20} {n:>9}  {repo}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    p = Registry(ROOT).get(args.project_id)
    if not p:
        print(f"no conozco el proyecto '{args.project_id}'", file=sys.stderr)
        return 1
    store = MemoryStore(MEMORY, p.project_id)
    print(f"{p.name}  ({p.project_id})")
    print(f"  repositorio : {p.repository}")
    print(f"  namespace   : {p.memory_namespace}")
    print(f"  stack       : {', '.join(p.stack) or '-'}")
    print(f"  memoria     : {store.stats()}")
    problemas = store.check()
    print(f"  integridad  : {'OK' if not problemas else problemas[:3]}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Salud del ciclo de memoria durante el uso real (DEC-031).

    Responde a preguntas que los tests no pueden contestar: cuanto se acumula sin
    revisar, cuanto de lo observado acaba siendo memoria, y si el modelo local
    acierta lo suficiente como para que revisar no canse.
    """
    from collections import Counter
    from datetime import date as _date

    from acm import sessions as ss
    from acm.events import load_events
    from acm.review import EDITABLES, correction_stats

    proyecto = Registry(ROOT).get(args.project)
    if not proyecto:
        print(f"no conozco el proyecto '{args.project}'", file=sys.stderr)
        return 1
    repo = Path(proyecto.repository)
    store = MemoryStore(MEMORY, args.project)
    registros = list(store.all())

    print(f"{proyecto.name}  ({args.project})")
    print("=" * 62)

    # --- embudo: que parte de lo observado llega a memoria ------------------
    pendientes = load_events(MEMORY, args.project)
    sin_propuesta = [e for e in pendientes if not e.proposal]
    verificados = [r for r in registros if r.body.get("task_id")]

    print()
    print("EMBUDO DEL CICLO")
    print(f"  pendientes sin revisar     {len(pendientes)}"
          f"{f'  ({len(sin_propuesta)} sin interpretar)' if sin_propuesta else ''}")
    print(f"  verificados desde el ciclo {len(verificados)}")
    total_ciclo = len(pendientes) + len(verificados)
    if total_ciclo:
        print(f"  tasa de verificacion       {len(verificados) / total_ciclo:.0%}")
    if pendientes:
        viejo = min(e.created_at for e in pendientes)
        try:
            dias = (_date.today() - _date.fromisoformat(viejo[:10])).days
            print(f"  el mas antiguo lleva       {dias} dia(s) esperando")
        except ValueError:
            pass

    # --- correcciones: cuanto cuesta revisar --------------------------------
    stats = correction_stats(registros)
    print()
    print("CALIDAD DE LAS PROPUESTAS")
    if not stats.verificadas:
        print("  todavia sin datos: nada verificado por el flujo de revision")
    else:
        print(f"  propuestas verificadas     {stats.verificadas}")
        print(f"  Proposal Correction Rate   {stats.proposal_correction_rate:.0%}")
        if stats.verificadas < 30:
            print(f"  (indicativo: hacen falta 30-50 para que signifique algo, DEC-028)")
        for campo in EDITABLES:
            n = stats.por_campo.get(campo, 0)
            if n:
                print(f"    {campo:<10} {stats.field_rate(campo):>4.0%}")

    # --- sesiones ------------------------------------------------------------
    try:
        sesiones = ss.load_all(repo)
    except OSError:
        sesiones = []
    print()
    print("SESIONES")
    if not sesiones:
        print("  ninguna todavia")
    else:
        abiertas = [s for s in sesiones if s.open]
        multi = [s for s in sesiones if len(s.commits) > 1]
        sin_rationale = [s for s in sesiones if not s.open and not s.rationale]
        print(f"  totales {len(sesiones)}   abiertas {len(abiertas)}")
        print(f"  con mas de un commit       {len(multi)}"
              "   <- vigila si la correlacion sigue siendo util")
        print(f"  cerradas sin rationale     {len(sin_rationale)}"
              "   <- friccion: no se llego a capturar")
        for s in abiertas:
            print(f"  abierta: {s.describe()}")

    # --- memoria -------------------------------------------------------------
    print()
    print("MEMORIA CANONICA")
    print(f"  registros {len(registros)}   {dict(store.stats())}")
    proc = Counter(r.provenance.value for r in registros)
    print(f"  procedencia {dict(proc)}")
    hook_ok, gestionado = __import__("acm.hooks", fromlist=["hooks"]).status(repo)
    estado_hook = ("instalado" if hook_ok and gestionado
                   else "hook ajeno" if hook_ok else "SIN INSTALAR")
    print()
    print(f"HOOK POST-COMMIT  {estado_hook}")
    if not hook_ok:
        print(f"  sin el, hay que ejecutar 'learn.py observe' a mano tras cada commit")
    return 0


def cmd_ia(args: argparse.Namespace) -> int:
    """Enciende, apaga o consulta la IA local (DEC-032)."""
    from acm.settings import (
        MODOS, clear_project_mode, forget_health, loaded_models,
        ollama_disponible, resolve, set_mode, unload_models,
    )

    if args.accion == "descargar":
        # Dejar de llamar al modelo no lo baja: Ollama lo mantiene cargado unos
        # minutos. Para recuperar la RAM hay que pedirlo.
        cargados = loaded_models()
        if not cargados:
            print("Ollama no tiene ningun modelo cargado.")
            return 0
        nombres = [m.get("name") or m.get("model", "?") for m in cargados]
        for m in cargados:
            mb = round(m.get("size_vram", m.get("size", 0)) / 1024 / 1024)
            print(f"  descargando {m.get('name', '?')}  ({mb} MB)")
        for nombre, ok in unload_models(nombres):
            print(f"  {'liberado' if ok else 'NO se pudo liberar'}  {nombre}")
        return 0

    if args.accion == "estado":
        efectivo = resolve(ROOT, args.project)
        print(f"modo efectivo{f' para {args.project}' if args.project else ''}: "
              f"{efectivo.describe()}")
        print(f"  {efectivo.descripcion}")
        print()
        disponible = ollama_disponible(ROOT, usar_cache=False)
        print(f"Ollama: {'responde' if disponible else 'NO responde'}")
        if disponible:
            cargados = loaded_models()
            if cargados:
                for m in cargados:
                    mb = round(m.get("size_vram", m.get("size", 0)) / 1024 / 1024)
                    print(f"  cargado: {m.get('name','?')}  {mb} MB")
            else:
                print("  sin modelos cargados en memoria")
        elif efectivo.usa_intencion or efectivo.usa_embeddings:
            print("  las consultas caeran a solapamiento lexico hasta que arranque")
        print()
        print("Modos disponibles:")
        for nombre, m in MODOS.items():
            marca = "->" if nombre == efectivo.nombre else "  "
            print(f"  {marca} {nombre:<9} {m.descripcion}")
        return 0

    if args.accion == "reiniciar":
        if not args.project:
            print("indica --project: 'reiniciar' quita la anulacion de un proyecto",
                  file=sys.stderr)
            return 1
        quitado = clear_project_mode(ROOT, args.project)
        print(f"{args.project}: {'anulacion retirada, vuelve al modo global' if quitado else 'no tenia anulacion propia'}")
        return 0

    # establecer un modo
    try:
        modo = set_mode(ROOT, args.accion, args.project)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    forget_health(ROOT)
    ambito = f"para {args.project}" if args.project else "globalmente"
    print(f"modo {modo.nombre} {ambito}: {modo.descripcion}")
    if not modo.usa_intencion and not modo.usa_embeddings:
        print()
        print("Ollama ya no hace falta. Para recuperar su memoria ahora:")
        print("  python context_manager.py ia descargar")
    return 0


def cmd_hook(args: argparse.Namespace) -> int:
    """Gestiona el hook post-commit de un proyecto (DEC-027)."""
    from acm import hooks

    proyecto = Registry(ROOT).get(args.project)
    if not proyecto:
        print(f"no conozco el proyecto '{args.project}'", file=sys.stderr)
        return 1
    repo = Path(proyecto.repository)

    if args.accion == "status":
        existe, gestionado = hooks.status(repo)
        ruta = hooks.hook_path(repo)
        if not existe:
            print(f"sin hook en {ruta}")
        elif gestionado:
            print(f"instalado y gestionado por el Context Manager: {ruta}")
        else:
            print(f"hay un hook ajeno en {ruta}; el Context Manager no lo tocara")
        return 0

    if args.accion == "install":
        ok, detalle = hooks.install(repo, args.project, ROOT, force=args.force)
        if not ok:
            print(detalle, file=sys.stderr)
            return 1
        print(f"hook instalado en {detalle}")
        print()
        print("A partir de ahora, cada commit en este repositorio creara un")
        print("OBSERVED en el area de espera. El hook no ejecuta ningun modelo")
        print("y nunca bloquea el commit.")
        print()
        print(f"Para interpretar lo observado cuando convenga:")
        print(f"  python learn.py propose --project {args.project} --all")
        return 0

    ok, detalle = hooks.uninstall(repo)
    print(detalle if not ok else f"hook retirado de {detalle}")
    return 0 if ok else 1


def cmd_session(args: argparse.Namespace) -> int:
    """Sesion de desarrollo y captura de justificacion (DEC-029)."""
    from acm import sessions as ss

    proyecto = Registry(ROOT).get(args.project)
    if not proyecto:
        print(f"no conozco el proyecto '{args.project}'", file=sys.stderr)
        return 1
    repo = Path(proyecto.repository)

    if args.accion == "start":
        abierta = ss.open_session(repo)
        if abierta and not args.force:
            print(f"ya hay una sesion abierta: {abierta.describe()}", file=sys.stderr)
            print("cierrala con 'session end' o usa --force", file=sys.stderr)
            return 1
        s = ss.Session(
            session_id=ss.next_session_id(repo),
            project_id=args.project,
            head_at_start=ss.git_head(repo),
            goal=args.goal or "",
        )
        ss.save(s, repo)
        print(f"{s.session_id} abierta  (HEAD {s.head_at_start or '-'})")
        if s.goal:
            print(f"  objetivo: {s.goal}")
        print()
        print("Trabaja normalmente. Al terminar, adjunta la explicacion del cambio:")
        print(f"  python context_manager.py session attach --project {args.project} "
              "--rationale FICHERO --source claude")
        return 0

    if args.accion == "attach":
        s = ss.load(repo, args.session) if args.session else ss.open_session(repo)
        if not s:
            print("no hay sesion abierta. Usa 'session start'.", file=sys.stderr)
            return 1

        if args.transcript:
            # Referencia para auditoria. NO se carga como evidencia ni entra en
            # memoria: guardar conversaciones enteras es justo lo que la
            # especificacion descartaba.
            s.transcript_ref = str(Path(args.transcript).resolve())
            print(f"transcripcion referenciada (solo auditoria): {Path(args.transcript).name}")

        if args.rationale:
            archivo = Path(args.rationale)
            if not archivo.exists():
                print(f"no encuentro {archivo}", file=sys.stderr)
                return 1
            s.rationale.append(ss.RationaleFragment(
                content=archivo.read_text(encoding="utf-8", errors="replace"),
                source=args.source, provider=args.provider, model=args.model_externo,
            ))
            print(f"rationale adjuntado a {s.session_id}  (origen: {args.source})")
        elif args.text:
            s.rationale.append(ss.RationaleFragment(
                content=args.text, source=args.source,
                provider=args.provider, model=args.model_externo,
            ))
            print(f"rationale adjuntado a {s.session_id}  (origen: {args.source})")
        elif not args.transcript:
            print("indica --rationale FICHERO, --text TEXTO o --transcript FICHERO",
                  file=sys.stderr)
            return 1

        ss.save(s, repo)
        return 0

    if args.accion == "import":
        from acm import transcripts as tr

        s = ss.load(repo, args.session) if args.session else ss.open_session(repo)
        if not s:
            print("no hay sesion abierta. Usa 'session start'.", file=sys.stderr)
            return 1

        if args.file:
            encontradas = [tr.parse(Path(args.file))]
        else:
            encontradas = tr.find_for_repo(repo)
        if not encontradas:
            print(f"no encuentro transcripciones de agente para {repo}", file=sys.stderr)
            print("indica una con --file, o adjunta la explicacion con "
                  "'session attach --rationale'", file=sys.stderr)
            return 1

        t = encontradas[0]
        print(f"transcripcion: {t.path.name}")
        print(f"  cwd    : {t.cwd}")
        print(f"  rama   : {t.branch or '-'}")
        print(f"  ultimo : {t.ended[:19] or '?'}")

        cands = tr.candidates(t, since=s.started_at if not args.todo else "",
                              limit=args.limit)
        if not cands:
            print("no hay fragmentos explicativos en la ventana de la sesion.")
            print("prueba con --todo para ignorar la ventana temporal.")
            return 0

        print()
        print(f"{len(cands)} fragmentos CANDIDATOS (ninguno es memoria todavia):")
        for i, f in enumerate(cands, 1):
            print(f"  [{i}] {f.timestamp[:19]}  {f.preview()}")

        elegidos: list[int] = []
        if args.take:
            elegidos = [int(x) for x in args.take.split(",")
                        if x.strip().isdigit() and 1 <= int(x) <= len(cands)]
        else:
            print()
            print("  Cuales son la explicacion del cambio? (ej: 1,3 — vacio para ninguno)")
            try:
                respuesta = input("  > ").strip()
            except EOFError:
                respuesta = ""
            elegidos = [int(x) for x in respuesta.split(",")
                        if x.strip().isdigit() and 1 <= int(x) <= len(cands)]

        if not elegidos:
            print("no se adjunto ningun fragmento.")
            return 0

        for i in elegidos:
            f = cands[i - 1]
            s.rationale.append(ss.RationaleFragment(
                content=f.text, source=args.source or "claude",
                provider=args.provider or "anthropic",
                model=args.model_externo,
                captured_at=f.timestamp[:19] or datetime.now().isoformat(timespec="seconds"),
            ))
        # La conversacion completa se referencia, nunca se carga (DEC-029).
        s.transcript_ref = str(t.path)
        ss.save(s, repo)
        print(f"{len(elegidos)} fragmento(s) adjuntados a {s.session_id}")
        print(f"transcripcion referenciada para auditoria: {t.path.name}")
        return 0

    if args.accion == "end":
        s = ss.load(repo, args.session) if args.session else ss.open_session(repo)
        if not s:
            print("no hay sesion abierta.", file=sys.stderr)
            return 1
        from datetime import datetime
        s.ended_at = datetime.now().isoformat(timespec="seconds")
        ss.save(s, repo)
        print(f"{s.session_id} cerrada  ({len(s.rationale)} rationale, "
              f"{len(s.commits)} commits)")
        return 0

    if args.accion == "show":
        s = ss.load(repo, args.session) if args.session else ss.open_session(repo)
        if not s:
            print("no hay sesion que mostrar.", file=sys.stderr)
            return 1
        print(s.describe())
        print(f"  iniciada : {s.started_at}   HEAD {s.head_at_start or '-'}")
        if s.ended_at:
            print(f"  cerrada  : {s.ended_at}")
        for c in s.commits:
            print(f"  commit   : {c}")
        for f in s.rationale:
            primera = f.content.strip().splitlines()[0] if f.content.strip() else ""
            print(f"  rationale: [{f.source}] {primera[:56]}")
        if s.transcript_ref:
            print(f"  transcripcion (solo auditoria): {s.transcript_ref}")
        return 0

    # list
    todas = ss.load_all(repo)
    if not todas:
        print("no hay sesiones en este proyecto.")
        return 0
    for s in todas:
        print(s.describe())
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Context Manager")
    sub = ap.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="convierte un repositorio en proyecto gestionado")
    i.add_argument("path")
    i.add_argument("--name", help="nombre legible (por defecto, el de la carpeta)")
    i.add_argument("--force", action="store_true")
    i.add_argument("--dry-run", action="store_true")
    i.set_defaults(func=cmd_init)

    l = sub.add_parser("list", help="proyectos conocidos")
    l.set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="detalle de un proyecto")
    s.add_argument("project_id")
    s.set_defaults(func=cmd_show)

    se = sub.add_parser("session", help="sesion de desarrollo y justificacion")
    se.add_argument("accion",
                    choices=["start", "attach", "import", "end", "show", "list"])
    se.add_argument("--project", required=True)
    se.add_argument("--session", help="id concreto; por defecto, la abierta")
    se.add_argument("--goal", help="que se va a hacer en esta sesion")
    se.add_argument("--rationale", help="fichero con la explicacion del cambio")
    se.add_argument("--text", help="la explicacion en linea")
    se.add_argument("--transcript",
                    help="conversacion completa; solo se referencia para "
                         "auditoria, no entra en memoria")
    se.add_argument("--source", default="human",
                    help="claude, gpt, cursor, copilot, gemini, human, terminal...")
    se.add_argument("--provider", default="")
    se.add_argument("--model-externo", default="", dest="model_externo")
    se.add_argument("--force", action="store_true")
    se.add_argument("--file", help="import: transcripcion concreta")
    se.add_argument("--take", help="import: fragmentos a adjuntar, ej 1,3")
    se.add_argument("--limit", type=int, default=8, help="import: candidatos a mostrar")
    se.add_argument("--todo", action="store_true",
                    help="import: ignorar la ventana temporal de la sesion")
    se.set_defaults(func=cmd_session)

    stt = sub.add_parser("status", help="salud del ciclo de memoria")
    stt.add_argument("--project", required=True)
    stt.set_defaults(func=cmd_status)

    ia = sub.add_parser("ia", help="enciende, apaga o consulta la IA local")
    ia.add_argument("accion",
                    choices=["completo", "ahorro", "minimo",
                             "estado", "descargar", "reiniciar"])
    ia.add_argument("--project", help="aplica solo a este proyecto")
    ia.set_defaults(func=cmd_ia)

    h = sub.add_parser("hook", help="hook post-commit del proyecto")
    h.add_argument("accion", choices=["install", "uninstall", "status"])
    h.add_argument("--project", required=True)
    h.add_argument("--force", action="store_true",
                   help="reemplazar un hook existente que no gestionamos")
    h.set_defaults(func=cmd_hook)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
