from __future__ import annotations

from pathlib import Path
import argparse
import time
import shutil
import json
from collections import Counter

import fitz

from .config import load_config, save_default_config
from .models import RunManifest
from .reference import load_reference_records, load_aliases, load_ignore_patterns, validate_reference_records
from .pdf_utils import extract_page_info, extract_word_hits, export_extracted_text, export_words_csv
from .issue_builder import IssueBuilder
from .rules.base import RuleContext
from .rules.core_rules import run_all_rules
from .annotations import annotate_pdf
from .reports import write_all_reports
from .review_packet import build_single_review_packet
from .sample import generate_sample_project


def timestamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def build_out_dir(base: str | Path, config: dict, input_pdf: Path | None = None) -> Path:
    base = Path(base)
    if config.get("outputs", {}).get("timestamped_output_folder", True):
        stem = input_pdf.stem if input_pdf else "batch"
        return base / f"{stem}_ngqa_{timestamp()}"
    return base


def load_references(config: dict, overrides: dict[str, str | None]) -> dict:
    ref_cfg = dict(config.get("reference_files", {}))
    ref_cfg.update({k: v for k, v in overrides.items() if v})
    maps = config.get("column_mapping", {})
    refs = {
        "drawing_index": load_reference_records(ref_cfg.get("drawing_index"), "drawing_index", maps.get("drawing_index", {}), config) if ref_cfg.get("drawing_index") else [],
        "valve_list": load_reference_records(ref_cfg.get("valve_list"), "valve_list", maps.get("valve_list", {}), config) if ref_cfg.get("valve_list") else [],
        "line_list": load_reference_records(ref_cfg.get("line_list"), "line_list", maps.get("line_list", {}), config) if ref_cfg.get("line_list") else [],
        "instrument_index": load_reference_records(ref_cfg.get("instrument_index"), "instrument_index", maps.get("instrument_index", {}), config) if ref_cfg.get("instrument_index") else [],
        "equipment_list": load_reference_records(ref_cfg.get("equipment_list"), "equipment_list", maps.get("equipment_list", {}), config) if ref_cfg.get("equipment_list") else [],
    }
    return refs


def process_one_pdf(input_pdf: Path, args, config: dict, batch_out_dir: Path | None = None) -> Path:
    started = time.monotonic()
    out_dir = batch_out_dir or build_out_dir(args.out_dir, config, input_pdf)
    out_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = out_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_path = logs_dir / f"run_{timestamp()}.log"

    warnings = []
    manifest = RunManifest(
        input=str(input_pdf),
        output_dir=str(out_dir),
        started_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        settings_used=config,
        warnings=warnings,
    )

    with log_path.open("w", encoding="utf-8") as log:
        def log_line(msg: str):
            print(msg)
            log.write(msg + "\n")
            log.flush()

        log_line(f"Opening PDF: {input_pdf}")
        doc = fitz.open(input_pdf)
        page_infos, page_texts = extract_page_info(doc, config)

        alias_path = args.alias_table or config.get("normalization", {}).get("alias_table")
        ignore_path = args.ignore_patterns or config.get("normalization", {}).get("ignore_patterns")
        aliases = load_aliases(alias_path, config)
        ignore_patterns = load_ignore_patterns(ignore_path)

        refs = load_references(config, {
            "drawing_index": args.drawing_index,
            "valve_list": args.valve_list,
            "line_list": args.line_list,
            "instrument_index": args.instrument_index,
            "equipment_list": args.equipment_list,
        })
        for group in refs.values():
            warnings.extend(validate_reference_records(group))

        hits = extract_word_hits(doc, page_infos, page_texts, config, aliases=aliases, ignore_patterns=ignore_patterns)

        if args.export_text or config.get("outputs", {}).get("export_text", False):
            export_extracted_text(out_dir, page_infos, page_texts)
        if args.export_words or config.get("outputs", {}).get("export_words", False):
            export_words_csv(out_dir / "word_coordinates_debug.csv", doc, page_infos)

        issue_builder = IssueBuilder(config)
        ctx = RuleContext(
            config=config,
            issue_builder=issue_builder,
            page_infos=page_infos,
            page_texts=page_texts,
            hits=hits,
            references=refs,
            run_warnings=warnings,
        )
        issues = run_all_rules(ctx)

        manifest.rule_counts = dict(Counter(i.rule_id for i in issues))
        manifest.severity_counts = dict(Counter(i.severity for i in issues))
        manifest.complete(started, doc.page_count, len(issues))

        log_line(f"Draft issues: {len(issues)}")
        log_line(f"Output directory: {out_dir}")

        if args.dry_run:
            config.setdefault("outputs", {})["dry_run"] = True

        if not config.get("outputs", {}).get("dry_run", False):
            annotate_pdf(doc, issues, config)
            output_pdf = out_dir / f"{input_pdf.stem}_marked_up.pdf"
            doc.save(output_pdf, garbage=4, deflate=True)
            log_line(f"Annotated PDF: {output_pdf}")

            if config.get("outputs", {}).get("single_review_packet_pdf", True):
                packet_name = config.get("outputs", {}).get("single_review_packet_name", "single_review_packet.pdf")
                packet_path = out_dir / packet_name
                build_single_review_packet(doc, issues, refs, packet_path, config)
                log_line(f"Single review packet PDF: {packet_path}")
        else:
            log_line("Dry run: PDF annotations skipped.")
            if config.get("outputs", {}).get("single_review_packet_pdf", True):
                log_line("Dry run: single review packet skipped because the marked-up PDF was not generated.")

        doc.close()
        write_all_reports(out_dir, issues, page_infos, hits, manifest, config)
        log_line("Reports written.")

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
    parser.add_argument("--profile", choices=["regulator_station", "pipeline_crossing", "p_and_id"], help="Rule profile")
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

    args = parser.parse_args(argv)

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

    process_one_pdf(Path(args.input_pdf), args, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
