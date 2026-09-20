"""Hook de git post-commit hacia OBSERVED (DEC-027).

Alcance deliberadamente minimo. El hook **solo** registra lo que git ya sabe:

    git commit → post-commit → learn.py observe → pending/

Lo que el hook NO hace, y no debe hacer nunca:

    - llamar a Claude o GPT
    - ejecutar el modelo local (eso es `learn.py propose`, despues)
    - tocar la memoria canonica
    - verificar nada automaticamente
    - inventar relaciones
    - **bloquear el commit**

Lo ultimo es lo mas importante. La memoria es una herramienta auxiliar del
desarrollo; no puede convertirse en un punto unico de fallo del repositorio. Si
el Context Manager esta roto, el commit sigue adelante con un aviso.
"""

from __future__ import annotations

import stat
import sys
from pathlib import Path

HOOK_NAME = "post-commit"
MARCA = "# managed-by: ai-context-manager"

PLANTILLA = """#!/bin/sh
{marca}
# Hook post-commit del Context Manager (DEC-027).
#
# Registra el commit como OBSERVED en el area de espera. No ejecuta ningun
# modelo y NUNCA bloquea el commit: si algo falla, avisa y sale con 0.
#
# Para interpretar lo observado, despues y cuando convenga:
#   {python} {learn} propose --project {project} --all

CM_PYTHON="{python}"
CM_LEARN="{learn}"
CM_PROJECT="{project}"

if [ ! -x "$CM_PYTHON" ]; then
  echo "[Context Manager] WARNING: no encuentro el interprete. El commit no fue bloqueado."
  exit 0
fi

CM_OUT=$("$CM_PYTHON" "$CM_LEARN" observe --project "$CM_PROJECT" --commit HEAD 2>&1)
CM_RC=$?

if [ $CM_RC -eq 0 ]; then
  CM_TASK=$(echo "$CM_OUT" | grep -o 'TASK-[0-9][0-9]*' | head -1)
  if [ -n "$CM_TASK" ]; then
    echo "[Context Manager] OBSERVED creado: $CM_TASK"
  else
    echo "[Context Manager] sin cambios observables"
  fi
else
  echo "[Context Manager] WARNING: no se pudo registrar OBSERVED."
  echo "[Context Manager] El commit no fue bloqueado."
fi

exit 0
"""


def hook_path(repo: Path | str) -> Path:
    return Path(repo) / ".git" / "hooks" / HOOK_NAME


def render(repo: Path, project_id: str, cm_root: Path) -> str:
    """Genera el script con rutas absolutas resueltas."""
    python = Path(sys.executable)
    # En Windows, git ejecuta los hooks con sh: hay que darle rutas estilo POSIX.
    def posix(p: Path) -> str:
        s = str(p).replace("\\", "/")
        if len(s) > 1 and s[1] == ":":
            s = "/" + s[0].lower() + s[2:]
        return s

    return PLANTILLA.format(
        marca=MARCA,
        python=posix(python),
        learn=posix(cm_root / "learn.py"),
        project=project_id,
    )


def status(repo: Path | str) -> tuple[bool, bool]:
    """Devuelve (existe, lo gestiona el Context Manager)."""
    destino = hook_path(repo)
    if not destino.exists():
        return False, False
    return True, MARCA in destino.read_text(encoding="utf-8", errors="replace")


def install(repo: Path | str, project_id: str, cm_root: Path,
            *, force: bool = False) -> tuple[bool, str]:
    """Instala el hook. No pisa un hook ajeno sin permiso explicito."""
    repo = Path(repo)
    if not (repo / ".git").exists():
        return False, f"{repo} no es un repositorio git"

    destino = hook_path(repo)
    existe, gestionado = status(repo)
    if existe and not gestionado and not force:
        return False, (
            f"ya hay un {HOOK_NAME} que no gestiona el Context Manager. "
            "Revisalo y usa --force si quieres reemplazarlo."
        )

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(render(repo, project_id, cm_root), encoding="utf-8", newline="\n")
    destino.chmod(destino.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return True, str(destino)


def uninstall(repo: Path | str) -> tuple[bool, str]:
    destino = hook_path(repo)
    existe, gestionado = status(repo)
    if not existe:
        return False, "no hay hook instalado"
    if not gestionado:
        return False, "el hook existente no lo gestiona el Context Manager; no se toca"
    destino.unlink()
    return True, str(destino)
