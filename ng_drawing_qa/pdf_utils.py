from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
import re
import csv

import fitz

from .models import PageInfo, Hit, RectData
from .reference import normalize_value, apply_alias


def page_text(page: fitz.Page) -> str:
    try:
        return page.get_text("text") or ""
    except Exception:
        return ""


def page_words(page: fitz.Page) -> list[tuple]:
    try:
        return list(page.get_text("words") or [])
    except Exception:
        return []


def images_count(page: fitz.Page) -> int:
    try:
        return len(page.get_images(full=True) or [])
    except Exception:
        return 0


def text_quality_score(text: str, word_count: int) -> tuple[float, bool]:
    if word_count <= 0:
        return 0.0, False
    if not text:
        return 0.0, False
    chars = len(text)
    weird = sum(1 for c in text if ord(c) < 9 or (ord(c) > 126 and not c.isalnum() and not c.isspace()))
    ratio = weird / max(1, chars)
    score = max(0.0, min(1.0, 1.0 - ratio * 4.0))
    return score, ratio > 0.18


def rect_from_fraction(page: fitz.Page, frac: list[float]) -> fitz.Rect:
    x0, y0, x1, y1 = frac
    return fitz.Rect(
        page.rect.width * x0,
        page.rect.height * y0,
        page.rect.width * x1,
        page.rect.height * y1,
    )


def extract_region_text(page: fitz.Page, frac: list[float]) -> str:
    rect = rect_from_fraction(page, frac)
    try:
        text = page.get_text("text", clip=rect) or ""
        return re.sub(r"\s+", " ", text).strip()
    except Exception:
        return ""


def guess_sheet_number(text: str, page_number: int, sheet_regex: re.Pattern, normalizer) -> str:
    matches = sheet_regex.findall(text or "")
    if not matches:
        return f"PAGE-{page_number}"
    flat = []
    for m in matches:
        if isinstance(m, tuple):
            m = next((x for x in m if x), "")
        flat.append(normalizer(str(m)))
    # Prefer common drawing prefixes; avoid picking references inside notes by choosing last unique occurrence.
    seen = []
    for m in flat:
        if m and m not in seen:
            seen.append(m)
    return seen[-1] if seen else f"PAGE-{page_number}"


def extract_page_info(doc: fitz.Document, config: dict[str, Any]) -> tuple[list[PageInfo], list[tuple[int, str, str]]]:
    sheet_regex = re.compile(config["regex"]["sheet"], re.IGNORECASE)
    norm_cfg = config.get("normalization", {})
    def norm(v: str) -> str:
        return normalize_value(v, norm_cfg.get("fuzzy_tags", True), False)

    page_infos: list[PageInfo] = []
    page_texts: list[tuple[int, str, str]] = []
    tb_cfg = config.get("title_block", {})
    tb_enabled = tb_cfg.get("enabled", True)
    regions = tb_cfg.get("regions", {}).get("default", {})

    for page_index in range(doc.page_count):
        page = doc[page_index]
        text = page_text(page)
        words = page_words(page)
        word_count = len(words)
        img_count = images_count(page)
        score, garbled = text_quality_score(text, word_count)
        width, height = float(page.rect.width), float(page.rect.height)
        orientation = "landscape" if width >= height else "portrait"

        fields = {}
        if tb_enabled and regions:
            for field, frac in regions.items():
                fields[field] = extract_region_text(page, frac)

        title_sheet = fields.get("sheet_number", "")
        if title_sheet:
            found = sheet_regex.findall(title_sheet)
            sheet_number = norm(found[-1] if found else title_sheet.split()[-1])
        else:
            sheet_number = guess_sheet_number(text, page_index + 1, sheet_regex, norm)

        pi = PageInfo(
            page_index=page_index,
            page_number=page_index + 1,
            sheet_number=sheet_number,
            sheet_title=fields.get("sheet_title", ""),
            revision=fields.get("revision", ""),
            issue_date=fields.get("issue_date", ""),
            status=fields.get("status", ""),
            width=width,
            height=height,
            orientation=orientation,
            rotation=int(page.rotation or 0),
            word_count=word_count,
            image_count=img_count,
            text_quality_score=round(score, 3),
            raster_only=bool(img_count >= config["pdf"].get("raster_image_count_threshold", 1) and word_count < config["pdf"].get("min_words_per_page", 20)),
            garbled_text_warning=garbled,
            title_block_fields=fields,
        )
        page_infos.append(pi)
        page_texts.append((page_index, sheet_number, text))

    return page_infos, page_texts


def get_context(text: str, found: str, chars: int = 90) -> str:
    if not text or not found:
        return ""
    idx = text.upper().find(found.upper())
    if idx < 0:
        return ""
    start = max(0, idx - chars)
    end = min(len(text), idx + len(found) + chars)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def extract_word_hits(
    doc: fitz.Document,
    page_infos: list[PageInfo],
    page_texts: list[tuple[int, str, str]],
    config: dict[str, Any],
    aliases: dict[str, str] | None = None,
    ignore_patterns: list[re.Pattern] | None = None,
) -> dict[str, list[Hit]]:
    aliases = aliases or {}
    ignore_patterns = ignore_patterns or []
    norm_cfg = config.get("normalization", {})
    fuzzy = norm_cfg.get("fuzzy_tags", True)
    remove_sep = norm_cfg.get("remove_separators_for_match", False)

    regex_map = {
        "Valve": re.compile(config["regex"]["valve"], re.IGNORECASE),
        "Instrument": re.compile(config["regex"]["instrument"], re.IGNORECASE),
        "Line": re.compile(config["regex"]["line"], re.IGNORECASE),
        "Equipment": re.compile(config["regex"]["equipment"], re.IGNORECASE),
        "TieIn": re.compile(config["regex"]["tie_in"], re.IGNORECASE),
        "Sheet": re.compile(config["regex"]["sheet"], re.IGNORECASE),
    }

    hits: dict[str, list[Hit]] = {k: [] for k in regex_map}
    page_text_lookup = {pi: text for pi, _, text in page_texts}
    seen = set()
    for page_info in page_infos:
        page = doc[page_info.page_index]
        text = page_text_lookup.get(page_info.page_index, "")
        for word in page_words(page):
            x0, y0, x1, y1, token = word[:5]
            token = str(token or "").strip(".,;:()[]{}<>")
            if not token:
                continue
            if any(p.search(token) for p in ignore_patterns):
                continue
            for kind, regex in regex_map.items():
                for match in regex.finditer(token):
                    raw = match.group(0)
                    if any(p.search(raw) for p in ignore_patterns):
                        continue
                    norm = normalize_value(raw, fuzzy=fuzzy, remove_separators=remove_sep)
                    norm = apply_alias(norm, aliases)
                    key = (kind, norm, page_info.page_index, round(x0, 1), round(y0, 1))
                    if key in seen:
                        continue
                    seen.add(key)
                    hits[kind].append(Hit(
                        text=raw,
                        normalized=norm,
                        kind=kind,
                        page_index=page_info.page_index,
                        page_number=page_info.page_number,
                        sheet_number=page_info.sheet_number,
                        rect=RectData(float(x0), float(y0), float(x1), float(y1)),
                        context=get_context(text, raw),
                        confidence=0.80,
                    ))
    return hits


def export_extracted_text(out_dir: Path, page_infos: list[PageInfo], page_texts: list[tuple[int, str, str]]) -> None:
    text_dir = out_dir / "extracted_text"
    text_dir.mkdir(parents=True, exist_ok=True)
    for page_index, sheet_number, text in page_texts:
        safe = re.sub(r"[^A-Z0-9_.-]+", "_", sheet_number.upper())
        (text_dir / f"{page_index+1:04d}_{safe}.txt").write_text(text or "", encoding="utf-8")


def export_words_csv(path: Path, doc: fitz.Document, page_infos: list[PageInfo]) -> None:
    fields = ["page_number", "sheet_number", "word", "x0", "y0", "x1", "y1"]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for pi in page_infos:
            for word in page_words(doc[pi.page_index]):
                x0, y0, x1, y1, token = word[:5]
                writer.writerow({
                    "page_number": pi.page_number,
                    "sheet_number": pi.sheet_number,
                    "word": token,
                    "x0": round(float(x0), 2),
                    "y0": round(float(y0), 2),
                    "x1": round(float(x1), 2),
                    "y1": round(float(y1), 2),
                })
