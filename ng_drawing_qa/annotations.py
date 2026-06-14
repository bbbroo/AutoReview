from __future__ import annotations

from collections import defaultdict
from typing import Any
import math
import textwrap
import fitz

from .models import Issue


def color_for(config: dict[str, Any], severity: str) -> tuple[float, float, float]:
    colors = config.get("annotation", {}).get("colors", {})
    return tuple(colors.get(severity, colors.get("Info", [0.0, 0.35, 1.0])))


def _rect(issue: Issue) -> fitz.Rect:
    return fitz.Rect(issue.x0, issue.y0, issue.x1, issue.y1)


def _has_valid_coordinates(issue: Issue) -> bool:
    values = [issue.x0, issue.y0, issue.x1, issue.y1]
    return all(math.isfinite(float(value)) for value in values) and issue.x1 > issue.x0 and issue.y1 > issue.y0


def _label_fill(color: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(min(1.0, 0.82 + channel * 0.18) for channel in color)


def _issue_label_rect(page: fitz.Page, rect: fitz.Rect, text: str, fontsize: float) -> fitz.Rect:
    width = min(max(72.0, len(text) * fontsize * 0.9 + 18.0), 140.0)
    height = max(20.0, fontsize + 12.0)
    x0 = min(max(0.0, rect.x0), max(0.0, page.rect.width - width))
    if rect.y0 >= height + 4:
        y0 = rect.y0 - height - 2
    else:
        y0 = min(page.rect.height - height, rect.y1 + 2)
    y0 = max(0.0, y0)
    return fitz.Rect(x0, y0, x0 + width, y0 + height)


def add_issue_id_label(
    page: fitz.Page,
    rect: fitz.Rect,
    issue: Issue,
    config: dict[str, Any],
    color: tuple[float, float, float],
    content: str,
) -> None:
    ann_config = config.get("annotation", {})
    if not ann_config.get("add_issue_id_labels", True):
        return

    try:
        fontsize = float(ann_config.get("issue_id_label_font_size", 7))
    except (TypeError, ValueError):
        fontsize = 7.0

    text = issue.issue_id
    label_rect = _issue_label_rect(page, rect, text, fontsize)
    try:
        page.draw_rect(label_rect, color=color, fill=_label_fill(color), width=0.5, overlay=True)
        page.insert_textbox(label_rect + (3, 2, -3, -2), text, fontsize=fontsize, fontname="helv", color=(0, 0, 0), overlay=True)
        label = page.add_freetext_annot(label_rect, text, fontsize=fontsize, fill_color=_label_fill(color), border_color=color)
        label.set_border(width=0.5)
        label.set_info(
            title="Natural Gas QA",
            subject=f"{issue.issue_id} - Issue ID Label",
            content=content,
        )
        label.update()
    except Exception:
        pass


def _issue_content(issue: Issue) -> str:
    return (
        f"{issue.issue_id} | {issue.status}\n"
        f"Rule: {issue.rule_id}\n"
        f"Severity: {issue.severity}\n"
        f"Confidence: {issue.confidence:.2f}\n\n"
        f"{issue.message}"
    )


def add_issue_markup(doc: fitz.Document, issue: Issue, config: dict[str, Any]) -> bool:
    if issue.page_number < 1 or issue.page_number > doc.page_count:
        return False
    if not _has_valid_coordinates(issue):
        return False

    page = doc[issue.page_number - 1]
    color = color_for(config, issue.severity)
    pad = 4
    rect = _rect(issue)
    rect.x0 = max(0, rect.x0 - pad)
    rect.y0 = max(0, rect.y0 - pad)
    rect.x1 = min(page.rect.width, rect.x1 + pad)
    rect.y1 = min(page.rect.height, rect.y1 + pad)

    content = _issue_content(issue)
    subject = issue.subject

    try:
        a = page.add_rect_annot(rect)
        a.set_colors(stroke=color)
        a.set_border(width=1.5)
        a.set_info(title="Natural Gas QA", subject=subject, content=content)
        a.update()
    except Exception:
        pass
    return True


def _fallback_callout_rect(page: fitz.Page, index: int) -> fitz.Rect:
    width = min(330.0, max(180.0, page.rect.width - 72.0))
    height = 62.0
    gap = 8.0
    x0 = max(24.0, page.rect.width - width - 24.0)
    y0 = 84.0 + index * (height + gap)
    max_y0 = max(84.0, page.rect.height - height - 24.0)
    if y0 > max_y0:
        column = int((y0 - 84.0) // max(1.0, max_y0 - 84.0 + height + gap))
        x0 = max(24.0, x0 - column * (width + 12.0))
        y0 = 84.0 + (index % max(1, int((max_y0 - 84.0) // (height + gap) + 1))) * (height + gap)
    x0 = min(max(24.0, x0), max(24.0, page.rect.width - width - 24.0))
    return fitz.Rect(x0, y0, x0 + width, y0 + height)


def add_page_level_callout(doc: fitz.Document, issue: Issue, config: dict[str, Any], index: int) -> bool:
    if issue.page_number < 1 or issue.page_number > doc.page_count:
        return False

    page = doc[issue.page_number - 1]
    color = color_for(config, issue.severity)
    rect = _fallback_callout_rect(page, index)
    content = _issue_content(issue)
    message = textwrap.shorten(str(issue.message or ""), width=150, placeholder="...")
    visible = f"{issue.issue_id} | {issue.severity} | {issue.rule_id}\n{message}"
    try:
        page.draw_rect(rect, color=color, fill=_label_fill(color), width=0.8, overlay=True)
        callout = page.add_freetext_annot(rect + (5, 4, -5, -4), visible, fontsize=7.5)
        callout.set_border(width=0.8)
        callout.set_info(
            title="Natural Gas QA",
            subject=f"{issue.issue_id} - Page Callout",
            content=content,
        )
        callout.update()
        return True
    except Exception:
        return False

    add_issue_id_label(page, rect, issue, config, color, content)

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


def annotate_pdf(doc: fitz.Document, issues: list[Issue], config: dict[str, Any]) -> dict[str, int]:
    stats = {
        "coordinate_backed_markups": 0,
        "fallback_page_callouts": 0,
        "unplaced_findings": 0,
    }
    if config.get("outputs", {}).get("dry_run", False) or not config.get("outputs", {}).get("annotate_pdf", True):
        stats["unplaced_findings"] = len(issues)
        return stats

    fallback_counts_by_page: dict[int, int] = defaultdict(int)
    for issue in issues:
        if issue.page_number < 1 or issue.page_number > doc.page_count:
            stats["unplaced_findings"] += 1
            continue
        if _has_valid_coordinates(issue):
            if add_issue_markup(doc, issue, config):
                stats["coordinate_backed_markups"] += 1
            else:
                stats["unplaced_findings"] += 1
            continue
        fallback_index = fallback_counts_by_page[issue.page_number]
        fallback_counts_by_page[issue.page_number] += 1
        if add_page_level_callout(doc, issue, config, fallback_index):
            stats["fallback_page_callouts"] += 1
        else:
            stats["unplaced_findings"] += 1

    add_sheet_summary_annotations(doc, issues, config)
    add_summary_page(doc, issues, config)
    return stats
