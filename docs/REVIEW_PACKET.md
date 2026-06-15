# Review Packet

The single review packet PDF is the primary deliverable.

## Contents

- cover and review disclaimer
- issue summary
- issue index
- critical and major finding list
- marked-up drawing pages
- rendered CSV/XLSX reference inputs with issue-linked row shading
- supplemental PDF/DOCX/TXT reference evidence
- packet source map

## Finding Scope

Export can include:

- accepted findings only
- accepted and needs-review findings
- all non-rejected findings
- backcheck findings: needs review, needs more information, RFI candidate, and backcheck required
- all findings

The default is accepted findings only. Rejected findings are excluded unless the export explicitly enables rejected findings; the built-in full debug mode does this for troubleshooting.

Backcheck mode uses the backcheck finding scope and is intended for unresolved findings, RFI candidates, needs-review findings, needs-more-information findings, and findings explicitly marked Backcheck Required.

## Packet Modes

The export dialog records packet intent separately from the finding filter:

- internal QA: accepted-only working packet for internal review
- client review: accepted-only packet intended for external comment transfer
- backcheck: unresolved/backcheck-oriented findings only
- full debug: all findings, including rejected findings, for troubleshooting

The exact included findings are still controlled by the deterministic finding scope stored with the packet export.

## Navigation

Generated packets include PDF bookmarks for the cover, issue index, critical/major list, marked-up drawing set, drawing-page finding clusters, rendered reference inputs, and source map. Issue IDs in the front matter are internal PDF links to the related marked-up drawing page when the viewer supports PDF links.

The Marked-Up Drawing Set uses two visible markup styles:

- Exact-location markups: findings with valid rule-provided hit coordinates get the existing rectangle markup around the matched drawing evidence plus a visible `AR-####` issue-ID label near the rectangle. These are reported as `exact_hit`.
- Resolved text-search markups: findings without rule-provided coordinates but with searchable `found_text` are resolved back to a PDF text rectangle before export. These are reported as `resolved_text_search`.
- Title-block region markups: title-block, revision, sheet-title, and duplicate-sheet findings use configured title-block regions when exact text coordinates are unavailable. These are reported as `title_block_region`.
- Page-level callouts: findings with a valid page number but no reliable exact or resolved location get a stacked callout box on the related drawing page. The callout includes issue ID, severity, rule ID, and reviewer-edited message. These are reported as `page_level`.
- Reference-only findings: findings for items listed in a reference file but not found on the drawing are not shown as misleading drawing-location rectangles. They remain in the issue index and reference evidence section and are reported as `reference_only`.

If a finding cannot be placed because its page number is invalid or outside the drawing set, it is counted as unplaced in the run manifest.

## Traceability

The same stable issue ID appears in the UI, SQLite, PDF markups, issue index, run manifest, `finding_traceability.csv`, and support exports. Reviewer-edited wording is used in the packet; original generated wording remains stored with the finding.

Reference CSV/XLSX inputs are rendered into the packet when included, and the desktop reference mapping preview should be checked before export so reviewers can trust which columns drove list-based evidence.

After packet export, `run_manifest.json` includes `packet_markup_counts` with `exact_location_markups`, `resolved_search_markups`, `title_block_region_markups`, `fallback_page_callouts`, `reference_only_findings`, and `unplaced_findings`. The run output also includes `placement_debug.csv` with each attempted placement and the reason it succeeded or fell back.
