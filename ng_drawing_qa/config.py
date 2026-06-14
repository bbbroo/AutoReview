from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
import yaml


DEFAULT_CONFIG: dict[str, Any] = {
    "project": {
        "name": "Natural Gas Drawing QA",
        "profile": "balanced",
        "timezone": "America/Chicago",
    },
    "outputs": {
        "timestamped_output_folder": True,
        "insert_summary_page": True,
        "annotate_pdf": True,
        "dry_run": False,
        "export_text": False,
        "export_words": False,
        "html_report": True,
        "excel_report": True,
        "markdown_report": True,
        "backcheck_log": True,
        "critical_log": True,
        "hyperlink_suggestions": True,
        "powerbi_ready": True,
        "planner_ready": True,
        "single_review_packet_pdf": True,
        "single_review_packet_name": "single_review_packet.pdf",
    },
    "pdf": {
        "min_words_per_page": 20,
        "garbled_text_ratio_threshold": 0.18,
        "raster_image_count_threshold": 1,
        "summary_page_size": "letter",
        "ocr_warning_annotations": True,
        "page_rotation_handling": True,
    },
    "normalization": {
        "fuzzy_tags": True,
        "remove_separators_for_match": True,
        "uppercase": True,
        "alias_table": "",
        "ignore_patterns": "",
    },
    "reference_files": {
        "drawing_index": "",
        "valve_list": "",
        "line_list": "",
        "instrument_index": "",
        "equipment_list": "",
        "spec_list": "",
        "design_basis": "",
    },
    "column_mapping": {
        "drawing_index": {
            "sheet_number": ["sheet_number", "sheet", "drawing_number", "dwg_no", "drawing_no"],
            "sheet_title": ["sheet_title", "title", "drawing_title"],
            "revision": ["revision", "rev"],
            "issue_date": ["date", "issue_date"],
            "status": ["status", "issue_status"],
        },
        "valve_list": {
            "tag": ["tag", "valve_tag", "valve", "tag_number", "item_tag"],
            "size": ["size", "nominal_size"],
            "type": ["type", "valve_type"],
            "service": ["service"],
        },
        "line_list": {
            "tag": ["line_number", "line_no", "line", "tag", "line_tag"],
            "size": ["size", "nominal_size"],
            "service": ["service"],
            "maop": ["maop", "maop_psig", "maop_psi"],
            "design_pressure": ["design_pressure", "design_pressure_psig"],
            "test_pressure": ["test_pressure", "test_pressure_psig"],
            "material": ["material", "pipe_material"],
            "spec": ["spec", "pipe_spec", "class"],
            "coating": ["coating", "coating_spec"],
        },
        "instrument_index": {
            "tag": ["tag", "instrument_tag", "instrument", "tag_number", "loop_tag"],
            "type": ["type", "instrument_type"],
            "service": ["service"],
        },
        "equipment_list": {
            "tag": ["tag", "equipment_tag", "item_tag"],
            "type": ["type", "equipment_type"],
            "service": ["service"],
        },
    },
    "title_block": {
        "enabled": True,
        "regions": {
            "default": {
                # Fractions of page width/height: x0, y0, x1, y1.
                # Default assumes title block is lower right.
                "sheet_number": [0.70, 0.78, 0.98, 0.96],
                "sheet_title": [0.45, 0.78, 0.98, 0.90],
                "revision": [0.86, 0.70, 0.98, 0.82],
                "issue_date": [0.62, 0.70, 0.86, 0.82],
                "status": [0.45, 0.70, 0.62, 0.82],
                "drawn_by": [0.45, 0.64, 0.58, 0.72],
                "checked_by": [0.58, 0.64, 0.72, 0.72],
                "approved_by": [0.72, 0.64, 0.86, 0.72],
            }
        },
    },
    "regex": {
        "valve": r"\b(?:BV|CV|XV|MOV|ESD|SDV|BDV|HV|LV|RV|PSV|PRV|PCV|FCV|TCV|REG)[- _]?\d{2,5}[A-Z]?\b",
        "instrument": r"\b(?:PT|PI|PG|PSH|PSL|PIT|FT|FIT|FI|FQI|TT|TI|TE|TSH|TSL|LT|LI|LSH|LSL|AIT|AE|ZT|ZI)[- _]?\d{2,5}[A-Z]?\b",
        "line": r"\b\d{1,2}(?:\"|IN)?[- _]?(?:G|NG|FG|VG|V|BD|VENT|FUEL|HPG|MPG|LPG)[- _]?\d{2,5}[A-Z]?\b",
        "equipment": r"\b(?:FLT|FIL|SEP|MTR|REG|HTR|SKID|PKG|FLS|SCRUBBER|ODOR|COMP)[- _]?\d{2,5}[A-Z]?\b",
        "sheet": r"\b(?:G|C|M|P|E|I|S|D|A|X|PID|PFD)[- _]?\d{3,4}[A-Z]?\b",
        "tie_in": r"\b(?:TI|TIE[- _]?IN)[- _]?\d{1,5}[A-Z]?\b",
        "detail_ref": r"\b(?P<detail>\d{1,2}[A-Z]?)\s*/\s*(?P<sheet>(?:G|C|M|P|E|I|S|D|A|X|PID|PFD)[- _]?\d{3,4}[A-Z]?)\b",
        "section_ref": r"\b(?P<section>[A-Z])\s*/\s*(?P<sheet>(?:G|C|M|P|E|I|S|D|A|X|PID|PFD)[- _]?\d{3,4}[A-Z]?)\b",
        "pressure": r"\b(?P<label>MAOP|MOP|DESIGN\s+PRESSURE|OPERATING\s+PRESSURE|MAX(?:IMUM)?\s+PRESSURE|TEST\s+PRESSURE)\b[^\n\r]{0,120}?(?P<value>\d{2,5}(?:\.\d+)?)\s*(?P<unit>PSIG|PSI|KPA|BAR)\b",
        "code": r"\bASME\s+B31\.(?:3|4|8|12)\b",
        "material": r"\b(?:API\s+5L|ASTM\s+A\d{3}|A106|A53|Grade\s+B|X42|X52|X60|X65|X70)\b",
        "coating": r"\b(?:FBE|fusion\s+bonded\s+epoxy|coal\s+tar|polyethylene\s+tape|holiday\s+test|NACE|cathodic\s+protection|CP\s+test)\b",
        "revision_cloud": r"\b(?:REVISION\s+CLOUD|REV\s+CLOUD|DELTA\s+\d+|\u0394\s*\d+)\b",
    },
    "terms": {
        "regulator_station": [
            "worker regulator", "monitor regulator", "relief valve", "bypass",
            "blowdown", "pressure gauge", "sensing line", "slam shut",
            "upstream isolation", "downstream isolation"
        ],
        "relief_vent": ["relief vent", "vent stack", "blowdown", "PSV", "PRV", "relief valve", "vent termination"],
        "tie_in_required": ["shutdown", "purge", "blowdown", "test boundary", "existing", "NDE", "weld", "detail"],
    },
    "rules": {
        "LOW_SEARCHABLE_TEXT": {"enabled": True, "severity": "Info", "discipline": "Document Control", "confidence": 0.95},
        "RASTER_ONLY_PAGE": {"enabled": True, "severity": "Info", "discipline": "Document Control", "confidence": 0.95},
        "GARBLED_OCR_TEXT": {"enabled": True, "severity": "Minor", "discipline": "Document Control", "confidence": 0.80},
        "DRAWING_INDEX_RECONCILIATION": {"enabled": True, "severity": "Major", "discipline": "CAD / Document Control", "confidence": 0.90},
        "TITLE_BLOCK_MISSING_FIELD": {"enabled": True, "severity": "Minor", "discipline": "CAD / Document Control", "confidence": 0.75},
        "DUPLICATE_SHEET_NUMBER": {"enabled": True, "severity": "Major", "discipline": "CAD / Document Control", "confidence": 0.90},
        "REVISION_MISMATCH": {"enabled": True, "severity": "Major", "discipline": "CAD / Document Control", "confidence": 0.80},
        "SHEET_TITLE_MISMATCH": {"enabled": True, "severity": "Minor", "discipline": "CAD / Document Control", "confidence": 0.70},
        "VALVE_TAG_RECONCILIATION": {"enabled": True, "severity": "Major", "discipline": "Mechanical", "confidence": 0.85},
        "LINE_NUMBER_RECONCILIATION": {"enabled": True, "severity": "Major", "discipline": "Mechanical", "confidence": 0.85},
        "INSTRUMENT_TAG_RECONCILIATION": {"enabled": True, "severity": "Major", "discipline": "I&C", "confidence": 0.85},
        "EQUIPMENT_TAG_RECONCILIATION": {"enabled": True, "severity": "Major", "discipline": "Mechanical", "confidence": 0.80},
        "PRESSURE_CONSISTENCY": {"enabled": True, "severity": "Major", "discipline": "Mechanical", "confidence": 0.80},
        "CODE_CONSISTENCY": {"enabled": True, "severity": "Major", "discipline": "Mechanical", "confidence": 0.80},
        "TEST_PRESSURE_CHECK": {"enabled": True, "severity": "Major", "discipline": "Mechanical", "confidence": 0.70},
        "MATERIAL_SPEC_CHECK": {"enabled": True, "severity": "Minor", "discipline": "Mechanical", "confidence": 0.65},
        "COATING_NOTE_CHECK": {"enabled": True, "severity": "Minor", "discipline": "Mechanical / Corrosion", "confidence": 0.65},
        "REGULATOR_STATION_CHECKLIST": {"enabled": True, "severity": "Major", "discipline": "Mechanical", "confidence": 0.70},
        "RELIEF_VENT_CHECKLIST": {"enabled": True, "severity": "Major", "discipline": "Mechanical", "confidence": 0.75},
        "TIE_IN_CHECKLIST": {"enabled": True, "severity": "Major", "discipline": "Mechanical / Construction", "confidence": 0.75},
        "DETAIL_REFERENCE_CHECK": {"enabled": True, "severity": "Major", "discipline": "CAD / Design", "confidence": 0.90},
        "SECTION_REFERENCE_CHECK": {"enabled": True, "severity": "Minor", "discipline": "CAD / Design", "confidence": 0.85},
        "REPEATED_TAG_REVIEW": {"enabled": True, "severity": "Info", "discipline": "General", "confidence": 0.55},
        "COMMENT_QUALITY_SCORER": {"enabled": True, "severity": "Info", "discipline": "QA", "confidence": 0.65},
        "RFI_CANDIDATE_DETECTOR": {"enabled": True, "severity": "Major", "discipline": "Project Management", "confidence": 0.65},
        "AI_COMMENT_DRAFTS": {"enabled": False, "severity": "Info", "discipline": "QA", "confidence": 0.50},
        "SYMBOL_RECOGNITION_STUB": {"enabled": False, "severity": "Info", "discipline": "QA", "confidence": 0.40},
        "ASSET_REGISTER_DRAFT": {"enabled": True, "severity": "Info", "discipline": "Operations", "confidence": 0.50},
    },
    "review": {
        "rfi_keywords": ["existing", "field verify", "client", "vendor", "unknown", "survey", "utility", "operations", "TBD"],
        "owner_by_discipline": {
            "Mechanical": "",
            "Mechanical / Construction": "",
            "Mechanical / Corrosion": "",
            "I&C": "",
            "CAD / Design": "",
            "CAD / Document Control": "",
            "Document Control": "",
            "Project Management": "",
            "Operations": "",
        },
        "suppress_repeated_findings_per_tag": 5,
        "suppress_repeated_findings_per_rule_page": 10,
    },
    "profiles": {
        "balanced": {
            "rules_on": [
                "LOW_SEARCHABLE_TEXT", "RASTER_ONLY_PAGE", "GARBLED_OCR_TEXT",
                "DRAWING_INDEX_RECONCILIATION", "TITLE_BLOCK_MISSING_FIELD",
                "DUPLICATE_SHEET_NUMBER", "REVISION_MISMATCH", "SHEET_TITLE_MISMATCH",
                "VALVE_TAG_RECONCILIATION", "LINE_NUMBER_RECONCILIATION",
                "INSTRUMENT_TAG_RECONCILIATION", "EQUIPMENT_TAG_RECONCILIATION",
                "PRESSURE_CONSISTENCY", "CODE_CONSISTENCY", "TEST_PRESSURE_CHECK",
                "MATERIAL_SPEC_CHECK", "REGULATOR_STATION_CHECKLIST",
                "RELIEF_VENT_CHECKLIST", "TIE_IN_CHECKLIST",
                "DETAIL_REFERENCE_CHECK", "SECTION_REFERENCE_CHECK",
                "RFI_CANDIDATE_DETECTOR", "ASSET_REGISTER_DRAFT"
            ],
            "rules_off": ["AI_COMMENT_DRAFTS", "SYMBOL_RECOGNITION_STUB", "REPEATED_TAG_REVIEW"],
        },
        "conservative": {
            "rules_on": [
                "LOW_SEARCHABLE_TEXT", "RASTER_ONLY_PAGE", "DRAWING_INDEX_RECONCILIATION",
                "DUPLICATE_SHEET_NUMBER", "REVISION_MISMATCH",
                "VALVE_TAG_RECONCILIATION", "LINE_NUMBER_RECONCILIATION",
                "INSTRUMENT_TAG_RECONCILIATION", "EQUIPMENT_TAG_RECONCILIATION",
                "PRESSURE_CONSISTENCY", "CODE_CONSISTENCY", "DETAIL_REFERENCE_CHECK",
                "RFI_CANDIDATE_DETECTOR", "ASSET_REGISTER_DRAFT"
            ],
            "rules_off": [
                "AI_COMMENT_DRAFTS", "SYMBOL_RECOGNITION_STUB", "REPEATED_TAG_REVIEW",
                "TITLE_BLOCK_MISSING_FIELD", "SHEET_TITLE_MISMATCH",
                "MATERIAL_SPEC_CHECK", "COATING_NOTE_CHECK",
                "REGULATOR_STATION_CHECKLIST", "RELIEF_VENT_CHECKLIST",
                "TIE_IN_CHECKLIST", "SECTION_REFERENCE_CHECK"
            ],
        },
        "aggressive": {
            "rules_on": [
                "LOW_SEARCHABLE_TEXT", "RASTER_ONLY_PAGE", "GARBLED_OCR_TEXT",
                "DRAWING_INDEX_RECONCILIATION", "TITLE_BLOCK_MISSING_FIELD",
                "DUPLICATE_SHEET_NUMBER", "REVISION_MISMATCH", "SHEET_TITLE_MISMATCH",
                "VALVE_TAG_RECONCILIATION", "LINE_NUMBER_RECONCILIATION",
                "INSTRUMENT_TAG_RECONCILIATION", "EQUIPMENT_TAG_RECONCILIATION",
                "PRESSURE_CONSISTENCY", "CODE_CONSISTENCY", "TEST_PRESSURE_CHECK",
                "MATERIAL_SPEC_CHECK", "COATING_NOTE_CHECK",
                "REGULATOR_STATION_CHECKLIST", "RELIEF_VENT_CHECKLIST",
                "TIE_IN_CHECKLIST", "DETAIL_REFERENCE_CHECK", "SECTION_REFERENCE_CHECK",
                "REPEATED_TAG_REVIEW", "RFI_CANDIDATE_DETECTOR", "ASSET_REGISTER_DRAFT"
            ],
            "rules_off": ["AI_COMMENT_DRAFTS", "SYMBOL_RECOGNITION_STUB"],
        },
        "regulator_station": {
            "rules_on": ["REGULATOR_STATION_CHECKLIST", "RELIEF_VENT_CHECKLIST", "VALVE_TAG_RECONCILIATION", "INSTRUMENT_TAG_RECONCILIATION"],
            "rules_off": ["AI_COMMENT_DRAFTS", "SYMBOL_RECOGNITION_STUB"],
        },
        "pipeline_crossing": {
            "rules_on": ["LINE_NUMBER_RECONCILIATION", "DETAIL_REFERENCE_CHECK", "MATERIAL_SPEC_CHECK", "COATING_NOTE_CHECK"],
            "rules_off": ["REGULATOR_STATION_CHECKLIST", "AI_COMMENT_DRAFTS", "SYMBOL_RECOGNITION_STUB"],
        },
        "p_and_id": {
            "rules_on": ["VALVE_TAG_RECONCILIATION", "INSTRUMENT_TAG_RECONCILIATION", "PRESSURE_CONSISTENCY"],
            "rules_off": ["AI_COMMENT_DRAFTS", "SYMBOL_RECOGNITION_STUB"],
        },
    },
    "integrations": {
        "ai": {
            "enabled": False,
            "provider": "none",
            "model": "",
            "api_key_env": "OPENAI_API_KEY",
        },
        "bluebeam_bax": {
            "enabled": False,
            "mode": "documentation_only"
        },
        "studio_api": {
            "enabled": False,
            "mode": "documentation_only"
        },
        "power_bi": {
            "enabled": True,
            "mode": "csv_ready"
        },
        "sharepoint_jira_planner": {
            "enabled": True,
            "mode": "csv_ready"
        },
        "field_photo_matching": {
            "enabled": False,
            "mode": "manifest_only"
        },
    },
    "annotation": {
        "issue_prefix": "NGQA",
        "status_text": "Draft - Engineer Review Required",
        "colors": {
            "Critical": [1.0, 0.0, 0.0],
            "Major": [1.0, 0.45, 0.0],
            "Minor": [1.0, 0.85, 0.0],
            "Info": [0.0, 0.35, 1.0],
        },
        "max_individual_markups_per_rule_page": 10,
        "add_sheet_summary_annotations": True,
    },
}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | Path | None = None, profile: str | None = None) -> dict[str, Any]:
    config = deepcopy(DEFAULT_CONFIG)
    if path:
        path = Path(path)
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                override = yaml.safe_load(f) or {}
            config = deep_merge(config, override)
        else:
            raise FileNotFoundError(f"Config file not found: {path}")

    active_profile = profile or config.get("project", {}).get("profile")
    if active_profile and active_profile in config.get("profiles", {}):
        prof = config["profiles"][active_profile]
        for rule_id in prof.get("rules_on", []):
            config.setdefault("rules", {}).setdefault(rule_id, {})["enabled"] = True
        for rule_id in prof.get("rules_off", []):
            config.setdefault("rules", {}).setdefault(rule_id, {})["enabled"] = False
        config.setdefault("project", {})["profile"] = active_profile

    return config


def save_default_config(path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(DEFAULT_CONFIG, f, sort_keys=False, allow_unicode=True)


def is_rule_enabled(config: dict[str, Any], rule_id: str) -> bool:
    return bool(config.get("rules", {}).get(rule_id, {}).get("enabled", True))


def rule_setting(config: dict[str, Any], rule_id: str, key: str, default: Any = None) -> Any:
    return config.get("rules", {}).get(rule_id, {}).get(key, default)


def severity_for(config: dict[str, Any], rule_id: str, default: str = "Info") -> str:
    return str(rule_setting(config, rule_id, "severity", default))


def confidence_for(config: dict[str, Any], rule_id: str, default: float = 0.75) -> float:
    try:
        return float(rule_setting(config, rule_id, "confidence", default))
    except Exception:
        return default
