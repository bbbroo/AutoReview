from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from ..config import load_config
from ..errors import MissingInputError, ValidationError
from ..storage.sqlite import ProjectRepository, now_iso


def export_review_profile(project_db_path: Path, profile_name: str) -> dict[str, Any]:
    repo = ProjectRepository(project_db_path)
    project = repo.get_project()
    if project is None:
        raise MissingInputError("Project not found for profile export.")
    config = load_config(profile=profile_name)
    profiles = config.get("profiles", {})
    if profile_name not in profiles:
        raise ValidationError(f"Profile not found: {profile_name}")
    out_dir = project.root_path / "profiles"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{profile_name}.profile.json"
    payload = {
        "profile_name": profile_name,
        "exported_at": now_iso(),
        "profile": profiles[profile_name],
        "rules": config.get("rules", {}),
        "regex": config.get("regex", {}),
        "title_block": config.get("title_block", {}),
        "review": config.get("review", {}),
        "outputs": config.get("outputs", {}),
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"profile_name": profile_name, "path": str(out_path), "profile": payload}


def import_review_profile(project_db_path: Path, source_path: Path) -> dict[str, Any]:
    repo = ProjectRepository(project_db_path)
    project = repo.get_project()
    if project is None:
        raise MissingInputError("Project not found for profile import.")
    source_path = Path(source_path)
    if not source_path.exists():
        raise MissingInputError(f"Profile file not found: {source_path}")
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValidationError(f"Profile file is not valid JSON: {exc}") from exc
    profile_name = str(payload.get("profile_name") or source_path.stem.replace(".profile", ""))
    target = project.root_path / "profiles" / f"{profile_name}.profile.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if source_path.resolve() != target.resolve():
        shutil.copy2(source_path, target)
    return {"profile_name": profile_name, "path": str(target), "profile": payload}
