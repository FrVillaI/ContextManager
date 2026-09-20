"""Extrae memoria del historial de git de un proyecto gestionado (DEC-016).

Todo lo que produce este script es deterministico. No interviene ningun modelo,
en cumplimiento de DEC-013:

- titulo y resumen  -> texto literal del mensaje de commit, escrito por el equipo
- archivos          -> `git show --name-only`
- modulos           -> derivados de las rutas por regla fija
- etiquetas         -> derivadas de rutas y de palabras del asunto
- relaciones        -> NINGUNA. No se infieren.

Procedencia: los commits `fix:` describen un problema y su correccion, asi que
producen registros `bug` en estado RESOLVED. El resto produce `change` en FACT.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acm.models import MemoryRecord, Provenance, Source, SourceKind  # noqa: E402
from acm.projects import Registry  # noqa: E402
from acm.store import MemoryStore  # noqa: E402

#: El repositorio se resuelve desde el registro de proyectos, no se escribe a
#: fuego: este script debe funcionar en cualquier instalacion.
REPO = Path(".")
PROJECT = ""
PROJECT_ID = ""

#: Commits ya representados por registros curados a mano, para no duplicarlos.
#: Se rellena con --skip.
YA_CURADOS: set[str] = set()

#: Rutas que no aportan conocimiento de ingenieria.
IGNORAR = re.compile(
    r"\.(png|jpe?g|gif|mp4|zip|rar|ico|webp|ttf|otf|pdf|docx|lock)$"
    r"|^(assets|img|Videos|Imagenes)/",
    re.IGNORECASE,
)

ES_FIX = re.compile(r"^\s*(fix|correc|bug|hotfix|arregl|solucion)", re.IGNORECASE)

#: Palabras del asunto que valen como etiqueta tematica.
#: Vocabulario generico de ingenieria. **Adaptalo al dominio de tu proyecto**:
#: cuanto mejor describan estas etiquetas de que trata cada commit, mejor
#: funcionara la recuperacion por tema. Un termino que no aparezca aqui no se
#: pierde —sigue estando en el titulo y el resumen—, solo deja de generar
#: etiqueta.
TEMAS = {
    # infraestructura y datos
    "migracion": "migraciones", "migraciones": "migraciones",
    "schema": "migraciones", "indice": "rendimiento", "query": "consultas",
    "consulta": "consultas", "transaccion": "transacciones",
    "politica": "permisos", "policies": "permisos", "rls": "permisos",
    "permiso": "permisos", "permisos": "permisos",
    # seguridad y acceso
    "auth": "auth", "login": "auth", "sesion": "auth", "token": "auth",
    "jwt": "auth", "cors": "seguridad", "seguridad": "seguridad",
    "admin": "admin",
    # comportamiento tipico
    "paginar": "paginacion", "paginacion": "paginacion", "paginado": "paginacion",
    "offline": "offline", "sincronizar": "sincronizacion",
    "sincronizacion": "sincronizacion", "cache": "cache",
    "notificacion": "notificaciones", "orden": "orden", "ordenar": "orden",
    "filtro": "filtros", "filtros": "filtros", "busqueda": "busqueda",
    # interfaz y entrega
    "ui": "ui", "visual": "ui", "color": "ui", "estilo": "ui",
    "build": "build", "compilar": "build", "deploy": "despliegue",
    "dependencias": "dependencias", "rendimiento": "rendimiento",
    "test": "tests", "tests": "tests",
}

#: Directorios de primer nivel que cuentan como modulo. Ampliala si tu
#: proyecto usa otra convencion.
RAICES = {
    "src", "app", "lib", "api", "backend", "server",
    "web", "frontend", "client", "mobile",
    "docs", "scripts", "tools", "tests", "design", "packages",
}


def git(*args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return out.stdout


def modulos_de(files: list[str]) -> list[str]:
    """Deriva modulos de las rutas, sin interpretacion semantica."""
    mods: list[str] = []
    for f in files:
        partes = f.replace("\\", "/").split("/")
        raiz = partes[0]
        if raiz not in RAICES:
            continue
        stem = Path(partes[-1]).stem
        mod = f"{raiz}/{stem}" if len(partes) > 1 and stem else raiz
        if mod not in mods:
            mods.append(mod)
    if not mods:
        mods = sorted({f.split("/")[0] for f in files if "/" in f})[:3]
    return mods[:8]


def etiquetas_de(subject: str, files: list[str]) -> list[str]:
    tags: set[str] = set()
    for palabra in re.split(r"[^a-záéíóúñ]+", subject.lower()):
        if palabra in TEMAS:
            tags.add(TEMAS[palabra])
    for f in files:
        raiz = f.split("/")[0]
        if raiz in RAICES:
            tags.add(raiz)
        if f.endswith(".sql"):
            tags.add("sql")
    return sorted(tags)[:6]


def cosechar(limite: int) -> list[MemoryRecord]:
    sep = "@@@COMMIT@@@"
    crudo = git("log", "--no-merges", f"--format={sep}%h%n%ad%n%s%n%b", "--date=short",
                "--name-only")
    registros: list[MemoryRecord] = []
    n_bug = n_chg = 0

    for bloque in crudo.split(sep):
        if not bloque.strip():
            continue
        lineas = bloque.strip("\n").split("\n")
        if len(lineas) < 3:
            continue
        sha, fecha, subject = lineas[0].strip(), lineas[1].strip(), lineas[2].strip()
        if sha in YA_CURADOS or not subject:
            continue

        cuerpo: list[str] = []
        archivos: list[str] = []
        for ln in lineas[3:]:
            ln = ln.strip()
            if not ln:
                continue
            if "/" in ln and not ln.endswith(".") and " " not in ln:
                archivos.append(ln)
            else:
                cuerpo.append(ln)

        archivos = [f for f in archivos if not IGNORAR.search(f)]
        if not archivos:
            continue

        es_bug = bool(ES_FIX.match(subject))
        if es_bug:
            n_bug += 1
            rid, tipo, proc = f"BUG-{100 + n_bug}", "bug", Provenance.RESOLVED
        else:
            n_chg += 1
            rid, tipo, proc = f"CHG-{100 + n_chg}", "change", Provenance.FACT

        resumen = " ".join(cuerpo)[:700]
        if not resumen:
            # Sin cuerpo de commit no hay explicacion: se marca como inferencia
            # porque el asunto solo dice que se toco, no que se supiera por que.
            proc = Provenance.INFERENCE
            resumen = f"Sin descripcion en el commit. Archivos tocados: {len(archivos)}."

        registros.append(MemoryRecord(
            id=rid, type=tipo, project_id=PROJECT_ID, project=PROJECT,
            title=subject[:150],
            provenance=proc,
            source=Source(kind=SourceKind.GIT_COMMIT, ref=sha, detail=subject[:100]),
            created_at=fecha,
            summary=resumen,
            modules=modulos_de(archivos),
            files=archivos[:12],
            tags=etiquetas_de(subject, archivos),
            body={"archivos_totales": len(archivos)},
        ))
        if len(registros) >= limite:
            break

    return registros


def main() -> int:
    global REPO, PROJECT, PROJECT_ID

    ap = argparse.ArgumentParser(
        description="Extrae memoria del historial de git de un proyecto gestionado")
    ap.add_argument("--project", required=True,
                    help="project_id registrado con 'context_manager.py init'")
    ap.add_argument("--repo", help="ruta del repositorio; por defecto, la registrada")
    ap.add_argument("--limit", type=int, default=95)
    ap.add_argument("--skip", default="",
                    help="shas ya representados a mano, separados por comas")
    ap.add_argument("--write", action="store_true", help="escribe en memory/")
    args = ap.parse_args()

    proyecto = Registry(ROOT).get(args.project)
    if not proyecto and not args.repo:
        print(f"no conozco el proyecto '{args.project}'. Registralo primero:",
              file=sys.stderr)
        print("  python context_manager.py init <ruta> --name <nombre>", file=sys.stderr)
        return 1

    PROJECT_ID = args.project
    PROJECT = proyecto.name if proyecto else args.project
    REPO = Path(args.repo or proyecto.repository)
    if args.skip:
        YA_CURADOS.update(x.strip() for x in args.skip.split(",") if x.strip())

    if not (REPO / ".git").exists():
        print(f"no encuentro un repositorio git en {REPO}", file=sys.stderr)
        return 1

    registros = cosechar(args.limit)
    bugs = sum(r.type == "bug" for r in registros)
    inferidos = sum(r.provenance == Provenance.INFERENCE for r in registros)
    print(f"cosechados {len(registros)} registros: {bugs} bugs, "
          f"{len(registros) - bugs} cambios")
    print(f"  sin descripcion en el commit (marcados INFERENCE): {inferidos}")

    if not args.write:
        print("\nmuestra:")
        for r in registros[:5]:
            print(f"  {r.id} [{r.provenance.value}] {r.title[:62]}")
            print(f"      modulos: {', '.join(r.modules[:4])}")
        print("\n(usa --write para guardarlos)")
        return 0

    store = MemoryStore(ROOT / "memory", PROJECT_ID)
    escritos = 0
    for r in registros:
        try:
            store.append(r)
            escritos += 1
        except ValueError:
            pass
    print(f"escritos {escritos}. Memoria total: {store.stats()}")
    problemas = store.check()
    print("integridad:", "OK" if not problemas else problemas[:5])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
