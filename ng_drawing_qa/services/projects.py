from __future__ import annotations

import re
from pathlib import Path

from ..schemas import ProjectCreate, ProjectRecord
from ..storage.sqlite import AppIndex, ProjectRepository, new_id, now_iso


PROJECT_DIRS = [
    "inputs",
    "inputs/drawings",
    "inputs/references",
    "outputs",
    "outputs/runs",
    "packets",
    "logs",
    "debug",
    "profiles",
    "training",
]


def safe_project_folder(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_. -]+", "_", name).strip().rstrip(".")
    return cleaned or "AutoReview Project"


def ensure_project_structure(root_path: Path) -> None:
    root_path.mkdir(parents=True, exist_ok=True)
    for rel in PROJECT_DIRS:
        (root_path / rel).mkdir(parents=True, exist_ok=True)


def create_project(request: ProjectCreate, app_index: AppIndex | None = None) -> ProjectRecord:
    root = Path(request.root_path)
    if root.suffix:
        root = root.parent / safe_project_folder(root.stem)
    else:
        root = root / safe_project_folder(request.name) if root.name.lower() != safe_project_folder(request.name).lower() else root
    ensure_project_structure(root)
    db_path = root / "project.sqlite"
    now = now_iso()
    project = ProjectRecord(
        id=new_id("proj"),
        name=request.name,
        root_path=root,
        database_path=db_path,
        created_at=now,
        updated_at=now,
    )
    repo = ProjectRepository(db_path)
    repo.save_project(project)
    (app_index or AppIndex()).upsert_project(project)
    return project


def open_project(root_path: Path, app_index: AppIndex | None = None) -> ProjectRecord:
    root = Path(root_path)
    db_path = root / "project.sqlite"
    repo = ProjectRepository(db_path)
    project = repo.get_project()
    if project is None:
        raise FileNotFoundError(f"No AutoReview project.sqlite found in {root}")
    (app_index or AppIndex()).upsert_project(project)
    return project


def repository_for_project(project: ProjectRecord) -> ProjectRepository:
    return ProjectRepository(project.database_path)
