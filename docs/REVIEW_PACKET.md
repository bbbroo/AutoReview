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

- Exact-location markups: findings with valid coordinates get the existing rectangle markup around the matched drawing evidence plus a visible `AR-####` issue-ID label near the rectangle.
- Page-level callouts: findings with a valid page number but missing, zero, or invalid coordinates get a stacked callout box on the related drawing page. The callout includes issue ID, severity, rule ID, and reviewer-edited message. This makes coordinate-less findings visible instead of silently dropping them.

If a finding cannot be placed because its page number is invalid or outside the drawing set, it is counted as unplaced in the run manifest.

## Traceability

The same stable issue ID appears in the UI, SQLite, PDF markups, issue index, run manifest, `finding_traceability.csv`, and support exports. Reviewer-edited wording is used in the packet; original generated wording remains stored with the finding.

Reference CSV/XLSX inputs are rendered into the packet when included, and the desktop reference mapping preview should be checked before export so reviewers can trust which columns drove list-based evidence.

After packet export, `run_manifest.json` includes `packet_markup_counts` with `coordinate_backed_markups`, `fallback_page_callouts`, and `unplaced_findings`.
