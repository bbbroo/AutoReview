from __future__ import annotations

from pathlib import Path
import argparse
import time
import json

import yaml

from .config import load_config, save_default_config
from .errors import AutoReviewError
from .sample import generate_sample_project
from .rules.registry import get_rule_metadata
from .schemas import FileRole, PacketExportSettings, PacketFindingScope, ProjectCreate
from .services.files import ingest_file
from .services.packet import export_review_packet
from .services.projects import create_project
from .services.review import run_project_review
from .storage.sqlite import AppIndex, ProjectRepository


def timestamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def build_out_dir(base: str | Path, config: dict, input_pdf: Path | None = None) -> Path:
    base = Path(base)
    if config.get("outputs", {}).get("timestamped_output_folder", True):
        stem = input_pdf.stem if input_pdf else "batch"
        return base / f"{stem}_ngqa_{timestamp()}"
    return base


CLI_REFERENCE_ROLES: dict[str, FileRole] = {
    "drawing_index": FileRole.DRAWING_INDEX,
    "valve_list": FileRole.VALVE_LIST,
    "line_list": FileRole.LINE_LIST,
    "instrument_index": FileRole.INSTRUMENT_INDEX,
    "equipment_list": FileRole.EQUIPMENT_LIST,
    "alias_table": FileRole.ALIAS_TABLE,
    "ignore_patterns": FileRole.IGNORE_PATTERNS,
}


def _write_cli_config(out_dir: Path, args, config: dict) -> Path:
    cli_config = json.loads(json.dumps(config))
    outputs = cli_config.setdefault("outputs", {})
    if args.dry_run:
        outputs["dry_run"] = True
    if args.export_text:
        outputs["export_text"] = True
    if args.export_words:
        outputs["export_words"] = True
    config_path = out_dir / "profiles" / "cli_run_config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(cli_config, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return config_path


def _cli_reference_paths(args) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for attr in CLI_REFERENCE_ROLES:
        value = getattr(args, attr, None)
        if value:
            paths[attr] = Path(value)
    return paths


def _print_packet_result(repo: ProjectRepository, run_id: str, packet_name: str) -> None:
    run = repo.get_run(run_id)
    if run is None:
        return
    manifest_path = run.output_dir / "run_manifest.json"
    packet_path = ""
    marked_path = ""
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            packet_path = manifest.get("output_packet_path", "")
            marked_path = manifest.get("marked_up_pdf_path", "")
        except Exception:
            pass
    if marked_path:
        print(f"Annotated PDF: {marked_path}")
    if packet_path:
        print(f"Single review packet PDF: {packet_path}")
    elif packet_name:
        print("Single review packet PDF: not generated.")


def process_one_pdf(input_pdf: Path, args, config: dict, batch_out_dir: Path | None = None) -> Path:
    out_dir = batch_out_dir or build_out_dir(args.out_dir, config, input_pdf)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Opening PDF: {input_pdf}")
    app_index = AppIndex(out_dir / "app_index.sqlite")
    project = create_project(ProjectCreate(name=out_dir.name, root_path=out_dir), app_index)
    repo = ProjectRepository(project.database_path)
    ingest_file(repo, project.id, project.root_path, input_pdf, role=FileRole.DRAWING_SET, copy_into_project=True)
    for attr, path in _cli_reference_paths(args).items():
        ingest_file(repo, project.id, project.root_path, path, role=CLI_REFERENCE_ROLES[attr], copy_into_project=True)

    config_path = _write_cli_config(project.root_path, args, config)
    run = repo.create_run(project.id, config.get("project", {}).get("profile", args.profile or "balanced"), project.root_path)
    run_project_review(project.database_path, project.id, run.id, run.profile, config_path=config_path)
    completed = repo.get_run(run.id)
    findings = repo.list_findings(run.id)
    print(f"Draft issues: {len(findings)}")
    print(f"Output directory: {project.root_path}")

    outputs = config.get("outputs", {})
    if args.dry_run or outputs.get("dry_run", False):
        print("Dry run: PDF annotations and packet export skipped.")
    elif outputs.get("single_review_packet_pdf", True):
        packet_name = outputs.get("single_review_packet_name", "single_review_packet.pdf")
        export_review_packet(
            project.database_path,
            run.id,
            PacketExportSettings(finding_scope=PacketFindingScope.ALL, include_reference_inputs=True, packet_name=packet_name),
        )
        _print_packet_result(repo, run.id, packet_name)
    else:
        print("Single review packet PDF: disabled by configuration.")
    if completed and completed.status.value == "completed":
        print("Reports written.")
    return out_dir


def create_project_template(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    save_default_config(out_dir / "config.yaml")
    (out_dir / "input_pdfs").mkdir(exist_ok=True)
    (out_dir / "references").mkdir(exist_ok=True)
    (out_dir / "outputs").mkdir(exist_ok=True)
    for name, headers in {
        "references/drawing_index.csv": ["sheet_number", "sheet_title", "revision", "issue_date", "status"],
        "references/valve_list.csv": ["tag", "type", "size", "service"],
        "references/line_list.csv": ["line_number", "size", "service", "maop_psig", "test_pressure_psig", "material", "spec", "coating"],
        "references/instrument_index.csv": ["tag", "type", "service"],
        "references/equipment_list.csv": ["tag", "type", "service"],
        "references/alias_table.csv": ["alias", "canonical"],
        "references/ignore_patterns.csv": ["pattern"],
    }.items():
        p = out_dir / name
        with p.open("w", encoding="utf-8") as f:
            f.write(",".join(headers) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Natural gas drawing QA automation for Bluebeam-reviewable PDF markups.")
    parser.add_argument("input_pdf", nargs="?", help="Input PDF drawing set")
    parser.add_argument("--out-dir", default="ngqa_outputs", help="Output directory")
    parser.add_argument("--config", help="YAML config file")
    parser.add_argument("--profile", choices=["balanced", "conservative", "aggressive", "regulator_station", "pipeline_crossing", "p_and_id"], help="Rule profile")
    parser.add_argument("--dry-run", action="store_true", help="Generate reports only, no marked-up PDF")
    parser.add_argument("--batch-folder", help="Process every PDF in this folder")
    parser.add_argument("--export-text", action="store_true", help="Export extracted text per page")
    parser.add_argument("--export-words", action="store_true", help="Export all word coordinates to CSV")

    parser.add_argument("--drawing-index")
    parser.add_argument("--valve-list")
    parser.add_argument("--line-list")
    parser.add_argument("--instrument-index")
    parser.add_argument("--equipment-list")
    parser.add_argument("--alias-table")
    parser.add_argument("--ignore-patterns")

    parser.add_argument("--write-default-config", help="Write default YAML config to this path and exit")
    parser.add_argument("--create-project-template", help="Create a reusable project template folder and exit")
    parser.add_argument("--generate-sample", help="Generate a sample PDF and reference files in this folder and exit")
    parser.add_argument("--list-rules", action="store_true", help="List deterministic rule metadata and exit")

    args = parser.parse_args(argv)

    if args.list_rules:
        for rule in get_rule_metadata():
            state = "default-on" if rule.enabled_by_default else "default-off"
            print(f"{rule.rule_id}: {rule.name} [{rule.default_severity.value}, {rule.discipline}, {state}]")
        return 0

    if args.write_default_config:
        save_default_config(args.write_default_config)
        print(f"Wrote default config: {args.write_default_config}")
        return 0
    if args.create_project_template:
        create_project_template(Path(args.create_project_template))
        print(f"Created project template: {args.create_project_template}")
        return 0
    if args.generate_sample:
        generate_sample_project(Path(args.generate_sample))
        print(f"Generated sample project: {args.generate_sample}")
        return 0

    config = load_config(args.config, profile=args.profile)
    if args.dry_run:
        config.setdefault("outputs", {})["dry_run"] = True

    if args.batch_folder:
        folder = Path(args.batch_folder)
        if not folder.exists():
            raise FileNotFoundError(folder)
        batch_out = build_out_dir(args.out_dir, config, None)
        batch_out.mkdir(parents=True, exist_ok=True)
        run_dirs = []
        for pdf in sorted(folder.glob("*.pdf")):
            run_dirs.append(str(process_one_pdf(pdf, args, config, batch_out / pdf.stem)))
        (batch_out / "batch_manifest.json").write_text(json.dumps({"runs": run_dirs}, indent=2), encoding="utf-8")
        print(f"Batch complete: {batch_out}")
        return 0

    if not args.input_pdf:
        parser.error("input_pdf is required unless using --batch-folder, --generate-sample, --write-default-config, or --create-project-template")

    try:
        process_one_pdf(Path(args.input_pdf), args, config)
        return 0
    except AutoReviewError as exc:
        print(f"{exc.code}: {exc.message}")
        return 2
    except FileNotFoundError as exc:
        print(f"Input error: file not found: {exc}")
        return 2
    except ValueError as exc:
        print(f"Input error: {exc}")
        return 2
    except RuntimeError as exc:
        print(f"Run error: {exc}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
