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

The default is accepted findings only.

## Packet Modes

The export dialog records packet intent separately from the finding filter:

- internal QA: accepted-only working packet for internal review
- client review: accepted-only packet intended for external comment transfer
- backcheck: unresolved/backcheck-oriented findings only
- full debug: all findings, including rejected findings, for troubleshooting

The exact included findings are still controlled by the deterministic finding scope stored with the packet export.

## Navigation

Generated packets include PDF bookmarks for the cover, issue index, critical/major list, marked-up drawing set, drawing-page finding clusters, rendered reference inputs, and source map. Issue IDs in the front matter are internal PDF links to the related marked-up drawing page when the viewer supports PDF links. Coordinate-backed drawing markups also carry a small visible issue-ID label, such as `AR-0022`, near the highlighted evidence so the drawing page can be reconciled back to the issue index and UI.

## Traceability

The same stable issue ID appears in the UI, SQLite, PDF markups, issue index, and support exports. Reviewer-edited wording is used in the packet; original generated wording remains stored with the finding.
