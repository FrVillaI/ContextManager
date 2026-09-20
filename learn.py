"""Ciclo post-tarea: observar el trabajo y convertirlo en memoria.

    python learn.py observe --project P [--commit REF]
                            [--rationale FICHERO] [--provider anthropic]
                            [--terminal F] [--tests F] [--pr F] [--note "texto"]
    python learn.py pending --project P
    python learn.py show    --project P TASK-001
    python learn.py verify  --project P TASK-001        (revision interactiva)
    python learn.py verify  --project P TASK-001 --summary "..." --as CHG-200
    python learn.py reject  --project P TASK-001
    python learn.py stats   --project P

`observe` nunca escribe en la memoria canonica: deja un evento de tarea en
`memory/<project_id>/pending/`. Solo `verify` promociona, y solo una persona
ejecuta `verify` (DEC-023).

La justificacion de la IA externa es evidencia de primera clase y mejora mucho la
propuesta, pero no promociona nada por si sola (DEC-025).

La salida del modelo nunca es memoria canonica, aunque este respaldada por
evidencia correcta: toda propuesta puede aceptarse, editarse o rechazarse, y la
version editada conserva el vinculo con la original (DEC-026).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from acm.events import (  # noqa: E402
    Evidence, EvidenceKind, EvidenceOrigin, TaskEvent, drop_event, load_event,
    load_events, next_task_id, save_event,
)
from acm.observe import (  # noqa: E402
    attach_proposal, build_event, extract, observe_commit, observe_worktree, propose,
)
from acm import sessions as ss  # noqa: E402
from acm.projects import Registry  # noqa: E402
from acm.review import (  # noqa: E402
    EDITABLES, Draft, build_verified, corrected_fields, correction_stats,
)
from acm.store import MemoryStore  # noqa: E402

MEMORY = ROOT / "memory"

#: Cada bandera declara su tipo de evidencia y su origen. Añadir una fuente
#: nueva es añadir una fila aqui, no rediseñar el esquema (DEC-025).
FUENTES = {
    "rationale": (EvidenceKind.RATIONALE, EvidenceOrigin.EXTERNAL_LLM),
    "terminal": (EvidenceKind.TERMINAL, EvidenceOrigin.TOOL),
    "tests": (EvidenceKind.TEST_RESULTS, EvidenceOrigin.CI),
    "pr": (EvidenceKind.PULL_REQUEST, EvidenceOrigin.USER),
}

CAMPOS_EDITABLES = ("title", "summary", "type", "tags", "modules", "related")


# --------------------------------------------------------------------------
# observe
# --------------------------------------------------------------------------

def recoger_evidencia(args: argparse.Namespace) -> list[Evidence]:
    fuera: list[Evidence] = []
    for bandera, (kind, origin) in FUENTES.items():
        ruta = getattr(args, bandera, None)
        if not ruta:
            continue
        archivo = Path(ruta)
        if not archivo.exists():
            print(f"aviso: no encuentro {archivo}, se ignora", file=sys.stderr)
            continue
        fuera.append(Evidence(
            kind=kind, origin=origin,
            content=archivo.read_text(encoding="utf-8", errors="replace"),
            provider=args.provider if kind == EvidenceKind.RATIONALE else "",
            model=args.model_externo if kind == EvidenceKind.RATIONALE else "",
            meta={"archivo": archivo.name},
        ))
    if args.note:
        fuera.append(Evidence(
            kind=EvidenceKind.USER_NOTE, origin=EvidenceOrigin.USER, content=args.note,
        ))
    return fuera


def cmd_observe(args: argparse.Namespace) -> int:
    proyecto = Registry(ROOT).get(args.project)
    if not proyecto:
        print(f"no conozco el proyecto '{args.project}'", file=sys.stderr)
        return 1

    repo = Path(proyecto.repository)
    memoria = list(MemoryStore(MEMORY, args.project).all())

    obs = observe_commit(repo, args.commit) if args.commit else observe_worktree(repo)
    print(f"[OBSERVED ] {obs.describe()}")
    if obs.empty:
        print("            no hay cambios que observar.")
        return 0

    externas = recoger_evidencia(args)

    # Si hay una sesion de desarrollo abierta, su justificacion se incorpora
    # sola (DEC-029). El commit queda anotado en la sesion, y la relacion se
    # declara como TEMPORAL: el rationale existia antes, no se afirma que
    # causara el cambio.
    sesion = None if args.sin_sesion else ss.open_session(repo)
    if sesion is not None:
        externas.extend(sesion.evidence())
        if obs.ref != "worktree":
            externas.append(sesion.temporal_note(obs.ref))
            if obs.ref not in sesion.commits:
                sesion.commits.append(obs.ref)
                ss.save(sesion, repo)

    ext = extract(obs, memoria)
    evento = build_event(
        obs, ext,
        task_id=next_task_id(MEMORY, args.project),
        project_id=args.project, project=proyecto.name,
        extra_evidence=externas,
    )
    if sesion is not None:
        evento.session_id = sesion.session_id
        print(f"[SESION   ] {sesion.session_id}, "
              f"{len(sesion.rationale)} fragmento(s) de justificacion")
    print(f"            evidencia: {', '.join(e.cite() for e in evento.evidence)}")
    print(f"[EXTRACTED] {ext.describe()[:108]}")

    explican = evento.explanation_sources
    print(f"            explican el trabajo: {', '.join(explican) or 'NINGUNA'}")

    # El modelo NO se ejecuta aqui salvo que se pida (DEC-027). Separar observar
    # de proponer es lo que permite que un hook de git no cueste nada: registrar
    # lo que paso es instantaneo, interpretarlo puede esperar.
    if args.propose:
        prop = propose(evento, model=args.model)
        if prop.error:
            print(f"[PROPOSED ] el modelo local fallo: {prop.error}", file=sys.stderr)
        else:
            print(f"[PROPOSED ] {prop.type}: {prop.title[:66]}")
        evento = attach_proposal(evento, prop)

    ruta = save_event(evento, MEMORY)
    print(f"{chr(10)}[PENDIENTE] {evento.task_id} en {ruta.parent.name}/")
    print("            NO esta en la memoria canonica ni aparece en ninguna")
    print("            recuperacion hasta que alguien lo verifique.")
    if not args.propose:
        print(f"            interpreta el cambio con: learn.py propose "
              f"--project {args.project} {evento.task_id}")
    if not explican:
        print(f"{chr(10)}  Aviso: ninguna evidencia explica el trabajo. La propuesta se")
        print("  basa solo en nombres de archivo. Revisala con cuidado.")
    return 0


def cmd_propose(args: argparse.Namespace) -> int:
    """Segunda fase: interpretar con el modelo local lo ya observado (DEC-027).

    Se ejecuta cuando conviene, no cuando se hace commit. Admite añadir evidencia
    que no existia en el momento del commit, como la justificacion de la IA que
    hizo el trabajo.
    """
    objetivos = (
        load_events(MEMORY, args.project) if args.all
        else [e for e in [load_event(MEMORY, args.project, args.task_id)] if e]
    )
    if not objetivos:
        print("nada que interpretar.", file=sys.stderr)
        return 1

    externas = recoger_evidencia(args)
    salida = 0
    for evento in objetivos:
        if evento.proposal and not args.force:
            print(f"{evento.task_id}: ya tiene propuesta, usa --force para rehacerla")
            continue
        if externas:
            evento.evidence.extend(externas)
        prop = propose(evento, model=args.model)
        if prop.error:
            print(f"{evento.task_id}: el modelo local fallo: {prop.error}", file=sys.stderr)
            salida = 1
            continue
        save_event(attach_proposal(evento, prop), MEMORY)
        print(f"{evento.task_id}: {prop.type} - {prop.title[:60]}")
        print(f"           apoyado en: "
              f"{', '.join(evento.explanation_sources) or 'solo rutas de archivo'}")
    return salida


# --------------------------------------------------------------------------
# pending / show
# --------------------------------------------------------------------------

def cmd_pending(args: argparse.Namespace) -> int:
    eventos = load_events(MEMORY, args.project)
    if not eventos:
        print("no hay eventos pendientes.")
        return 0
    for e in eventos:
        print()
        print(e.summary_line())
        print(f"  {e.proposal.get('title', '(sin propuesta)')[:74]}")
        print(f"  explican: {', '.join(e.explanation_sources) or 'ninguna'}")
    print()
    print(f"{len(eventos)} pendientes. Detalle: learn.py show --project "
          f"{args.project} <TASK-ID>")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    evento = load_event(MEMORY, args.project, args.task_id)
    if not evento:
        print(f"no encuentro {args.task_id}", file=sys.stderr)
        return 1

    print("=" * 72)
    print(f"{evento.task_id}   proyecto {evento.project_id}   "
          f"commit {evento.commit or '(worktree)'}")
    print("=" * 72)

    print()
    print("EVIDENCIA")
    for e in evento.evidence:
        marca = "explica" if e.explains else "no explica"
        print(f"  [{marca:<10}] {e.cite()}")
        if e.content.strip():
            print(f"               {e.content.strip().splitlines()[0][:64]}")

    print()
    print("DERIVADO POR REGLA FIJA (sin modelo)")
    print(f"  archivos  : {len(evento.files)}")
    print(f"  modulos   : {', '.join(evento.modules) or '-'}")
    for rel in evento.related[:4]:
        print(f"  relacion  : {rel['id']} - {rel['evidencia'][:54]}")

    print()
    print("INFERIDO POR EL MODELO LOCAL")
    for inf in evento.inferences:
        print(f"  {inf.kind:<20} {inf.value[:52]}")
    if evento.inferences:
        print(f"  (apoyado en: {evento.inferences[0].basis} · por {evento.inferences[0].by})")

    print()
    print(f"Procedencia si se verificara: "
          f"{'PROPOSAL' if evento.has_explanation else 'INFERENCE'}")
    return 0


# --------------------------------------------------------------------------
# verify — revision editable (DEC-026)
# --------------------------------------------------------------------------

def _render(draft: Draft, event: TaskEvent) -> None:
    print()
    print("=" * 70)
    print("PROPUESTA".center(70))
    print("=" * 70)
    print()
    print(f"Tipo     : {draft.type}")
    print(f"Titulo   : {draft.title}")
    print()
    print(f"Resumen  : {draft.summary}")
    print()
    print(f"Etiquetas: {', '.join(draft.tags) or '-'}")
    print(f"Modulos  : {', '.join(draft.modules) or '-'}")
    print(f"Relacion : {', '.join(draft.related) or '-'}")
    print()
    print(f"Origen   : {event.commit or 'worktree'}")
    print(f"           propuesto por {event.proposal.get('model', '?')}")
    print(f"           evidencia que explica: "
          f"{', '.join(event.explanation_sources) or 'NINGUNA'}")
    print("-" * 70)


def _aplicar_banderas(draft: Draft, args: argparse.Namespace) -> Draft:
    """Edicion no interactiva. No vuelve a pasar por el modelo (DEC-026)."""
    if args.title:
        draft.title = args.title
    if args.summary:
        draft.summary = args.summary
    if args.type:
        draft.type = args.type
    for campo, valor in (("tags", args.tags), ("modules", args.modules),
                         ("related", args.related)):
        if valor is not None:
            setattr(draft, campo, [x.strip() for x in valor.split(",") if x.strip()])
    return draft


def _editar_interactivo(draft: Draft) -> Draft:
    """Edicion campo a campo. Lo que escribe la persona es lo que queda."""
    opciones = {"1": "title", "2": "summary", "3": "tags",
                "4": "modules", "5": "related", "6": "type"}
    while True:
        print()
        print("  1. Titulo     2. Resumen     3. Etiquetas")
        print("  4. Modulos    5. Relaciones  6. Tipo")
        print("  0. Terminar de editar")
        try:
            opcion = input("  Que quieres modificar? ").strip()
        except EOFError:
            return draft
        if opcion in ("0", "", "q"):
            return draft
        campo = opciones.get(opcion)
        if not campo:
            print("  opcion no valida")
            continue
        actual = getattr(draft, campo)
        actual_txt = ", ".join(actual) if isinstance(actual, list) else actual
        print()
        print(f"  actual: {actual_txt}")
        try:
            nuevo = input("  nuevo : ").strip()
        except EOFError:
            return draft
        if not nuevo:
            print("  sin cambios")
            continue
        if isinstance(actual, list):
            setattr(draft, campo, [x.strip() for x in nuevo.split(",") if x.strip()])
        else:
            setattr(draft, campo, nuevo)


def cmd_verify(args: argparse.Namespace) -> int:
    evento = load_event(MEMORY, args.project, args.task_id)
    if not evento:
        print(f"no encuentro {args.task_id}", file=sys.stderr)
        return 1

    original = Draft.from_event(evento)
    draft = Draft.from_event(evento)
    tiene_banderas = any(getattr(args, n) is not None for n in CAMPOS_EDITABLES)

    if tiene_banderas:
        draft = _aplicar_banderas(draft, args)
    elif not args.accept:
        _render(draft, evento)
        while True:
            try:
                accion = input("  [A] Aceptar  [E] Editar  [R] Rechazar > ").strip().lower()
            except EOFError:
                accion = "a"
            if accion in ("a", "aceptar", ""):
                break
            if accion in ("r", "rechazar"):
                drop_event(MEMORY, args.project, args.task_id)
                print(f"{args.task_id} descartado. No entra en la memoria.")
                return 0
            if accion in ("e", "editar"):
                draft = _editar_interactivo(draft)
                _render(draft, evento)
                continue
            print("  responde A, E o R")

    tocados = corrected_fields(original, draft)
    store = MemoryStore(MEMORY, args.project)
    nuevo_id = args.as_id or _siguiente_id(store, draft.type)

    registro = build_verified(evento, original, draft, nuevo_id)
    store.append(registro)
    drop_event(MEMORY, args.project, args.task_id)

    print()
    print(f"{evento.task_id} -> {nuevo_id} promovido "
          f"({registro.stage.value} / {registro.provenance.value})")
    if tocados:
        print(f"  campos corregidos por la persona: {', '.join(tocados)}")
        print("  la propuesta original queda guardada junto a la version verificada")
    else:
        print("  aceptado tal cual, sin correcciones")
    return 0


def cmd_reject(args: argparse.Namespace) -> int:
    if not drop_event(MEMORY, args.project, args.task_id):
        print(f"no encuentro {args.task_id}", file=sys.stderr)
        return 1
    print(f"{args.task_id} descartado. No entra en la memoria.")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Cuanto corrige la persona al modelo, en conjunto y por campo (DEC-026)."""
    store = MemoryStore(MEMORY, args.project)
    stats = correction_stats(list(store.all()))
    if not stats.verificadas:
        print("todavia no hay propuestas verificadas por el flujo de revision.")
        return 0
    print(f"propuestas verificadas     {stats.verificadas}")
    print(f"Proposal Correction Rate   {stats.proposal_correction_rate:.0%}  "
          f"({stats.con_correccion} de {stats.verificadas})")
    print()
    print("Field Correction Rate")
    for campo in EDITABLES:
        n = stats.por_campo.get(campo, 0)
        print(f"  {campo:<10} {stats.field_rate(campo):>5.0%}  {'#' * n}")
    return 0


def _siguiente_id(store: MemoryStore, tipo: str) -> str:
    prefijo = {"bug": "BUG", "solution": "SOL", "decision": "ADR",
               "constraint": "CONSTRAINT", "change": "CHG"}.get(tipo, "CHG")
    usados = [
        int(r.id.split("-")[1]) for r in store.read(tipo)
        if r.id.startswith(prefijo + "-") and r.id.split("-")[1].isdigit()
    ]
    return f"{prefijo}-{max(usados, default=200) + 1}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Ciclo post-tarea")
    sub = ap.add_subparsers(dest="cmd", required=True)

    o = sub.add_parser("observe", help="observa el trabajo y propone memoria")
    o.add_argument("--project", required=True)
    o.add_argument("--commit", help="sha o ref; por defecto, el trabajo sin confirmar")
    o.add_argument("--model", default="llama3.2:3b", help="modelo local que propone")
    o.add_argument("--rationale", help="explicacion de quien hizo el trabajo")
    o.add_argument("--provider", default="anthropic")
    o.add_argument("--model-externo", default="claude", dest="model_externo")
    o.add_argument("--terminal", help="salida de terminal relevante")
    o.add_argument("--tests", help="resultado de los tests")
    o.add_argument("--pr", help="descripcion del pull request")
    o.add_argument("--note", help="nota del desarrollador")
    o.add_argument("--sin-sesion", action="store_true", dest="sin_sesion",
                   help="ignorar la sesion de desarrollo abierta")
    o.add_argument("--propose", action="store_true",
                   help="interpretar ya con el modelo local (por defecto no, "
                        "para que un hook de git sea instantaneo)")
    o.set_defaults(func=cmd_observe)

    pr = sub.add_parser("propose", help="interpreta con el modelo local lo observado")
    pr.add_argument("--project", required=True)
    pr.add_argument("task_id", nargs="?")
    pr.add_argument("--all", action="store_true", help="todos los pendientes sin propuesta")
    pr.add_argument("--force", action="store_true", help="rehacer una propuesta existente")
    pr.add_argument("--model", default="llama3.2:3b")
    pr.add_argument("--rationale", help="explicacion de quien hizo el trabajo")
    pr.add_argument("--provider", default="anthropic")
    pr.add_argument("--model-externo", default="claude", dest="model_externo")
    pr.add_argument("--terminal")
    pr.add_argument("--tests")
    pr.add_argument("--pr", dest="pr")
    pr.add_argument("--note")
    pr.add_argument("--sin-sesion", action="store_true", dest="sin_sesion")
    pr.set_defaults(func=cmd_propose)

    p = sub.add_parser("pending", help="eventos a la espera de verificacion")
    p.add_argument("--project", required=True)
    p.set_defaults(func=cmd_pending)

    sh = sub.add_parser("show", help="detalle de un evento")
    sh.add_argument("--project", required=True)
    sh.add_argument("task_id")
    sh.set_defaults(func=cmd_show)

    v = sub.add_parser("verify", help="revisa y promociona un evento")
    v.add_argument("--project", required=True)
    v.add_argument("task_id")
    v.add_argument("--as", dest="as_id")
    v.add_argument("--accept", action="store_true", help="aceptar sin revisar")
    v.add_argument("--title", help="corrige el titulo")
    v.add_argument("--summary", help="corrige el resumen")
    v.add_argument("--type", help="corrige el tipo")
    v.add_argument("--tags", help="lista separada por comas")
    v.add_argument("--modules", help="lista separada por comas")
    v.add_argument("--related", help="lista separada por comas")
    v.set_defaults(func=cmd_verify)

    r = sub.add_parser("reject", help="descarta un evento")
    r.add_argument("--project", required=True)
    r.add_argument("task_id")
    r.set_defaults(func=cmd_reject)

    st = sub.add_parser("stats", help="metricas de correccion de propuestas")
    st.add_argument("--project", required=True)
    st.set_defaults(func=cmd_stats)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
