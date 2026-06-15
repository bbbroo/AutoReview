from __future__ import annotations

from pathlib import Path

import fitz

from ng_drawing_qa.annotations import annotate_pdf
from ng_drawing_qa.models import Issue
from ng_drawing_qa.placement import resolve_issue_placements


def _synthetic_pdf(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 140), "VALVE BV-101", fontsize=12)
    page.insert_text((220, 300), "DESIGN PRESSURE 720 PSIG", fontsize=12)
    page.insert_text((450, 720), "SHEET NUMBER: P-201", fontsize=10)
    doc.save(path)
    doc.close()
    return path


def _config() -> dict:
    return {
        "outputs": {"dry_run": False, "annotate_pdf": True, "insert_summary_page": False},
        "annotation": {"add_issue_id_labels": True, "issue_id_label_font_size": 8},
        "title_block": {
            "regions": {
                "default": {
                    "sheet_number": [0.70, 0.86, 0.98, 0.95],
                }
            }
        },
    }


def test_resolve_placement_types_and_coordinates(tmp_path: Path):
    pdf = _synthetic_pdf(tmp_path / "placement.pdf")
    issues = [
        Issue(
            issue_id="AR-0001",
            rule_id="VALVE_TAG_RECONCILIATION",
            subject="Valve tag not in reference",
            message="Valve BV-101 was found on the drawing.",
            page_number=1,
            found_text="BV-101",
            x0=108,
            y0=128,
            x1=148,
            y1=144,
        ),
        Issue(
            issue_id="AR-0002",
            rule_id="PRESSURE_CONSISTENCY",
            subject="Pressure conflict",
            message="Verify design pressure.",
            page_number=1,
            found_text="DESIGN PRESSURE 720 PSIG",
        ),
        Issue(
            issue_id="AR-0003",
            rule_id="TITLE_BLOCK_MISSING_FIELD",
            subject="Missing title block field",
            message="Title block sheet number needs review.",
            page_number=1,
            found_text="sheet_number",
        ),
        Issue(
            issue_id="AR-0004",
            rule_id="VALVE_TAG_RECONCILIATION",
            subject="Valve tag listed but not found on drawings",
            message="Valve BV-999 exists in the provided valve list, but was not found in searchable PDF text.",
            page_number=1,
            found_text="BV-999",
        ),
    ]

    with fitz.open(pdf) as doc:
        resolve_issue_placements(doc, issues, _config())

    assert issues[0].placement_type == "exact_hit"
    assert issues[0].coordinate_source == "rule_hit"

    assert issues[1].placement_type == "resolved_text_search"
    assert issues[1].coordinate_source == "pdf_text_search"
    assert 210 <= issues[1].x0 <= 235
    assert 285 <= issues[1].y0 <= 305
    assert issues[1].resolved_match_text == "DESIGN PRESSURE 720 PSIG"

    assert issues[2].placement_type == "title_block_region"
    assert issues[2].x0 > 400
    assert issues[2].y0 > 650

    assert issues[3].placement_type == "reference_only"
    assert issues[3].placement_warning


def test_annotation_skips_reference_only_and_counts_resolved_types(tmp_path: Path):
    pdf = _synthetic_pdf(tmp_path / "annotated.pdf")
    issues = [
        Issue(issue_id="AR-0001", rule_id="VALVE_TAG_RECONCILIATION", subject="Valve", message="Valve exact.", page_number=1, found_text="BV-101", x0=108, y0=128, x1=148, y1=144),
        Issue(issue_id="AR-0002", rule_id="PRESSURE_CONSISTENCY", subject="Pressure", message="Pressure resolved.", page_number=1, found_text="DESIGN PRESSURE 720 PSIG"),
        Issue(issue_id="AR-0003", rule_id="VALVE_TAG_RECONCILIATION", subject="Valve tag listed but not found on drawings", message="Valve BV-999 exists in the provided valve list, but was not found in searchable PDF text.", page_number=1, found_text="BV-999"),
    ]

    with fitz.open(pdf) as doc:
        resolve_issue_placements(doc, issues, _config())
        counts = annotate_pdf(doc, issues, _config())
        subjects = [(annot.info or {}).get("subject", "") for annot in list(doc[0].annots() or [])]

    assert counts["exact_location_markups"] == 1
    assert counts["resolved_search_markups"] == 1
    assert counts["reference_only_findings"] == 1
    assert counts["fallback_page_callouts"] == 0
    assert counts["unplaced_findings"] == 0
    assert not any("AR-0003" in subject for subject in subjects)


def test_annotation_draws_page_level_callout_when_text_cannot_be_resolved(tmp_path: Path):
    pdf = _synthetic_pdf(tmp_path / "page_level.pdf")
    issue = Issue(
        issue_id="AR-0099",
        rule_id="LOW_SEARCHABLE_TEXT",
        subject="Low searchable text",
        message="Page-level quality issue without an exact text rectangle.",
        page_number=1,
        found_text="not-a-real-token",
    )

    with fitz.open(pdf) as doc:
        resolve_issue_placements(doc, [issue], _config())
        counts = annotate_pdf(doc, [issue], _config())
        subjects = [(annot.info or {}).get("subject", "") for annot in list(doc[0].annots() or [])]

    assert issue.placement_type == "page_level"
    assert counts["fallback_page_callouts"] == 1
    assert "AR-0099 - Page Callout" in subjects
