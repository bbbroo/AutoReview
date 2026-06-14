from __future__ import annotations

from collections import defaultdict
from typing import Any
import re

from .base import RuleContext
from ..models import RectData, Hit
from ..config import is_rule_enabled
from ..reference import normalize_value


def _page_text_lookup(ctx: RuleContext) -> dict[int, str]:
    return {idx: text for idx, _, text in ctx.page_texts}


def _add(ctx: RuleContext, *args, **kwargs):
    return ctx.issue_builder.add(*args, **kwargs)


def _ref_map(records):
    return {r.normalized: r for r in records}


def _hits_map(hits: list[Hit]):
    out = defaultdict(list)
    for h in hits:
        out[h.normalized].append(h)
    return out


def _sheet_set(ctx: RuleContext) -> set[str]:
    return {pi.sheet_number for pi in ctx.page_infos if pi.sheet_number}


def _rfi_candidate(ctx: RuleContext, message: str) -> str:
    words = [w.lower() for w in ctx.config.get("review", {}).get("rfi_keywords", [])]
    return "Yes" if any(w in message.lower() for w in words) else "No"


def check_text_quality(ctx: RuleContext):
    if not is_rule_enabled(ctx.config, "LOW_SEARCHABLE_TEXT") and not is_rule_enabled(ctx.config, "RASTER_ONLY_PAGE"):
        return
    min_words = int(ctx.config.get("pdf", {}).get("min_words_per_page", 20))
    for pi in ctx.page_infos:
        if is_rule_enabled(ctx.config, "LOW_SEARCHABLE_TEXT") and pi.word_count < min_words:
            _add(ctx, "LOW_SEARCHABLE_TEXT", "NGQA - Low searchable text",
                 f"Page has only {pi.word_count} searchable words. Run Bluebeam OCR before relying on automated tag checks.",
                 page_number=pi.page_number, sheet_number=pi.sheet_number, found_text=str(pi.word_count), confidence=0.95)
        if is_rule_enabled(ctx.config, "RASTER_ONLY_PAGE") and pi.raster_only:
            _add(ctx, "RASTER_ONLY_PAGE", "NGQA - Raster-only or scan-like page",
                 "Page appears to contain images with little searchable text. OCR is likely required.",
                 page_number=pi.page_number, sheet_number=pi.sheet_number, found_text=str(pi.image_count), confidence=0.95)
        if is_rule_enabled(ctx.config, "GARBLED_OCR_TEXT") and pi.garbled_text_warning:
            _add(ctx, "GARBLED_OCR_TEXT", "NGQA - Possible garbled OCR text",
                 f"Text quality score is {pi.text_quality_score}. Verify OCR quality before trusting automated checks.",
                 page_number=pi.page_number, sheet_number=pi.sheet_number, found_text=str(pi.text_quality_score), confidence=0.80)


def check_drawing_index(ctx: RuleContext):
    if not is_rule_enabled(ctx.config, "DRAWING_INDEX_RECONCILIATION"):
        return
    refs = _ref_map(ctx.references.get("drawing_index", []))
    if not refs:
        return
    found = _sheet_set(ctx)
    for sheet, rec in sorted(refs.items()):
        if sheet not in found:
            _add(ctx, "DRAWING_INDEX_RECONCILIATION", "NGQA - Sheet listed in index but not found",
                 f"Sheet {rec.raw} exists in the drawing index but was not detected in the PDF set. Verify missing sheet, OCR issue, or title block extraction.",
                 page_number=1, sheet_number=rec.raw, found_text=rec.raw, confidence=0.90)
    for sheet in sorted(found - set(refs)):
        if sheet.startswith("PAGE-"):
            continue
        _add(ctx, "DRAWING_INDEX_RECONCILIATION", "NGQA - PDF sheet not listed in drawing index",
             f"Sheet {sheet} was detected in the PDF but was not found in the drawing index. Verify whether the drawing index needs to be updated.",
             page_number=1, sheet_number=sheet, found_text=sheet, severity="Minor", confidence=0.80)

    # Compare revision/title/status when available.
    pages_by_sheet = {pi.sheet_number: pi for pi in ctx.page_infos}
    for sheet, rec in refs.items():
        pi = pages_by_sheet.get(sheet)
        if not pi:
            continue
        rev_ref = rec.fields.get("revision", "")
        if rev_ref and pi.revision and rev_ref.strip().upper() not in pi.revision.upper():
            _add(ctx, "REVISION_MISMATCH", "NGQA - Revision mismatch",
                 f"Sheet {sheet} title block revision appears to be '{pi.revision}', but drawing index says '{rev_ref}'.",
                 page_number=pi.page_number, sheet_number=sheet, found_text=pi.revision, confidence=0.80)
        title_ref = rec.fields.get("sheet_title", "")
        if title_ref and pi.sheet_title and title_ref.strip().upper() not in pi.sheet_title.upper() and pi.sheet_title.strip().upper() not in title_ref.upper():
            _add(ctx, "SHEET_TITLE_MISMATCH", "NGQA - Sheet title mismatch",
                 f"Sheet {sheet} title block title appears to differ from drawing index. Title block: '{pi.sheet_title}'. Index: '{title_ref}'.",
                 page_number=pi.page_number, sheet_number=sheet, found_text=pi.sheet_title, confidence=0.70)


def check_title_block(ctx: RuleContext):
    if not is_rule_enabled(ctx.config, "TITLE_BLOCK_MISSING_FIELD"):
        return
    required = ["sheet_number", "revision", "issue_date", "checked_by"]
    for pi in ctx.page_infos:
        fields = pi.title_block_fields or {}
        for field in required:
            val = (fields.get(field) or "").strip()
            if not val:
                _add(ctx, "TITLE_BLOCK_MISSING_FIELD", "NGQA - Missing title block field",
                     f"Title block field '{field}' appears blank or was not extracted. Verify manually.",
                     page_number=pi.page_number, sheet_number=pi.sheet_number, found_text=field, confidence=0.60)


def check_duplicate_sheets(ctx: RuleContext):
    if not is_rule_enabled(ctx.config, "DUPLICATE_SHEET_NUMBER"):
        return
    by_sheet = defaultdict(list)
    for pi in ctx.page_infos:
        if not pi.sheet_number.startswith("PAGE-"):
            by_sheet[pi.sheet_number].append(pi)
    for sheet, rows in by_sheet.items():
        if len(rows) > 1:
            pages = ", ".join(str(r.page_number) for r in rows)
            _add(ctx, "DUPLICATE_SHEET_NUMBER", "NGQA - Duplicate sheet number",
                 f"Sheet number {sheet} appears on multiple PDF pages: {pages}. Verify duplicate sheet, title block, or extraction issue.",
                 page_number=rows[0].page_number, sheet_number=sheet, found_text=sheet, confidence=0.90)


def reconcile_tags(ctx: RuleContext, hit_kind: str, ref_name: str, rule_id: str, label: str, discipline: str):
    if not is_rule_enabled(ctx.config, rule_id):
        return
    refs = _ref_map(ctx.references.get(ref_name, []))
    if not refs:
        return
    hits = _hits_map(ctx.hits.get(hit_kind, []))
    ref_values = set(refs)
    hit_values = set(hits)

    max_per_tag = int(ctx.config.get("review", {}).get("suppress_repeated_findings_per_tag", 5))
    for val in sorted(hit_values - ref_values):
        for hit in hits[val][:max_per_tag]:
            msg = f"{label} '{hit.text}' was found on sheet {hit.sheet_number}, but was not found in the provided {ref_name.replace('_', ' ')}."
            _add(ctx, rule_id, f"NGQA - {label} not in reference list", msg,
                 page_number=hit.page_number, sheet_number=hit.sheet_number, found_text=hit.text,
                 context=hit.context, rect=hit.rect, discipline=discipline, rfi_candidate=_rfi_candidate(ctx, msg), confidence=0.85)
    for val in sorted(ref_values - hit_values):
        rec = refs[val]
        msg = f"{label} '{rec.raw}' exists in the provided {ref_name.replace('_', ' ')}, but was not found in searchable PDF text."
        _add(ctx, rule_id, f"NGQA - {label} listed but not found on drawings", msg,
             page_number=1, sheet_number="Drawing Set", found_text=rec.raw, discipline=discipline, rfi_candidate=_rfi_candidate(ctx, msg), confidence=0.75)


def check_reference_reconciliations(ctx: RuleContext):
    reconcile_tags(ctx, "Valve", "valve_list", "VALVE_TAG_RECONCILIATION", "Valve tag", "Mechanical")
    reconcile_tags(ctx, "Line", "line_list", "LINE_NUMBER_RECONCILIATION", "Line number", "Mechanical")
    reconcile_tags(ctx, "Instrument", "instrument_index", "INSTRUMENT_TAG_RECONCILIATION", "Instrument tag", "I&C")
    reconcile_tags(ctx, "Equipment", "equipment_list", "EQUIPMENT_TAG_RECONCILIATION", "Equipment tag", "Mechanical")


def check_repeated_tags(ctx: RuleContext):
    if not is_rule_enabled(ctx.config, "REPEATED_TAG_REVIEW"):
        return
    for kind in ["Valve", "Instrument", "Equipment"]:
        by_tag = _hits_map(ctx.hits.get(kind, []))
        for tag, rows in by_tag.items():
            sheets = sorted({h.sheet_number for h in rows})
            if len(sheets) >= 3:
                h = rows[0]
                _add(ctx, "REPEATED_TAG_REVIEW", f"NGQA - Repeated {kind} tag review",
                     f"{kind} tag '{h.text}' appears on multiple sheets: {', '.join(sheets[:12])}. This may be valid, but verify it is not a duplicate tag conflict.",
                     page_number=h.page_number, sheet_number=h.sheet_number, found_text=h.text,
                     context=h.context, rect=h.rect, severity="Info", confidence=0.55)


def check_pressure_and_code(ctx: RuleContext):
    text_lookup = _page_text_lookup(ctx)

    if is_rule_enabled(ctx.config, "PRESSURE_CONSISTENCY") or is_rule_enabled(ctx.config, "TEST_PRESSURE_CHECK"):
        pressure_re = re.compile(ctx.config["regex"]["pressure"], re.IGNORECASE)
        by_label = defaultdict(list)
        for page_index, sheet_number, text in ctx.page_texts:
            for m in pressure_re.finditer(text):
                label = re.sub(r"\s+", " ", m.group("label").upper())
                value = f"{m.group('value')} {m.group('unit').upper()}"
                context = re.sub(r"\s+", " ", m.group(0)).strip()
                by_label[label].append((page_index, sheet_number, value, context))

        for label, rows in by_label.items():
            values = sorted({r[2] for r in rows})
            if len(values) > 1:
                rule_id = "TEST_PRESSURE_CHECK" if "TEST" in label else "PRESSURE_CONSISTENCY"
                _add(ctx, rule_id, f"NGQA - {label.title()} conflict",
                     f"Multiple {label} values were found: {', '.join(values)}. Verify consistency against design basis, line list, and equipment ratings.",
                     page_number=rows[0][0] + 1, sheet_number=rows[0][1], found_text=", ".join(values), confidence=0.80)

    if is_rule_enabled(ctx.config, "CODE_CONSISTENCY"):
        code_re = re.compile(ctx.config["regex"]["code"], re.IGNORECASE)
        codes = defaultdict(list)
        for page_index, sheet_number, text in ctx.page_texts:
            for m in code_re.finditer(text):
                codes[m.group(0).upper()].append((page_index, sheet_number))
        if len(codes) > 1:
            _add(ctx, "CODE_CONSISTENCY", "NGQA - Multiple ASME B31 code references",
                 f"Multiple code references found: {', '.join(sorted(codes))}. Verify drawing notes match the project design basis.",
                 page_number=1, sheet_number="Drawing Set", found_text=", ".join(sorted(codes)), confidence=0.80)


def check_material_and_coating(ctx: RuleContext):
    material_re = re.compile(ctx.config["regex"]["material"], re.IGNORECASE)
    coating_re = re.compile(ctx.config["regex"]["coating"], re.IGNORECASE)

    for page_index, sheet_number, text in ctx.page_texts:
        if is_rule_enabled(ctx.config, "MATERIAL_SPEC_CHECK"):
            mats = sorted({m.group(0).upper() for m in material_re.finditer(text)})
            if len(mats) > 3:
                _add(ctx, "MATERIAL_SPEC_CHECK", "NGQA - Multiple material/spec references",
                     f"Multiple material/spec references found on {sheet_number}: {', '.join(mats[:10])}. Verify consistency with line/spec list.",
                     page_number=page_index+1, sheet_number=sheet_number, found_text=", ".join(mats[:10]), confidence=0.65)
        if is_rule_enabled(ctx.config, "COATING_NOTE_CHECK"):
            coats = sorted({m.group(0).upper() for m in coating_re.finditer(text)})
            if coats:
                _add(ctx, "COATING_NOTE_CHECK", "NGQA - Coating/CP note review",
                     f"Coating/CP-related terms found on {sheet_number}: {', '.join(coats[:10])}. Verify coating and corrosion notes are consistent with project standards.",
                     page_number=page_index+1, sheet_number=sheet_number, found_text=", ".join(coats[:10]), severity="Info", confidence=0.60)


def check_regulator_relief_tiein(ctx: RuleContext):
    page_text = {idx: text.lower() for idx, _, text in ctx.page_texts}

    if is_rule_enabled(ctx.config, "REGULATOR_STATION_CHECKLIST"):
        terms = [t.lower() for t in ctx.config.get("terms", {}).get("regulator_station", [])]
        combined = "\n".join(page_text.values())
        regulator_present = "regulator" in combined or any(hits for hits in [ctx.hits.get("Valve", [])] if hits)
        if regulator_present:
            for term in terms:
                if term not in combined:
                    _add(ctx, "REGULATOR_STATION_CHECKLIST", "NGQA - Regulator station checklist review",
                         f"Regulator-station-related drawing set appears to be present, but term '{term}' was not found in searchable text. Verify whether this function/item is required and shown.",
                         page_number=1, sheet_number="Drawing Set", found_text=term, confidence=0.60)

    if is_rule_enabled(ctx.config, "RELIEF_VENT_CHECKLIST"):
        relief_terms = [t.lower() for t in ctx.config.get("terms", {}).get("relief_vent", [])]
        detail_re = re.compile(ctx.config["regex"]["detail_ref"], re.IGNORECASE)
        for page_index, sheet_number, text in ctx.page_texts:
            low = text.lower()
            if any(t.lower() in low for t in relief_terms) and not detail_re.search(text):
                _add(ctx, "RELIEF_VENT_CHECKLIST", "NGQA - Relief/vent detail reference review",
                     f"Relief/vent/blowdown-related text was found on {sheet_number}, but no obvious detail reference was detected on the same page. Verify vent termination/detail references.",
                     page_number=page_index+1, sheet_number=sheet_number, found_text="relief/vent/blowdown", confidence=0.75)

    if is_rule_enabled(ctx.config, "TIE_IN_CHECKLIST"):
        required = [t.lower() for t in ctx.config.get("terms", {}).get("tie_in_required", [])]
        for hit in ctx.hits.get("TieIn", []):
            text = page_text.get(hit.page_index, "")
            missing = [term for term in required if term not in text]
            if missing:
                _add(ctx, "TIE_IN_CHECKLIST", "NGQA - Tie-in checklist review",
                     f"Tie-in '{hit.text}' was found, but these supporting terms were not found on the same page: {', '.join(missing)}. Verify shutdown, purge/blowdown, test boundary, existing line, and detail information.",
                     page_number=hit.page_number, sheet_number=hit.sheet_number, found_text=hit.text,
                     context=hit.context, rect=hit.rect, rfi_candidate="Yes", confidence=0.75)


def check_references(ctx: RuleContext):
    sheets = _sheet_set(ctx)
    if is_rule_enabled(ctx.config, "DETAIL_REFERENCE_CHECK"):
        detail_re = re.compile(ctx.config["regex"]["detail_ref"], re.IGNORECASE)
        for page_index, sheet_number, text in ctx.page_texts:
            for m in detail_re.finditer(text):
                target = normalize_value(m.group("sheet"))
                if target not in sheets:
                    _add(ctx, "DETAIL_REFERENCE_CHECK", "NGQA - Detail reference target sheet not found",
                         f"Detail reference {m.group(0)} was found on {sheet_number}, but target sheet {target} was not detected in the PDF set.",
                         page_number=page_index+1, sheet_number=sheet_number, found_text=m.group(0), confidence=0.90)

    if is_rule_enabled(ctx.config, "SECTION_REFERENCE_CHECK"):
        section_re = re.compile(ctx.config["regex"]["section_ref"], re.IGNORECASE)
        for page_index, sheet_number, text in ctx.page_texts:
            for m in section_re.finditer(text):
                target = normalize_value(m.group("sheet"))
                if target not in sheets:
                    _add(ctx, "SECTION_REFERENCE_CHECK", "NGQA - Section reference target sheet not found",
                         f"Section/reference {m.group(0)} was found on {sheet_number}, but target sheet {target} was not detected in the PDF set.",
                         page_number=page_index+1, sheet_number=sheet_number, found_text=m.group(0), confidence=0.85)


def advanced_safe_hooks(ctx: RuleContext):
    # AI comment drafts: safe offline rewrite template only.
    if is_rule_enabled(ctx.config, "AI_COMMENT_DRAFTS"):
        for issue in ctx.issue_builder.issues:
            if not issue.ai_suggested_comment:
                issue.ai_suggested_comment = (
                    f"Please review {issue.found_text or 'this item'} on sheet {issue.sheet_number}. "
                    f"{issue.message}"
                )

    if is_rule_enabled(ctx.config, "RFI_CANDIDATE_DETECTOR"):
        for issue in ctx.issue_builder.issues:
            if issue.rfi_candidate == "No" and _rfi_candidate(ctx, issue.message) == "Yes":
                issue.rfi_candidate = "Yes"

    # Symbol recognition stub: creates one documentation issue if profile suggests P&ID.
    if is_rule_enabled(ctx.config, "SYMBOL_RECOGNITION_STUB"):
        _add(ctx, "SYMBOL_RECOGNITION_STUB", "NGQA - Symbol recognition hook available",
             "Symbol recognition is scaffolded as an extension point. Current offline release does not perform computer vision counting; use text/tag reconciliation first.",
             page_number=1, sheet_number="Drawing Set", found_text="symbol-recognition-hook", severity="Info", confidence=0.40, source="extension_hook")

    if is_rule_enabled(ctx.config, "ASSET_REGISTER_DRAFT"):
        # No issue needed; asset register report is generated from hits later.
        pass


def run_all_rules(ctx: RuleContext) -> list:
    check_text_quality(ctx)
    check_drawing_index(ctx)
    check_title_block(ctx)
    check_duplicate_sheets(ctx)
    check_reference_reconciliations(ctx)
    check_repeated_tags(ctx)
    check_pressure_and_code(ctx)
    check_material_and_coating(ctx)
    check_regulator_relief_tiein(ctx)
    check_references(ctx)
    advanced_safe_hooks(ctx)
    return ctx.issue_builder.issues
