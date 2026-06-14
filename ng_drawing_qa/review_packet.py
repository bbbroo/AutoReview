from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import csv
import math
import re
import html
import zipfile
import xml.etree.ElementTree as ET

import fitz

from .models import Issue, PageInfo, Hit
from .reference import ReferenceRecord, read_table, pick_column


PAGE_W = 792
PAGE_H = 612
MARGIN = 36
LINE_H = 13
SMALL = 7.5
NORMAL = 9
TITLE = 16


def _severity_color(severity: str) -> tuple[float, float, float]:
    return {
        "Critical": (1.0, 0.78, 0.78),
        "Major": (1.0, 0.88, 0.65),
        "Minor": (1.0, 0.96, 0.65),
        "Info": (0.80, 0.90, 1.0),
    }.get(severity, (0.92, 0.92, 0.92))


def _stroke_color(severity: str) -> tuple[float, float, float]:
    return {
        "Critical": (0.90, 0.0, 0.0),
        "Major": (0.95, 0.42, 0.0),
        "Minor": (0.75, 0.62, 0.0),
        "Info": (0.0, 0.25, 0.75),
    }.get(severity, (0.2, 0.2, 0.2))


def _wrap(text: str, width: int) -> list[str]:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return [""]
    import textwrap
    return textwrap.wrap(text, width=width, break_long_words=False, replace_whitespace=True) or [""]


def _insert_textbox(page: fitz.Page, rect: fitz.Rect, text: str, fontsize: float = NORMAL, bold: bool = False, color=(0, 0, 0), align=0):
    font = "helv"
    page.insert_textbox(rect, str(text or ""), fontsize=fontsize, fontname=font, color=color, align=align)


def _draw_header(page: fitz.Page, title: str, subtitle: str = ""):
    page.insert_text((MARGIN, 32), title, fontsize=TITLE, fontname="helv")
    if subtitle:
        page.insert_text((MARGIN, 50), subtitle, fontsize=NORMAL, color=(0.25, 0.25, 0.25))


def _draw_footer(page: fitz.Page, footer: str):
    page.insert_text((MARGIN, PAGE_H - 16), footer, fontsize=7, color=(0.4, 0.4, 0.4))


def _add_note(page: fitz.Page, rect: fitz.Rect, text: str, severity: str = "Info"):
    page.draw_rect(rect, color=_stroke_color(severity), fill=_severity_color(severity), width=0.8)
    _insert_textbox(page, rect + (5, 4, -5, -4), text, fontsize=8)


def _table_page(doc: fitz.Document, title: str, headers: list[str], rows: list[list[str]], footer: str, col_widths: list[float] | None = None):
    col_widths = col_widths or [1 / len(headers)] * len(headers)
    usable_w = PAGE_W - 2 * MARGIN
    header_h = 18
    row_h = 30
    max_rows = int((PAGE_H - 92 - 42) // row_h)
    chunks = [rows[i:i + max_rows] for i in range(0, len(rows), max_rows)] or [[]]

    for chunk_idx, chunk in enumerate(chunks, start=1):
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        _draw_header(page, title, f"Page {chunk_idx} of {len(chunks)}")
        y = 72
        x = MARGIN
        for h, cw in zip(headers, col_widths):
            w = usable_w * cw
            r = fitz.Rect(x, y, x + w, y + header_h)
            page.draw_rect(r, color=(0.2, 0.2, 0.2), fill=(0.88, 0.92, 0.96), width=0.5)
            _insert_textbox(page, r + (3, 2, -3, -2), h, fontsize=7.5)
            x += w
        y += header_h

        for row in chunk:
            x = MARGIN
            for cell, cw in zip(row, col_widths):
                w = usable_w * cw
                r = fitz.Rect(x, y, x + w, y + row_h)
                page.draw_rect(r, color=(0.75, 0.75, 0.75), width=0.3)
                _insert_textbox(page, r + (3, 2, -3, -2), str(cell)[:400], fontsize=7)
                x += w
            y += row_h
        _draw_footer(page, footer)


def _table_page_count(rows: list[list[str]]) -> int:
    row_h = 30
    max_rows = int((PAGE_H - 92 - 42) // row_h)
    return max(1, math.ceil(len(rows) / max_rows)) if max_rows else 1


def build_issue_index_pdf(issues: list[Issue], source_pdf_page_count: int, config: dict[str, Any]) -> fitz.Document:
    doc = fitz.open()
    packet_settings = config.get("packet", {})
    include_issue_index = bool(packet_settings.get("include_issue_index", True))
    include_critical_major_list = bool(packet_settings.get("include_critical_major_list", True))

    sev = Counter(i.severity for i in issues)
    rule = Counter(i.rule_id for i in issues)
    sheet = Counter(i.sheet_number for i in issues)

    cover = doc.new_page(width=PAGE_W, height=PAGE_H)
    _draw_header(cover, "Natural Gas Drawing QA Review Packet", "Single-source PDF issue index, marked-up drawings, and reference evidence")
    y = 92
    _add_note(
        cover,
        fitz.Rect(MARGIN, y, PAGE_W - MARGIN, y + 58),
        "All markups and findings in this packet are draft automated review findings. They must be accepted, edited, or rejected by a qualified reviewer before being used as formal engineering comments.",
        "Major",
    )
    y += 80

    cover.insert_text((MARGIN, y), f"Draft issue count: {len(issues)}", fontsize=12)
    y += 22
    cover.insert_text((MARGIN, y), "Severity counts:", fontsize=11)
    y += 18
    for s in ["Critical", "Major", "Minor", "Info"]:
        cover.insert_text((MARGIN + 18, y), f"{s}: {sev.get(s, 0)}", fontsize=10)
        y += 15

    y += 12
    cover.insert_text((MARGIN, y), "Top rules:", fontsize=11)
    y += 16
    for k, v in rule.most_common(8):
        cover.insert_text((MARGIN + 18, y), f"{k}: {v}", fontsize=9)
        y += 13

    y += 12
    cover.insert_text((MARGIN, y), "Highest issue sheets:", fontsize=11)
    y += 16
    for k, v in sheet.most_common(8):
        cover.insert_text((MARGIN + 18, y), f"{k}: {v}", fontsize=9)
        y += 13

    y += 12
    cover.insert_text((MARGIN, y), f"Packet mode: {packet_settings.get('packet_mode', 'internal_qa')}", fontsize=9)
    y += 13
    cover.insert_text((MARGIN, y), f"Finding scope: {packet_settings.get('finding_scope', 'accepted_only')}", fontsize=9)

    _draw_footer(cover, "Section 1: Packet summary")

    # Issue index pages.
    headers = ["ID", "Sev", "Sheet", "Rule", "Finding / Action"]
    rows = []
    for i in issues:
        rows.append([
            i.issue_id,
            i.severity,
            i.sheet_number,
            i.rule_id,
            f"{i.subject}: {i.message}",
        ])
    if include_issue_index:
        _table_page(
            doc,
            "Issue Index",
            headers,
            rows,
            "Section 2: Issue index. Open the marked-up drawing pages that follow to review visual markups.",
            col_widths=[0.10, 0.08, 0.10, 0.22, 0.50],
        )

    # Critical / major quick list.
    crit = [i for i in issues if i.severity in {"Critical", "Major"}]
    rows = [[i.issue_id, i.severity, i.sheet_number, i.found_text, i.message] for i in crit]
    if include_critical_major_list:
        _table_page(
            doc,
            "Critical and Major Findings",
            ["ID", "Sev", "Sheet", "Found", "Message"],
            rows,
            "Section 3: Priority findings.",
            col_widths=[0.10, 0.08, 0.10, 0.14, 0.58],
        )

    return doc


def _load_reference_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        return read_table(path)
    except Exception:
        return [], []


def build_reference_pdf(references: dict[str, list[ReferenceRecord]], issues: list[Issue]) -> fitz.Document:
    doc = fitz.open()

    # Map issue text to issue list for row highlighting.
    issues_by_text: dict[str, list[Issue]] = defaultdict(list)
    for issue in issues:
        key = re.sub(r"[\s_-]+", "", str(issue.found_text or "").upper())
        if key:
            issues_by_text[key].append(issue)

    grouped_files: dict[str, list[ReferenceRecord]] = defaultdict(list)
    for recs in references.values():
        for rec in recs:
            grouped_files[rec.source_file].append(rec)

    if not grouped_files:
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        _draw_header(page, "Reference Inputs", "No reference CSV/XLSX files were provided for this run.")
        _add_note(page, fitz.Rect(MARGIN, 86, PAGE_W - MARGIN, 140), "Add drawing index, valve list, line list, instrument index, and equipment list files to include them in this packet.", "Info")
        return doc

    for file_path_str, recs in grouped_files.items():
        path = Path(file_path_str)
        headers, rows = _load_reference_table(path)
        if not headers:
            continue

        # Limit columns to readable PDF width. Keep key columns first.
        preferred = ["sheet_number", "drawing_number", "tag", "valve_tag", "line_number", "instrument_tag", "equipment_tag", "type", "size", "service", "revision", "date", "issue_date", "status"]
        chosen = []
        lower_map = {h.lower(): h for h in headers}
        for p in preferred:
            if p in lower_map and lower_map[p] not in chosen:
                chosen.append(lower_map[p])
        for h in headers:
            if h not in chosen and len(chosen) < 7:
                chosen.append(h)
        if not chosen:
            chosen = headers[:7]

        key_candidates = ["sheet_number", "drawing_number", "tag", "valve_tag", "line_number", "instrument_tag", "equipment_tag"]
        key_col = None
        for k in key_candidates:
            for h in headers:
                if h.lower().replace(" ", "_") == k:
                    key_col = h
                    break
            if key_col:
                break
        key_col = key_col or chosen[0]

        title = f"Reference Input: {path.name}"
        usable_w = PAGE_W - 2 * MARGIN
        row_h = 26
        max_rows = int((PAGE_H - 96 - 38) // row_h)
        chunks = [rows[i:i + max_rows] for i in range(0, len(rows), max_rows)] or [[]]

        for chunk_idx, chunk in enumerate(chunks, start=1):
            page = doc.new_page(width=PAGE_W, height=PAGE_H)
            _draw_header(page, title, f"Rendered input file. Page {chunk_idx} of {len(chunks)}")
            y = 72
            widths = [0.12] + [(0.88 / len(chosen))] * len(chosen)
            cols = ["Row"] + chosen

            x = MARGIN
            for h, cw in zip(cols, widths):
                w = usable_w * cw
                r = fitz.Rect(x, y, x + w, y + 18)
                page.draw_rect(r, color=(0.2, 0.2, 0.2), fill=(0.88, 0.92, 0.96), width=0.5)
                _insert_textbox(page, r + (3, 2, -3, -2), h, fontsize=7)
                x += w
            y += 18

            for idx, row in enumerate(chunk, start=1 + (chunk_idx - 1) * max_rows):
                key_value = str(row.get(key_col, "") or "")
                norm_key = re.sub(r"[\s_-]+", "", key_value.upper())
                related = issues_by_text.get(norm_key, [])
                fill = _severity_color(related[0].severity) if related else None

                x = MARGIN
                vals = [str(idx + 1)] + [str(row.get(c, "") or "") for c in chosen]
                for cell, cw in zip(vals, widths):
                    w = usable_w * cw
                    r = fitz.Rect(x, y, x + w, y + row_h)
                    page.draw_rect(r, color=(0.75, 0.75, 0.75), fill=fill, width=0.3)
                    _insert_textbox(page, r + (3, 2, -3, -2), cell[:250], fontsize=6.8)
                    x += w

                if related:
                    note = "; ".join(i.issue_id for i in related[:4])
                    page.insert_text((PAGE_W - MARGIN - 90, y + row_h - 5), note, fontsize=6, color=(0.65, 0, 0))
                y += row_h

            _draw_footer(page, "Reference rows shaded when tied to an automated finding.")

    return doc


def _docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml")
        root = ET.fromstring(xml)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        texts = [node.text or "" for node in root.findall(".//w:t", ns)]
        return " ".join(texts)
    except Exception:
        return "DOCX text could not be extracted. Open the source file directly if this reference is needed."


def _text_pages_from_content(title: str, content: str) -> fitz.Document:
    doc = fitz.open()
    lines: list[str] = []
    for paragraph in re.split(r"\n{2,}", content or ""):
        lines.extend(_wrap(paragraph, 112))
        lines.append("")
    if not lines:
        lines = ["No text content was extracted."]
    page = None
    y = 0
    for line in lines:
        if page is None or y > PAGE_H - 48:
            page = doc.new_page(width=PAGE_W, height=PAGE_H)
            _draw_header(page, title, "Rendered text reference")
            y = 78
        page.insert_text((MARGIN, y), line[:180], fontsize=8)
        y += 12
    return doc


def build_supplemental_reference_pdf(reference_files: list[Path]) -> fitz.Document:
    doc = fitz.open()
    for path in reference_files:
        path = Path(path)
        divider = doc.new_page(width=PAGE_W, height=PAGE_H)
        _draw_header(divider, f"Reference File: {path.name}", "Supplemental reference evidence")
        _add_note(
            divider,
            fitz.Rect(MARGIN, 88, PAGE_W - MARGIN, 142),
            "This file was attached to the project as reference evidence. Structured CSV/XLSX references are rendered separately with issue-row highlighting when applicable.",
            "Info",
        )
        _draw_footer(divider, "Supplemental reference input")
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            try:
                ref_doc = fitz.open(path)
                doc.insert_pdf(ref_doc)
                ref_doc.close()
            except Exception:
                error_doc = _text_pages_from_content(path.name, f"PDF could not be rendered: {path}")
                doc.insert_pdf(error_doc)
                error_doc.close()
        elif suffix == ".docx":
            text_doc = _text_pages_from_content(path.name, _docx_text(path))
            doc.insert_pdf(text_doc)
            text_doc.close()
        elif suffix == ".txt":
            text_doc = _text_pages_from_content(path.name, path.read_text(encoding="utf-8", errors="replace"))
            doc.insert_pdf(text_doc)
            text_doc.close()
    return doc


def _add_issue_index_links(
    packet: fitz.Document,
    issues: list[Issue],
    first_link_page_index: int,
    last_link_page_index: int,
    drawing_start_page_index: int,
) -> None:
    if not issues or last_link_page_index < first_link_page_index:
        return

    for issue in issues:
        if issue.page_number < 1:
            continue
        target_page_index = drawing_start_page_index + issue.page_number - 1
        if target_page_index >= packet.page_count:
            continue
        for page_index in range(first_link_page_index, last_link_page_index + 1):
            page = packet[page_index]
            try:
                matches = page.search_for(issue.issue_id)
            except Exception:
                matches = []
            for rect in matches:
                link_rect = fitz.Rect(rect)
                link_rect.x0 = max(0, link_rect.x0 - 1)
                link_rect.y0 = max(0, link_rect.y0 - 1)
                link_rect.x1 = min(page.rect.x1, link_rect.x1 + 4)
                link_rect.y1 = min(page.rect.y1, link_rect.y1 + 2)
                try:
                    page.insert_link({"kind": fitz.LINK_GOTO, "from": link_rect, "page": target_page_index})
                except Exception:
                    continue


def _set_packet_toc(
    packet: fitz.Document,
    issues: list[Issue],
    issue_index_page_num: int | None,
    critical_major_page_num: int | None,
    drawing_divider_page_num: int,
    drawing_start_page_num: int,
    ref_divider_page_num: int,
    source_map_page_num: int,
) -> None:
    toc: list[list[Any]] = [[1, "Cover and Review Disclaimer", 1]]
    if issue_index_page_num:
        toc.append([1, "Issue Index", issue_index_page_num])
    if critical_major_page_num:
        toc.append([1, "Critical and Major Findings", critical_major_page_num])
    toc.append([1, "Marked-Up Drawing Set", drawing_divider_page_num])

    issues_by_page: dict[int, list[Issue]] = defaultdict(list)
    for issue in issues:
        if issue.page_number >= 1:
            issues_by_page[issue.page_number].append(issue)
    for drawing_page_num, page_issues in sorted(issues_by_page.items()):
        target_page_num = drawing_start_page_num + drawing_page_num - 1
        if target_page_num > packet.page_count:
            continue
        sheet = page_issues[0].sheet_number or f"Drawing page {drawing_page_num}"
        toc.append([2, f"{sheet} - {len(page_issues)} finding(s)", target_page_num])

    toc.append([1, "Rendered Reference Inputs", ref_divider_page_num])
    toc.append([1, "Packet Source Map", source_map_page_num])
    try:
        packet.set_toc(toc)
    except Exception:
        pass


def build_single_review_packet(
    annotated_doc: fitz.Document,
    issues: list[Issue],
    references: dict[str, list[ReferenceRecord]],
    out_path: Path,
    config: dict[str, Any],
    supplemental_reference_files: list[Path] | None = None,
) -> None:
    """
    Create one single PDF containing:
    1. Cover and issue index
    2. The fully marked-up drawing set
    3. Rendered reference input files with issue-related rows highlighted
    """
    packet = fitz.open()
    packet_settings = config.get("packet", {})
    include_issue_index = bool(packet_settings.get("include_issue_index", True))
    include_critical_major_list = bool(packet_settings.get("include_critical_major_list", True))
    index_doc = build_issue_index_pdf(issues, annotated_doc.page_count, config)
    issue_index_rows = [[i.issue_id, i.severity, i.sheet_number, i.rule_id, f"{i.subject}: {i.message}"] for i in issues]
    issue_index_page_count = _table_page_count(issue_index_rows) if include_issue_index else 0
    issue_index_page_num = 2 if include_issue_index else None
    critical_major_page_num = 2 + issue_index_page_count if include_critical_major_list else None
    packet.insert_pdf(index_doc)
    index_doc.close()

    # Section divider before drawings.
    drawing_divider_page_num = packet.page_count + 1
    divider = packet.new_page(width=PAGE_W, height=PAGE_H)
    _draw_header(divider, "Marked-Up Drawing Set", "The pages after this divider are the Bluebeam-reviewable drawing pages with draft automated markups.")
    _add_note(divider, fitz.Rect(MARGIN, 90, PAGE_W - MARGIN, 150), "Use this section to review the actual visual markups. The issue index at the front helps you find issues by ID, sheet, severity, and rule. Issue IDs in the front matter link to drawing pages when the PDF viewer supports internal links.", "Info")
    _draw_footer(divider, "Section 4: Marked-up drawings")

    drawing_start_page_index = packet.page_count
    drawing_start_page_num = drawing_start_page_index + 1
    packet.insert_pdf(annotated_doc)

    # References section.
    ref_divider_page_num = packet.page_count + 1
    ref_divider = packet.new_page(width=PAGE_W, height=PAGE_H)
    _draw_header(ref_divider, "Rendered Reference Inputs", "Input lists printed into the packet so all evidence is available in one PDF.")
    _add_note(ref_divider, fitz.Rect(MARGIN, 90, PAGE_W - MARGIN, 150), "Reference-list rows related to findings are shaded. CSV/Excel files are still exported, but this PDF is intended to be the single review source.", "Info")
    _draw_footer(ref_divider, "Section 5: Reference inputs")

    ref_doc = build_reference_pdf(references, issues)
    packet.insert_pdf(ref_doc)
    ref_doc.close()

    supplemental_reference_files = supplemental_reference_files or []
    if supplemental_reference_files:
        supplemental_doc = build_supplemental_reference_pdf(supplemental_reference_files)
        packet.insert_pdf(supplemental_doc)
        supplemental_doc.close()

    # Appendix / source map.
    source_map_page_num = packet.page_count + 1
    page = packet.new_page(width=PAGE_W, height=PAGE_H)
    _draw_header(page, "Packet Source Map", "How to use this single PDF")
    y = 88
    bullets = [
        "Start with the Issue Index to triage findings by severity, sheet, and rule.",
        "Use PDF bookmarks for section navigation and drawing-page finding clusters.",
        "Click issue IDs in the front matter to jump to the related marked-up drawing page when supported by the viewer.",
        "Use the Marked-Up Drawing Set section to review the actual visual comments.",
        "Use the Rendered Reference Inputs section to verify list-driven issues without opening Excel.",
        "CSV/Excel/HTML outputs are optional support files, not the primary review source.",
        "All findings remain draft automated findings until accepted by a reviewer.",
    ]
    for b in bullets:
        for line in _wrap("- " + b, 110):
            page.insert_text((MARGIN, y), line, fontsize=10)
            y += 16
        y += 4
    _draw_footer(page, "Section 6: Source map")

    _add_issue_index_links(
        packet,
        issues,
        first_link_page_index=0,
        last_link_page_index=max(0, drawing_divider_page_num - 2),
        drawing_start_page_index=drawing_start_page_index,
    )
    _set_packet_toc(
        packet,
        issues,
        issue_index_page_num=issue_index_page_num,
        critical_major_page_num=critical_major_page_num,
        drawing_divider_page_num=drawing_divider_page_num,
        drawing_start_page_num=drawing_start_page_num,
        ref_divider_page_num=ref_divider_page_num,
        source_map_page_num=source_map_page_num,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    packet.save(out_path, garbage=4, deflate=True)
    packet.close()
