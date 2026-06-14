from __future__ import annotations

import csv
import json
from pathlib import Path

import fitz

from ng_drawing_qa.cli import main as cli_main
from ng_drawing_qa.sample import generate_sample_project
from ng_drawing_qa.schemas import FileRole, ProjectCreate
from ng_drawing_qa.services.files import ingest_file
from ng_drawing_qa.services.projects import create_project
from ng_drawing_qa.services.review import run_project_review
from ng_drawing_qa.storage.sqlite import AppIndex, ProjectRepository


def _issue_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _fingerprint_like(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row["rule_id"],
        row["sheet_number"],
        row["found_text"],
        row["subject"],
        row["context"][:180],
    )


def _seed_persisted_sample(tmp_path: Path, sample_dir: Path) -> tuple[ProjectRepository, str]:
    project = create_project(ProjectCreate(name="Persisted Consistency", root_path=tmp_path / "persisted"), AppIndex(tmp_path / "app.sqlite"))
    repo = ProjectRepository(project.database_path)
    roles = {
        "sample_natural_gas_drawing_set.pdf": FileRole.DRAWING_SET,
        "drawing_index.csv": FileRole.DRAWING_INDEX,
        "valve_list.csv": FileRole.VALVE_LIST,
        "line_list.csv": FileRole.LINE_LIST,
        "instrument_index.csv": FileRole.INSTRUMENT_INDEX,
        "equipment_list.csv": FileRole.EQUIPMENT_LIST,
    }
    for name, role in roles.items():
        ingest_file(repo, project.id, project.root_path, sample_dir / name, role=role)
    run = repo.create_run(project.id, "balanced", project.root_path / "outputs" / "runs" / "consistency")
    run_project_review(project.database_path, project.id, run.id, "balanced")
    return repo, run.id


def test_cli_direct_pdf_uses_shared_persisted_review_workflow(tmp_path: Path):
    sample_dir = tmp_path / "sample"
    generate_sample_project(sample_dir)
    cli_out_root = tmp_path / "cli_outputs"

    exit_code = cli_main([
        str(sample_dir / "sample_natural_gas_drawing_set.pdf"),
        "--out-dir", str(cli_out_root),
        "--drawing-index", str(sample_dir / "drawing_index.csv"),
        "--valve-list", str(sample_dir / "valve_list.csv"),
        "--line-list", str(sample_dir / "line_list.csv"),
        "--instrument-index", str(sample_dir / "instrument_index.csv"),
        "--equipment-list", str(sample_dir / "equipment_list.csv"),
    ])

    assert exit_code == 0
    cli_run_dirs = list(cli_out_root.glob("sample_natural_gas_drawing_set_ngqa_*"))
    assert len(cli_run_dirs) == 1
    cli_run_dir = cli_run_dirs[0]
    assert (cli_run_dir / "project.sqlite").exists()
    assert (cli_run_dir / "issue_log.csv").exists()
    assert (cli_run_dir / "sample_natural_gas_drawing_set_reviewed_marked_up.pdf").exists()
    assert (cli_run_dir / "packets" / "single_review_packet.pdf").exists()

    persisted_repo, persisted_run_id = _seed_persisted_sample(tmp_path, sample_dir)
    persisted_findings = persisted_repo.list_findings(persisted_run_id)
    cli_rows = _issue_rows(cli_run_dir / "issue_log.csv")

    assert len(cli_rows) == len(persisted_findings)
    assert [row["issue_id"] for row in cli_rows] == [finding.issue_id for finding in persisted_findings]
    assert {_fingerprint_like(row) for row in cli_rows} == {
        (
            finding.rule_id,
            finding.sheet_number,
            finding.found_text,
            finding.subject,
            finding.context[:180],
        )
        for finding in persisted_findings
    }

    manifest = json.loads((cli_run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"]
    assert manifest["project_id"]
    assert manifest["input_files"]
    assert manifest["packet_finding_count"] == len(cli_rows)
    assert manifest["output_packet_path"].endswith("single_review_packet.pdf")
    assert manifest["finding_status_counts"]["Draft"] == len(cli_rows)

    with fitz.open(cli_run_dir / "packets" / "single_review_packet.pdf") as packet:
        text = "\n".join(page.get_text() for page in packet)
        toc_titles = [item[1] for item in packet.get_toc()]
    assert "Issue Index" in text
    assert "Marked-Up Drawing Set" in text
    assert "Rendered Reference Inputs" in text
    assert cli_rows[0]["issue_id"] in text
    assert "Issue Index" in toc_titles
    assert "Marked-Up Drawing Set" in toc_titles


def test_cli_dry_run_uses_shared_workflow_without_packet_export(tmp_path: Path):
    sample_dir = tmp_path / "sample"
    generate_sample_project(sample_dir)
    cli_out_root = tmp_path / "cli_dry_run"

    exit_code = cli_main([
        str(sample_dir / "sample_natural_gas_drawing_set.pdf"),
        "--out-dir", str(cli_out_root),
        "--dry-run",
    ])

    assert exit_code == 0
    cli_run_dir = next(cli_out_root.glob("sample_natural_gas_drawing_set_ngqa_*"))
    assert (cli_run_dir / "project.sqlite").exists()
    assert (cli_run_dir / "issue_log.csv").exists()
    assert not (cli_run_dir / "packets" / "single_review_packet.pdf").exists()
