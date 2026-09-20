"""Registro de proyectos (DEC-018).

El Context Manager gestiona **varios** proyectos. el proyecto piloto es uno de ellos,
no una dependencia del sistema. Cada proyecto tiene su propio espacio de memoria
y nunca ve la memoria de otro.

Dos artefactos, con papeles distintos:

- `projects.json` en la raiz del Context Manager: que proyectos conoce.
- `.context/project.json` dentro de cada repositorio: identifica ese repositorio
  como proyecto gestionado. **No contiene memoria**, solo identidad y
  configuracion; la memoria vive en el espacio del Context Manager y, indexada,
  en el grafo.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

CONTEXT_DIR = ".context"
PROJECT_FILE = "project.json"
REGISTRY_FILE = "projects.json"
CONTRACT_VERSION = "1.0"


def slugify(name: str) -> str:
    """Convierte un nombre en identificador estable."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return re.sub(r"-+", "-", s) or "proyecto"


@dataclass
class Project:
    project_id: str
    name: str
    repository: str
    memory_namespace: str = ""
    stack: list[str] = field(default_factory=list)
    directories: list[str] = field(default_factory=list)
    created_at: str = ""
    context_manager_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        self.memory_namespace = self.memory_namespace or self.project_id
        self.created_at = self.created_at or date.today().isoformat()

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "repository": self.repository,
            "memory_namespace": self.memory_namespace,
            "context_manager_version": self.context_manager_version,
            "stack": self.stack,
            "directories": self.directories,
            "created_at": self.created_at,
        }


class Registry:
    """Los proyectos que conoce esta instalacion del Context Manager."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.path = self.root / REGISTRY_FILE

    def load(self) -> dict[str, Project]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return {pid: Project(**p) for pid, p in data.get("projects", {}).items()}

    def save(self, projects: dict[str, Project]) -> None:
        payload = {
            "context_manager_version": CONTRACT_VERSION,
            "projects": {pid: p.to_dict() for pid, p in sorted(projects.items())},
        }
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def add(self, project: Project) -> None:
        projects = self.load()
        projects[project.project_id] = project
        self.save(projects)

    def get(self, project_id: str) -> Project | None:
        return self.load().get(project_id)

    def ids(self) -> list[str]:
        return sorted(self.load())


# --------------------------------------------------------------------------
# Inspeccion de un repositorio
# --------------------------------------------------------------------------

#: Que archivo delata que tecnologia. Es **evidencia observada**, no inferencia
#: del modelo: el archivo existe o no existe.
HUELLAS: dict[str, str] = {
    "package.json": "Node/JavaScript",
    "tsconfig.json": "TypeScript",
    "requirements.txt": "Python",
    "pyproject.toml": "Python",
    "go.mod": "Go",
    "Cargo.toml": "Rust",
    "pom.xml": "Java/Maven",
    "build.gradle": "Java/Gradle",
    "Gemfile": "Ruby",
    "composer.json": "PHP",
    "docker-compose.yml": "Docker",
    "Dockerfile": "Docker",
    "app.json": "Expo",
    "next.config.js": "Next.js",
    "angular.json": "Angular",
}

IGNORAR_DIRS = {
    ".git", ".venv", "node_modules", "__pycache__", "dist", "build",
    ".next", "bin", "obj", ".vscode", ".idea", "venv", ".context",
}


def inspect(repo: Path) -> tuple[list[str], list[str], bool]:
    """Observa un repositorio. Devuelve (stack, directorios, tiene_git).

    Todo lo que sale de aqui es verificable mirando el disco. Ningun modelo
    interviene, en cumplimiento de DEC-013.
    """
    repo = Path(repo)
    stack: list[str] = []
    for huella, tecnologia in HUELLAS.items():
        if list(repo.glob(huella)) or list(repo.glob(f"*/{huella}")):
            if tecnologia not in stack:
                stack.append(tecnologia)
    if list(repo.glob("*.csproj")) or list(repo.glob("*/*.csproj")) or list(repo.glob("*.sln")):
        stack.append(".NET")

    directorios = sorted(
        d.name for d in repo.iterdir()
        if d.is_dir() and d.name not in IGNORAR_DIRS and not d.name.startswith(".")
    )
    return stack, directorios[:20], (repo / ".git").exists()


def git_remote(repo: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), "remote", "get-url", "origin"],
        capture_output=True, text=True,
    )
    return out.stdout.strip()


def write_context_file(repo: Path, project: Project) -> Path:
    """Escribe `.context/project.json` dentro del repositorio gestionado."""
    carpeta = Path(repo) / CONTEXT_DIR
    carpeta.mkdir(exist_ok=True)
    destino = carpeta / PROJECT_FILE
    destino.write_text(
        json.dumps(
            {
                "project_id": project.project_id,
                "repository": project.repository,
                "context_manager_version": project.context_manager_version,
                "memory_namespace": project.memory_namespace,
            },
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return destino


def read_context_file(repo: Path) -> dict | None:
    destino = Path(repo) / CONTEXT_DIR / PROJECT_FILE
    if not destino.exists():
        return None
    return json.loads(destino.read_text(encoding="utf-8"))
