from __future__ import annotations

from pathlib import Path

from ng_drawing_qa.models import Issue
from ng_drawing_qa.reports import write_reference_reports


def test_reference_reports_handle_dangling_issue_objects(tmp_path: Path):
    issue = Issue(
        issue_id="AR-0001",
        rule_id="DETAIL_REFERENCE_CHECK",
        subject="Reference target sheet not found",
        message="Detail references M-999 but that sheet is missing.",
        severity="Major",
        sheet_number="P-201",
        found_text="1/M-999",
        page_number=3,
    )

    write_reference_reports(tmp_path, [issue])

    report = (tmp_path / "hyperlink_suggestions.csv").read_text(encoding="utf-8")
    assert "AR-0001" in report
    assert "P-201" in report
    assert "1/M-999" in report
