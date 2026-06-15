from __future__ import annotations

from copy import deepcopy

from ng_drawing_qa.config import DEFAULT_CONFIG
from ng_drawing_qa.issue_builder import IssueBuilder
from ng_drawing_qa.models import Hit, PageInfo, RectData
from ng_drawing_qa.reference import ReferenceRecord, normalize_value
from ng_drawing_qa.rules.base import RuleContext
from ng_drawing_qa.rules.core_rules import (
    check_duplicate_sheets,
    check_reference_reconciliations,
    check_regulator_relief_tiein,
    check_title_block,
)


def _ctx(
    *,
    page_infos: list[PageInfo],
    page_texts: list[tuple[int, str, str]] | None = None,
    hits: dict[str, list[Hit]] | None = None,
    references: dict[str, list[ReferenceRecord]] | None = None,
    config_overrides: dict | None = None,
) -> RuleContext:
    config = deepcopy(DEFAULT_CONFIG)
    if config_overrides:
        for section, values in config_overrides.items():
            config.setdefault(section, {}).update(values)
    return RuleContext(
        config=config,
        issue_builder=IssueBuilder(config),
        page_infos=page_infos,
        page_texts=page_texts or [(pi.page_index, pi.sheet_number, "") for pi in page_infos],
        hits=hits or {},
        references=references or {},
        run_warnings=[],
    )


def _page(page_number: int, sheet: str, *, words: int = 100, fields: dict[str, str] | None = None) -> PageInfo:
    return PageInfo(
        page_index=page_number - 1,
        page_number=page_number,
        sheet_number=sheet,
        word_count=words,
        title_block_fields=fields or {},
    )


def _ref(raw: str, source_type: str = "valve_list") -> ReferenceRecord:
    return ReferenceRecord(
        normalized=normalize_value(raw),
        raw=raw,
        source_type=source_type,
        source_file="valves.csv",
        row_number=2,
        fields={"tag": raw},
    )


def test_title_block_missing_fields_requires_readable_extracted_title_block():
    ctx = _ctx(page_infos=[_page(1, "PAGE-1", words=8, fields={})])

    check_title_block(ctx)

    assert ctx.issue_builder.issues == []


def test_title_block_missing_field_becomes_low_confidence_review_prompt_when_grounded():
    ctx = _ctx(
        page_infos=[
            _page(
                1,
                "P-101",
                fields={"sheet_number": "P-101", "revision": "0", "issue_date": "2026-06-14", "checked_by": ""},
            )
        ]
    )

    check_title_block(ctx)

    assert len(ctx.issue_builder.issues) == 1
    issue = ctx.issue_builder.issues[0]
    assert issue.rule_id == "TITLE_BLOCK_MISSING_FIELD"
    assert issue.severity == "Info"
    assert issue.confidence == 0.55


def test_duplicate_sheet_ignores_weak_title_block_extraction():
    ctx = _ctx(
        page_infos=[
            _page(1, "P-101", words=100, fields={"sheet_number": "P-101"}),
            _page(2, "P-101", words=100, fields={"sheet_number": "P-101"}),
        ],
        config_overrides={"review": {"sheet_number_min_title_fields": 2}},
    )

    check_duplicate_sheets(ctx)

    assert ctx.issue_builder.issues == []


def test_reference_only_missing_tag_is_downgraded_when_pdf_searchability_is_weak():
    ctx = _ctx(
        page_infos=[_page(1, "P-101", words=3, fields={"sheet_number": "P-101", "revision": "0"})],
        hits={"Valve": []},
        references={"valve_list": [_ref("BV-101")]},
    )

    check_reference_reconciliations(ctx)

    assert len(ctx.issue_builder.issues) == 1
    issue = ctx.issue_builder.issues[0]
    assert issue.rule_id == "VALVE_TAG_RECONCILIATION"
    assert issue.severity == "Info"
    assert issue.confidence == 0.50
    assert "reference-only review warning" in issue.message


def test_ambiguous_low_confidence_tag_hit_is_suppressed_but_real_hit_remains():
    weak_hit = Hit(
        text="BV",
        normalized="BV",
        kind="Valve",
        page_index=0,
        page_number=1,
        sheet_number="P-101",
        rect=RectData(10, 10, 20, 20),
        confidence=0.40,
    )
    real_hit = Hit(
        text="BV-101",
        normalized=normalize_value("BV-101"),
        kind="Valve",
        page_index=0,
        page_number=1,
        sheet_number="P-101",
        rect=RectData(30, 30, 60, 40),
        confidence=0.90,
    )
    ctx = _ctx(
        page_infos=[_page(1, "P-101", fields={"sheet_number": "P-101", "revision": "0"})],
        hits={"Valve": [weak_hit, real_hit]},
        references={"valve_list": [_ref("BV-200")]},
    )

    check_reference_reconciliations(ctx)

    messages = [issue.message for issue in ctx.issue_builder.issues]
    assert any("BV-101" in message for message in messages)
    assert all("'BV'" not in message for message in messages)


def test_regulator_check_requires_explicit_regulator_context_not_any_valve_hit():
    hit = Hit(
        text="BV-101",
        normalized=normalize_value("BV-101"),
        kind="Valve",
        page_index=0,
        page_number=1,
        sheet_number="P-101",
        rect=RectData(30, 30, 60, 40),
        confidence=0.90,
    )
    ctx = _ctx(
        page_infos=[_page(1, "P-101", fields={"sheet_number": "P-101", "revision": "0"})],
        page_texts=[(0, "P-101", "Plan view with valve BV-101 and gas main.")],
        hits={"Valve": [hit]},
    )

    check_regulator_relief_tiein(ctx)

    assert [issue for issue in ctx.issue_builder.issues if issue.rule_id == "REGULATOR_STATION_CHECKLIST"] == []
