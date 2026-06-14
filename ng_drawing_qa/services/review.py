from __future__ import annotations

from collections import Counter
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import fitz

from .. import __version__ as ENGINE_VERSION
from ..config import load_config
from ..errors import MissingInputError, ReviewRunError, ValidationError
from ..issue_builder import IssueBuilder
from ..models import Issue, RunManifest
from ..pdf_utils import extract_page_info, extract_word_hits, export_extracted_text, export_words_csv
from ..reference import load_aliases, load_ignore_patterns, load_reference_records, validate_reference_records
from ..reports import write_all_reports, write_manifest
from ..rules.base import RuleContext
from ..rules.core_rules import run_all_rules
from ..rules.registry import RULE_METADATA_BY_ID
from ..schemas import FileRecord, FileRole, FindingEvidence, FindingRecord, FindingStatus, RunStatus, Severity
from ..storage.sqlite import ProjectRepository, now_iso, new_id
from .reference_mappings import apply_saved_reference_mappings
from .validation import validate_project_inputs


REFERENCE_ROLE_TO_CONFIG_KEY: dict[FileRole, str] = {
    FileRole.DRAWING_INDEX: "drawing_index",
    FileRole.VALVE_LIST: "valve_list",
    FileRole.LINE_LIST: "line_list",
    FileRole.INSTRUMENT_INDEX: "instrument_index",
    FileRole.EQUIPMENT_LIST: "equipment_list",
}

APP_VERSION = "0.3.0"


def _severity(value: str) -> Severity:
    try:
        return Severity(value)
    except ValueError:
        return Severity.INFO


def finding_fingerprint(issue: Issue) -> str:
    parts = [
        issue.rule_id,
        issue.sheet_number.upper().strip(),
        issue.found_text.upper().strip(),
        str(issue.page_number),
        issue.subject.upper().strip(),
        issue.context.upper().strip()[:180],
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def _next_issue_number(repo: ProjectRepository, project_id: str) -> int:
    first = repo.next_issue_id(project_id)
    try:
        return int(first.split("-", 1)[1])
    except Exception:
        return 1


def _issue_to_finding(
    repo: ProjectRepository,
    issue: Issue,
    project_id: str,
    run_id: str,
    next_number: int,
) -> tuple[FindingRecord, int]:
    fingerprint = finding_fingerprint(issue)
    issue_id = repo.find_issue_id_by_fingerprint(project_id, fingerprint)
    if not issue_id:
        issue_id = f"AR-{next_number:04d}"
        next_number += 1
    issue.issue_id = issue_id

    metadata = RULE_METADATA_BY_ID.get(issue.rule_id)
    evidence = FindingEvidence(
        reason=issue.message,
        context=issue.context,
        matched_text=issue.found_text,
        coordinates={"x0": issue.x0, "y0": issue.y0, "x1": issue.x1, "y1": issue.y1},
        rule_metadata=metadata.model_dump(mode="json") if metadata else {},
    )
    now = now_iso()
    record = FindingRecord(
        id=new_id("finding"),
        project_id=project_id,
        run_id=run_id,
        issue_id=issue_id,
        fingerprint=fingerprint,
        rule_id=issue.rule_id,
        subject=issue.subject,
        original_message=issue.message,
        edited_message=issue.message,
        severity=_severity(issue.severity),
        discipline=issue.discipline,
        confidence=float(issue.confidence),
        status=FindingStatus.DRAFT,
        page_number=issue.page_number,
        output_pdf_page_number=issue.output_pdf_page_number,
        sheet_number=issue.sheet_number,
        found_text=issue.found_text,
        context=issue.context,
        x0=issue.x0,
        y0=issue.y0,
        x1=issue.x1,
        y1=issue.y1,
        owner=issue.owner,
        reviewer_notes="",
        rfi_candidate=issue.rfi_candidate == "Yes",
        source=issue.source,
        evidence=evidence,
        created_at=now,
        updated_at=now,
    )
    return record, next_number


def _files_by_role(files: list[FileRecord]) -> dict[FileRole, list[FileRecord]]:
    grouped: dict[FileRole, list[FileRecord]] = {}
    for file in files:
        grouped.setdefault(file.role, []).append(file)
    return grouped


def _reference_overrides(files: list[FileRecord]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for file in files:
        key = REFERENCE_ROLE_TO_CONFIG_KEY.get(file.role)
        if key and file.extension in {".csv", ".xlsx", ".xlsm"} and key not in overrides:
            overrides[key] = str(file.local_path)
        if file.role == FileRole.ALIAS_TABLE:
            overrides["alias_table"] = str(file.local_path)
        if file.role == FileRole.IGNORE_PATTERNS:
            overrides["ignore_patterns"] = str(file.local_path)
    return overrides


def _manifest_file(record: FileRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "role": record.role.value,
        "file_name": record.file_name,
        "original_path": str(record.original_path),
        "local_path": str(record.local_path),
        "extension": record.extension,
        "size_bytes": record.size_bytes,
        "sha256": record.sha256,
        "warnings": record.warnings,
    }


def _manifest_outputs(out_dir: Path) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    if not out_dir.exists():
        return outputs
    for path in sorted(item for item in out_dir.iterdir() if item.is_file()):
        try:
            outputs.append({
                "path": str(path),
                "file_name": path.name,
                "extension": path.suffix.lower(),
                "size_bytes": path.stat().st_size,
            })
        except OSError:
            outputs.append({"path": str(path), "file_name": path.name, "extension": path.suffix.lower()})
    return outputs


def _active_rule_count(config: dict[str, Any]) -> int:
    return sum(1 for rule in config.get("rules", {}).values() if bool(rule.get("enabled", True)))


def load_project_references(config: dict[str, Any], overrides: dict[str, str]) -> dict:
    ref_cfg = dict(config.get("reference_files", {}))
    for key in REFERENCE_ROLE_TO_CONFIG_KEY.values():
        if overrides.get(key):
            ref_cfg[key] = overrides[key]
    maps = config.get("column_mapping", {})
    return {
        "drawing_index": load_reference_records(ref_cfg.get("drawing_index"), "drawing_index", maps.get("drawing_index", {}), config) if ref_cfg.get("drawing_index") else [],
        "valve_list": load_reference_records(ref_cfg.get("valve_list"), "valve_list", maps.get("valve_list", {}), config) if ref_cfg.get("valve_list") else [],
        "line_list": load_reference_records(ref_cfg.get("line_list"), "line_list", maps.get("line_list", {}), config) if ref_cfg.get("line_list") else [],
        "instrument_index": load_reference_records(ref_cfg.get("instrument_index"), "instrument_index", maps.get("instrument_index", {}), config) if ref_cfg.get("instrument_index") else [],
        "equipment_list": load_reference_records(ref_cfg.get("equipment_list"), "equipment_list", maps.get("equipment_list", {}), config) if ref_cfg.get("equipment_list") else [],
    }


def run_project_review(
    project_db_path: Path,
    project_id: str,
    run_id: str,
    profile: str,
    config_path: Path | None = None,
) -> None:
    repo = ProjectRepository(project_db_path)
    project = repo.get_project(project_id)
    if project is None:
        raise MissingInputError(f"Project not found: {project_id}")

    started = time.monotonic()
    warnings: list[str] = []
    doc: fitz.Document | None = None

    try:
        repo.update_run(run_id, status=RunStatus.RUNNING, started_at=now_iso())
        repo.add_progress(run_id, "validation", "Validating project inputs.", 5)
        files = repo.list_files(project_id)
        validation_issues = validate_project_inputs(files, project_root=project.root_path)
        blocking = [issue for issue in validation_issues if issue.level == "error"]
        warnings.extend(issue.message for issue in validation_issues if issue.level != "error")
        if blocking:
            raise ValidationError("; ".join(issue.message for issue in blocking), details={"issues": [issue.model_dump(mode="json") for issue in blocking]})

        grouped = _files_by_role(files)
        drawing = grouped.get(FileRole.DRAWING_SET, [None])[0]
        if drawing is None:
            raise MissingInputError("Select one drawing set PDF before running a review.")

        config = apply_saved_reference_mappings(load_config(config_path, profile=profile), project.root_path)
        config.setdefault("outputs", {})["single_review_packet_pdf"] = False
        config.setdefault("outputs", {})["dry_run"] = True
        overrides = _reference_overrides(files)
        if overrides.get("alias_table"):
            config.setdefault("normalization", {})["alias_table"] = overrides["alias_table"]
        if overrides.get("ignore_patterns"):
            config.setdefault("normalization", {})["ignore_patterns"] = overrides["ignore_patterns"]

        repo.add_progress(run_id, "extract", f"Opening drawing set: {drawing.file_name}", 15)
        doc = fitz.open(drawing.local_path)
        page_infos, page_texts = extract_page_info(doc, config)

        repo.add_progress(run_id, "references", "Loading reference files and normalization settings.", 35)
        aliases = load_aliases(config.get("normalization", {}).get("alias_table"), config)
        ignore_patterns = load_ignore_patterns(config.get("normalization", {}).get("ignore_patterns"))
        refs = load_project_references(config, overrides)
        for group in refs.values():
            warnings.extend(validate_reference_records(group))

        repo.add_progress(run_id, "extract", "Extracting deterministic text hits and coordinates.", 50)
        hits = extract_word_hits(doc, page_infos, page_texts, config, aliases=aliases, ignore_patterns=ignore_patterns)

        out_dir = Path(repo.get_run(run_id).output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        if config.get("outputs", {}).get("export_text", False):
            export_extracted_text(out_dir, page_infos, page_texts)
        if config.get("outputs", {}).get("export_words", False):
            export_words_csv(out_dir / "word_coordinates_debug.csv", doc, page_infos)

        repo.add_progress(run_id, "rules", "Running deterministic QA rules.", 70)
        builder = IssueBuilder(config)
        ctx = RuleContext(
            config=config,
            issue_builder=builder,
            page_infos=page_infos,
            page_texts=page_texts,
            hits=hits,
            references=refs,
            run_warnings=warnings,
        )
        issues = run_all_rules(ctx)

        repo.add_progress(run_id, "persist", "Persisting findings with stable issue IDs.", 82)
        next_number = _next_issue_number(repo, project_id)
        finding_records: list[FindingRecord] = []
        for issue in issues:
            record, next_number = _issue_to_finding(repo, issue, project_id, run_id, next_number)
            finding_records.append(record)
        repo.add_findings(finding_records)

        manifest = RunManifest(
            input=str(drawing.local_path),
            output_dir=str(out_dir),
            started_at=repo.get_run(run_id).started_at or now_iso(),
            run_id=run_id,
            project_id=project_id,
            profile=profile,
            app_version=APP_VERSION,
            engine_version=ENGINE_VERSION,
            active_rule_count=_active_rule_count(config),
            total_rule_count=len(config.get("rules", {})),
            input_files=[_manifest_file(file) for file in files],
            settings_used=config,
            warnings=warnings,
            validation_warnings=list(warnings),
        )
        manifest.rule_counts = dict(Counter(i.rule_id for i in issues))
        manifest.severity_counts = dict(Counter(i.severity for i in issues))
        manifest.finding_status_counts = {FindingStatus.DRAFT.value: len(issues)}
        manifest.complete(started, doc.page_count, len(issues))

        repo.add_progress(run_id, "reports", "Writing support reports.", 92)
        write_all_reports(out_dir, issues, page_infos, hits, manifest, config)
        manifest.output_files = _manifest_outputs(out_dir)
        write_manifest(out_dir, manifest)
        (out_dir / "run_inputs.json").write_text(
            json.dumps({"files": [file.model_dump(mode="json") for file in files], "validation_warnings": warnings}, indent=2),
            encoding="utf-8",
        )

        repo.update_run(
            run_id,
            status=RunStatus.COMPLETED,
            completed_at=now_iso(),
            page_count=doc.page_count,
            issue_count=len(issues),
            warnings=warnings,
            error_message="",
        )
        repo.add_progress(run_id, "completed", f"Review completed with {len(issues)} draft finding(s).", 100)
    except Exception as exc:
        message = exc.message if hasattr(exc, "message") else str(exc)
        failed_run = repo.get_run(run_id)
        out_dir = Path(failed_run.output_dir) if failed_run else project.root_path / "outputs" / "runs" / run_id
        failed_manifest = RunManifest(
            input="",
            output_dir=str(out_dir),
            started_at=failed_run.started_at if failed_run and failed_run.started_at else now_iso(),
            run_id=run_id,
            project_id=project_id,
            profile=profile,
            app_version=APP_VERSION,
            engine_version=ENGINE_VERSION,
            status="failed",
            input_files=[_manifest_file(file) for file in repo.list_files(project_id)],
            warnings=warnings,
            validation_warnings=list(warnings),
            error_message=message or "Review run failed.",
        )
        failed_manifest.completed_at = now_iso()
        out_dir.mkdir(parents=True, exist_ok=True)
        write_manifest(out_dir, failed_manifest)
        repo.update_run(run_id, status=RunStatus.FAILED, completed_at=now_iso(), warnings=warnings, error_message=message)
        repo.add_progress(run_id, "failed", message or "Review failed.", 100, level="error")
        if isinstance(exc, (ValidationError, MissingInputError)):
            raise
        raise ReviewRunError(message or "Review run failed.") from exc
    finally:
        if doc is not None:
            doc.close()
