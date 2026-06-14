from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from ..models import PageInfo, Hit
from ..reference import ReferenceRecord
from ..issue_builder import IssueBuilder


@dataclass
class RuleContext:
    config: dict[str, Any]
    issue_builder: IssueBuilder
    page_infos: list[PageInfo]
    page_texts: list[tuple[int, str, str]]
    hits: dict[str, list[Hit]]
    references: dict[str, list[ReferenceRecord]]
    run_warnings: list[str]
