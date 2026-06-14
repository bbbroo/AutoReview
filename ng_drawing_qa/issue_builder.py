from __future__ import annotations

from collections import defaultdict
from typing import Any

from .models import Issue, RectData
from .config import severity_for, confidence_for


class IssueBuilder:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.issues: list[Issue] = []
        self.prefix = config.get("annotation", {}).get("issue_prefix", "NGQA")
        self.status = config.get("annotation", {}).get("status_text", "Draft - Engineer Review Required")
        self._counts_by_rule_page: dict[tuple[str, int], int] = defaultdict(int)
        self._counts_by_rule_tag: dict[tuple[str, str], int] = defaultdict(int)

    def add(
        self,
        rule_id: str,
        subject: str,
        message: str,
        page_number: int = 1,
        sheet_number: str = "",
        found_text: str = "",
        context: str = "",
        rect: RectData | None = None,
        severity: str | None = None,
        discipline: str | None = None,
        confidence: float | None = None,
        owner: str = "",
        rfi_candidate: str = "No",
        source: str = "auto",
        ai_suggested_comment: str = "",
    ) -> Issue:
        rule_cfg = self.config.get("rules", {}).get(rule_id, {})
        sev = severity or rule_cfg.get("severity") or severity_for(self.config, rule_id, "Info")
        disc = discipline or rule_cfg.get("discipline") or "General"
        conf = float(confidence if confidence is not None else confidence_for(self.config, rule_id, 0.75))
        rect = rect or RectData()

        issue = Issue(
            issue_id=f"{self.prefix}-{len(self.issues)+1:04d}",
            rule_id=rule_id,
            subject=subject,
            message=message,
            severity=sev,
            discipline=disc,
            confidence=conf,
            status=self.status,
            page_number=page_number,
            output_pdf_page_number=page_number + (1 if self.config.get("outputs", {}).get("insert_summary_page", True) else 0),
            sheet_number=sheet_number,
            found_text=found_text,
            context=context,
            x0=round(rect.x0, 2),
            y0=round(rect.y0, 2),
            x1=round(rect.x1, 2),
            y1=round(rect.y1, 2),
            owner=owner,
            rfi_candidate=rfi_candidate,
            source=source,
            ai_suggested_comment=ai_suggested_comment,
        )
        self.issues.append(issue)
        return issue
