from __future__ import annotations

from collections import defaultdict
from typing import Any
import textwrap
import fitz

from .models import Issue


def color_for(config: dict[str, Any], severity: str) -> tuple[float, float, float]:
    colors = config.get("annotation", {}).get("colors", {})
    return tuple(colors.get(severity, colors.get("Info", [0.0, 0.35, 1.0])))


def _rect(issue: Issue) -> fitz.Rect:
    return fitz.Rect(issue.x0, issue.y0, issue.x1, issue.y1)


def add_issue_markup(doc: fitz.Document, issue: Issue, config: dict[str, Any]) -> None:
    if issue.page_number < 1 or issue.page_number > doc.page_count:
        return
    if issue.x1 <= issue.x0 or issue.y1 <= issue.y0:
        return

    page = doc[issue.page_number - 1]
    color = color_for(config, issue.severity)
    pad = 4
    rect = _rect(issue)
    rect.x0 = max(0, rect.x0 - pad)
    rect.y0 = max(0, rect.y0 - pad)
    rect.x1 = min(page.rect.width, rect.x1 + pad)
    rect.y1 = min(page.rect.height, rect.y1 + pad)

    content = (
        f"{issue.issue_id} | {issue.status}\n"
        f"Rule: {issue.rule_id}\n"
        f"Severity: {issue.severity}\n"
        f"Confidence: {issue.confidence:.2f}\n\n"
        f"{issue.message}"
    )
    subject = issue.subject

    try:
        a = page.add_rect_annot(rect)
        a.set_colors(stroke=color)
        a.set_border(width=1.5)
        a.set_info(title="Natural Gas QA", subject=subject, content=content)
        a.update()
    except Exception:
        pass

    try:
        note_x = min(page.rect.width - 16, rect.x1 + 8)
        note_y = max(16, rect.y0)
        n = page.add_text_annot(fitz.Point(note_x, note_y), content)
        n.set_info(title="Natural Gas QA", subject=subject, content=content)
        n.update()
    except Exception:
        pass


def add_summary_page(doc: fitz.Document, issues: list[Issue], config: dict[str, Any]) -> None:
    if not config.get("outputs", {}).get("insert_summary_page", True):
        return

    page = doc.new_page(pno=0, width=612, height=792)
    severity_order = ["Critical", "Major", "Minor", "Info"]
    sev_counts = {s: sum(1 for i in issues if i.severity == s) for s in severity_order}
    rule_counts: dict[str, int] = defaultdict(int)
    sheet_counts: dict[str, int] = defaultdict(int)
    for issue in issues:
        rule_counts[issue.rule_id] += 1
        sheet_counts[issue.sheet_number or "Unknown"] += 1

    y = 48
    page.insert_text((48, y), "Natural Gas Drawing QA - Draft Review Summary", fontsize=18)
    y += 28
    page.insert_text((48, y), f"Total draft issues: {len(issues)}", fontsize=11)
    y += 20
    page.insert_text((48, y), "Severity counts:", fontsize=11)
    y += 16
    for sev in severity_order:
        page.insert_text((70, y), f"{sev}: {sev_counts.get(sev, 0)}", fontsize=10)
        y += 14

    y += 12
    page.insert_text((48, y), "Top rules:", fontsize=11)
    y += 16
    for rule, count in sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)[:12]:
        page.insert_text((70, y), f"{rule}: {count}", fontsize=9)
        y += 13

    y += 12
    page.insert_text((48, y), "Top sheets by issue count:", fontsize=11)
    y += 16
    for sheet, count in sorted(sheet_counts.items(), key=lambda x: x[1], reverse=True)[:12]:
        page.insert_text((70, y), f"{sheet}: {count}", fontsize=9)
        y += 13

    y += 20
    note = (
        "All items are draft automated findings. They must be reviewed, edited, "
        "accepted, or rejected by a qualified engineer/designer before use as formal comments."
    )
    wrapped = textwrap.wrap(note, width=86)
    for line in wrapped:
        page.insert_text((48, y), line, fontsize=9)
        y += 12


def add_sheet_summary_annotations(doc: fitz.Document, issues: list[Issue], config: dict[str, Any]) -> None:
    if not config.get("annotation", {}).get("add_sheet_summary_annotations", True):
        return
    by_page: dict[int, list[Issue]] = defaultdict(list)
    for issue in issues:
        if 1 <= issue.page_number <= doc.page_count:
            by_page[issue.page_number].append(issue)

    for page_number, rows in by_page.items():
        if not rows:
            continue
        page = doc[page_number - 1]
        major = sum(1 for i in rows if i.severity in {"Critical", "Major"})
        minor = sum(1 for i in rows if i.severity == "Minor")
        info = sum(1 for i in rows if i.severity == "Info")
        text = f"NGQA sheet summary: {len(rows)} draft issue(s). Critical/Major: {major}, Minor: {minor}, Info: {info}."
        try:
            rect = fitz.Rect(36, 36, min(page.rect.width - 36, 500), 72)
            a = page.add_freetext_annot(rect, text, fontsize=8, fill_color=(1, 1, 0.85), border_color=color_for(config, "Info"))
            a.set_info(title="Natural Gas QA", subject="NGQA - Sheet Summary", content=text)
            a.update()
        except Exception:
            pass


def annotate_pdf(doc: fitz.Document, issues: list[Issue], config: dict[str, Any]) -> None:
    if config.get("outputs", {}).get("dry_run", False) or not config.get("outputs", {}).get("annotate_pdf", True):
        return

    max_per_rule_page = int(config.get("annotation", {}).get("max_individual_markups_per_rule_page", 10))
    seen_count: dict[tuple[str, int], int] = defaultdict(int)
    for issue in issues:
        key = (issue.rule_id, issue.page_number)
        seen_count[key] += 1
        if seen_count[key] <= max_per_rule_page:
            add_issue_markup(doc, issue, config)

    add_sheet_summary_annotations(doc, issues, config)
    add_summary_page(doc, issues, config)
