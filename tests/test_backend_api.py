from __future__ import annotations

from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from apps.backend.autoreview_backend import main
from ng_drawing_qa.sample import generate_sample_project
from ng_drawing_qa.services.review import run_project_review
from ng_drawing_qa.storage.sqlite import AppIndex


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(main, "INDEX", AppIndex(tmp_path / "api_index.sqlite"))
    return TestClient(main.app)


def _create_project(client: TestClient, tmp_path: Path) -> dict:
    response = client.post("/projects", json={"name": "API Test Project", "root_path": str(tmp_path / "projects")})
    assert response.status_code == 200
    return response.json()


def _ingest_sample_files(client: TestClient, project_id: str, sample_dir: Path) -> None:
    roles = {
        "sample_natural_gas_drawing_set.pdf": "drawing_set",
        "drawing_index.csv": "drawing_index",
        "valve_list.csv": "valve_list",
        "line_list.csv": "line_list",
        "instrument_index.csv": "instrument_index",
        "equipment_list.csv": "equipment_list",
    }
    for name, role in roles.items():
        response = client.post(
            f"/projects/{project_id}/files/ingest",
            json={"paths": [str(sample_dir / name)], "role": role, "copy_into_project": True},
        )
        assert response.status_code == 200, response.text


def test_backend_api_project_file_run_finding_packet_and_training_flow(tmp_path: Path, monkeypatch):
    sample_dir = tmp_path / "sample"
    generate_sample_project(sample_dir)
    client = _client(tmp_path, monkeypatch)
    project = _create_project(client, tmp_path)

    missing = client.post(
        f"/projects/{project['id']}/files/ingest",
        json={"paths": [str(tmp_path / "missing.pdf")], "role": "drawing_set"},
    )
    assert missing.status_code == 400
    assert missing.json()["detail"]["message"].startswith("Selected file could not be found")

    _ingest_sample_files(client, project["id"], sample_dir)
    files = client.get(f"/projects/{project['id']}/files").json()
    assert len(files) == 6
    patch = client.patch(f"/projects/{project['id']}/files/{files[1]['id']}", json={"role": "drawing_register"})
    assert patch.status_code == 200
    patch_back = client.patch(f"/projects/{project['id']}/files/{files[1]['id']}", json={"role": "drawing_index"})
    assert patch_back.status_code == 200

    validation = client.post(f"/projects/{project['id']}/validate")
    assert validation.status_code == 200
    assert not [issue for issue in validation.json() if issue["level"] == "error"]

    def run_inline(project_record, run_record):
        run_project_review(project_record.database_path, project_record.id, run_record.id, run_record.profile)

    monkeypatch.setattr(main, "_spawn_review_worker", run_inline)
    created_run = client.post(f"/projects/{project['id']}/runs", json={"profile": "balanced"})
    assert created_run.status_code == 200, created_run.text
    run_id = created_run.json()["id"]
    run = client.get(f"/runs/{run_id}").json()
    assert run["run"]["status"] == "completed"

    findings = client.get(f"/runs/{run_id}/findings").json()
    assert findings
    accepted = client.patch(
        f"/findings/{findings[0]['id']}",
        json={"status": "Accepted", "edited_message": "API edited accepted wording."},
    )
    rejected = client.patch(f"/findings/{findings[1]['id']}", json={"status": "Rejected"})
    assert accepted.status_code == 200
    assert rejected.status_code == 200
    accepted_body = accepted.json()
    history_fields = {item["field_name"] for item in accepted_body["decision_history"]}
    assert {"status", "edited_message"} <= history_fields
    history = client.get(f"/findings/{findings[0]['id']}/history")
    assert history.status_code == 200
    assert {item["field_name"] for item in history.json()} == history_fields

    packet = client.post(
        f"/runs/{run_id}/export-packet",
        json={"packet_mode": "client_review", "finding_scope": "accepted_only", "packet_name": "api_packet.pdf"},
    )
    assert packet.status_code == 200, packet.text
    packet_body = packet.json()
    assert packet_body["settings"]["packet_mode"] == "client_review"
    assert packet_body["finding_count"] == 1
    packet_path = Path(packet_body["packet_path"])
    assert packet_path.exists()
    with fitz.open(packet_path) as doc:
        text = "\n".join(page.get_text() for page in doc)
        toc_titles = [item[1] for item in doc.get_toc()]
    assert "API edited accepted wording." in text
    assert findings[0]["issue_id"] in text
    assert findings[1]["issue_id"] not in text
    assert "Issue Index" in toc_titles
    assert "Marked-Up Drawing Set" in toc_titles

    second_run = client.post(f"/projects/{project['id']}/runs", json={"profile": "balanced"})
    assert second_run.status_code == 200
    second_run_id = second_run.json()["id"]
    comparison = client.get(f"/runs/{run_id}/compare/{second_run_id}")
    assert comparison.status_code == 200
    comparison_body = comparison.json()
    assert comparison_body["repeated_issue_ids"]
    assert not comparison_body["new_issue_ids"]
    assert not comparison_body["resolved_issue_ids"]

    exported = client.get(f"/projects/{project['id']}/profiles/export/balanced")
    assert exported.status_code == 200
    imported = client.post(f"/projects/{project['id']}/profiles/import", json={"path": exported.json()["path"]})
    assert imported.status_code == 200
    assert imported.json()["profile_name"] == "balanced"

    training = client.post(
        f"/projects/{project['id']}/training-sets",
        json={"name": "API Golden", "source_project_id": project["id"], "source_run_id": run_id, "notes": "api"},
    )
    assert training.status_code == 200
    training_id = training.json()["id"]
    label = client.post(
        f"/training-sets/{training_id}/labels",
        json={"finding_id": findings[0]["id"], "label": "false_positive", "notes": "api label"},
    )
    missed = client.post(
        f"/training-sets/{training_id}/missed-findings",
        json={"rule_id": "VALVE_TAG_RECONCILIATION", "sheet_number": "P-201", "expected_message": "Expected missed issue."},
    )
    regression = client.post(f"/training-sets/{training_id}/regression", json={"run_id": run_id})
    assert label.status_code == 200
    assert missed.status_code == 200
    assert regression.status_code == 200
    assert regression.json()["actual_count"] == len(findings)


def test_backend_api_open_project_returns_friendly_error(tmp_path: Path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.post("/projects/open", json={"root_path": str(tmp_path / "not_a_project")})
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["code"] == "MISSING_INPUT"
    assert "project.sqlite" in body["detail"]["message"]
