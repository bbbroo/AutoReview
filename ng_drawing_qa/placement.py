from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import csv
import math
import re

import fitz

from .models import Issue


EXACT_HIT = "exact_hit"
RESOLVED_TEXT_SEARCH = "resolved_text_search"
TITLE_BLOCK_REGION = "title_block_region"
PAGE_LEVEL = "page_level"
REFERENCE_ONLY = "reference_only"
UNPLACED = "unplaced"


@dataclass
class PlacementAttempt:
    issue_id: str
    rule_id: str
    page_number: int
    found_text: str
    placement_type: str
    coordinate_source: str
    placement_confidence: float
    resolved_match_text: str = ""
    placement_warning: str = ""
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0


def has_valid_coordinates(issue: Issue) -> bool:
    values = [issue.x0, issue.y0, issue.x1, issue.y1]
    return all(math.isfinite(float(value)) for value in values) and issue.x1 > issue.x0 and issue.y1 > issue.y0


def placement_counts(issues: list[Issue]) -> dict[str, int]:
    counts = {
        "coordinate_backed_markups": 0,
        "exact_location_markups": 0,
        "resolved_search_markups": 0,
        "title_block_region_markups": 0,
        "fallback_page_callouts": 0,
        "reference_only_findings": 0,
        "unplaced_findings": 0,
    }
    for issue in issues:
        if issue.placement_type == EXACT_HIT:
            counts["coordinate_backed_markups"] += 1
            counts["exact_location_markups"] += 1
        elif issue.placement_type == RESOLVED_TEXT_SEARCH:
            counts["resolved_search_markups"] += 1
        elif issue.placement_type == TITLE_BLOCK_REGION:
            counts["title_block_region_markups"] += 1
        elif issue.placement_type == PAGE_LEVEL:
            counts["fallback_page_callouts"] += 1
        elif issue.placement_type == REFERENCE_ONLY:
            counts["reference_only_findings"] += 1
        elif issue.placement_type == UNPLACED:
            counts["unplaced_findings"] += 1
    return counts


def _set_issue_rect(issue: Issue, rect: fitz.Rect) -> None:
    issue.x0 = round(float(rect.x0), 2)
    issue.y0 = round(float(rect.y0), 2)
    issue.x1 = round(float(rect.x1), 2)
    issue.y1 = round(float(rect.y1), 2)


def _mark(
    issue: Issue,
    placement_type: str,
    coordinate_source: str,
    confidence: float,
    warning: str = "",
    resolved_match_text: str = "",
) -> None:
    issue.placement_type = placement_type
    issue.coordinate_source = coordinate_source
    issue.placement_confidence = round(float(confidence), 3)
    issue.original_found_text = issue.original_found_text or issue.found_text
    issue.resolved_match_text = resolved_match_text or issue.resolved_match_text
    issue.resolved_page_number = issue.page_number if issue.page_number else 0
    issue.placement_warning = warning


def _is_reference_only(issue: Issue) -> bool:
    subject = issue.subject.lower()
    message = issue.message.lower()
    return (
        "listed but not found" in subject
        or "listed in index but not found" in subject
        or "exists in the provided" in message and "not found in searchable pdf text" in message
        or issue.sheet_number == "Drawing Set" and "not found" in subject
    )


def _title_block_region(issue: Issue, doc: fitz.Document, config: dict[str, Any]) -> fitz.Rect | None:
    if issue.page_number < 1 or issue.page_number > doc.page_count:
        return None
    title_block_rules = {"TITLE_BLOCK_MISSING_FIELD", "REVISION_MISMATCH", "SHEET_TITLE_MISMATCH", "DUPLICATE_SHEET_NUMBER"}
    if issue.rule_id not in title_block_rules:
        return None
    page = doc[issue.page_number - 1]
    regions = config.get("title_block", {}).get("regions", {}).get("default", {})
    field = str(issue.found_text or "").lower().strip()
    frac = regions.get(field)
    if not frac:
        frac = regions.get("sheet_number") or regions.get("revision") or regions.get("status")
    if not frac or len(frac) != 4:
        # Right-lower title block fallback when configured fields are unavailable.
        frac = [0.62, 0.72, 0.98, 0.98]
    return fitz.Rect(
        page.rect.width * float(frac[0]),
        page.rect.height * float(frac[1]),
        page.rect.width * float(frac[2]),
        page.rect.height * float(frac[3]),
    )


def _candidate_terms(issue: Issue) -> list[str]:
    terms: list[str] = []
    raw = str(issue.found_text or "").strip()
    if raw:
        terms.append(raw)
        for piece in re.split(r"[,;/|]\s*", raw):
            piece = piece.strip()
            if piece and piece not in terms:
                terms.append(piece)
    context = str(issue.context or "")
    for token in re.findall(r"[A-Z]{1,6}[-_ ]?\d{2,6}[A-Z]?|[A-Z]{1,4}[-_ ]?\d{2,5}", context, re.IGNORECASE):
        if token not in terms:
            terms.append(token)
    return [term for term in terms if len(term) <= 80]


def _context_score(issue: Issue, page: fitz.Page, rect: fitz.Rect, term: str) -> float:
    score = 0.0
    context = str(issue.context or "")
    if context and term.lower() in context.lower():
        score += 0.2
    if issue.rule_id in {"TITLE_BLOCK_MISSING_FIELD", "REVISION_MISMATCH", "SHEET_TITLE_MISMATCH", "DUPLICATE_SHEET_NUMBER"}:
        if rect.y0 > page.rect.height * 0.55 and rect.x0 > page.rect.width * 0.45:
            score += 0.25
    if issue.sheet_number and term.upper().replace(" ", "") in issue.sheet_number.upper().replace(" ", ""):
        score += 0.1
    return score


def _search_page(issue: Issue, doc: fitz.Document) -> tuple[fitz.Rect, str, float] | None:
    if issue.page_number < 1 or issue.page_number > doc.page_count:
        return None
    page = doc[issue.page_number - 1]
    best: tuple[fitz.Rect, str, float] | None = None
    for term in _candidate_terms(issue):
        try:
            rects = list(page.search_for(term) or [])
        except Exception:
            rects = []
        for rect in rects:
            confidence = 0.72 + _context_score(issue, page, rect, term)
            if best is None or confidence > best[2]:
                best = (fitz.Rect(rect), term, min(0.95, confidence))
    return best


def resolve_issue_placements(doc: fitz.Document, issues: list[Issue], config: dict[str, Any]) -> list[PlacementAttempt]:
    attempts: list[PlacementAttempt] = []
    for issue in issues:
        issue.original_found_text = issue.original_found_text or issue.found_text
        if issue.page_number < 1 or issue.page_number > doc.page_count:
            _mark(issue, UNPLACED, "none", 0.0, "Finding page number is outside the drawing set.")
        elif _is_reference_only(issue):
            _mark(issue, REFERENCE_ONLY, "reference", 0.0, "Reference item was not found on the drawing; no exact drawing location is available.")
        elif has_valid_coordinates(issue):
            _mark(issue, EXACT_HIT, "rule_hit", 1.0, resolved_match_text=issue.found_text)
        else:
            title_rect = _title_block_region(issue, doc, config)
            if title_rect is not None:
                _set_issue_rect(issue, title_rect)
                _mark(issue, TITLE_BLOCK_REGION, "title_block_region", 0.82, resolved_match_text=issue.found_text)
            else:
                match = _search_page(issue, doc)
                if match:
                    rect, text, confidence = match
                    _set_issue_rect(issue, rect)
                    _mark(issue, RESOLVED_TEXT_SEARCH, "pdf_text_search", confidence, resolved_match_text=text)
                else:
                    _mark(issue, PAGE_LEVEL, "page_level", 0.35, "No reliable text rectangle found; showing page-level callout.")
        attempts.append(PlacementAttempt(
            issue_id=issue.issue_id,
            rule_id=issue.rule_id,
            page_number=issue.page_number,
            found_text=issue.original_found_text,
            placement_type=issue.placement_type,
            coordinate_source=issue.coordinate_source,
            placement_confidence=issue.placement_confidence,
            resolved_match_text=issue.resolved_match_text,
            placement_warning=issue.placement_warning,
            x0=issue.x0,
            y0=issue.y0,
            x1=issue.x1,
            y1=issue.y1,
        ))
    return attempts


def write_placement_debug_csv(path: Path, attempts: list[PlacementAttempt]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(asdict(attempts[0]).keys()) if attempts else [
        "issue_id", "rule_id", "page_number", "found_text", "placement_type",
        "coordinate_source", "placement_confidence", "resolved_match_text",
        "placement_warning", "x0", "y0", "x1", "y1",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for attempt in attempts:
            writer.writerow(asdict(attempt))
