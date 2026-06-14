# Bluebeam Natural Gas Review Automation

A Python-based drawing QA tool that creates:

- A **Bluebeam-reviewable marked-up PDF**
- A **CSV issue log**
- A **single-source Review Packet PDF** containing the issue index, marked-up drawings, and rendered reference inputs
- A **formatted Excel issue dashboard**
- A **Markdown review report**
- A **local HTML dashboard**
- OCR/searchability reports
- Drawing index reconciliation reports
- Natural-gas-specific QA findings

The app is designed for natural gas drawing sets such as regulator stations, P&IDs, piping plans, pipeline crossings, and construction packages.

## Important Safety Note

This tool creates **draft automated findings**. It does not approve drawings, make engineering decisions, or replace a qualified engineer/designer.

Recommended status for all generated comments:

`Draft - Engineer Review Required`

## Install

```bash
python -m pip install -r requirements.txt
```

Or install as an editable package:

```bash
python -m pip install -e .
```

## Generate a Sample Project

```bash
python -m ng_drawing_qa.cli --generate-sample sample_project
```

Then run:

```bash
python -m ng_drawing_qa.cli sample_project/sample_natural_gas_drawing_set.pdf ^
  --drawing-index sample_project/drawing_index.csv ^
  --valve-list sample_project/valve_list.csv ^
  --line-list sample_project/line_list.csv ^
  --instrument-index sample_project/instrument_index.csv ^
  --equipment-list sample_project/equipment_list.csv ^
  --out-dir outputs
```

PowerShell users can replace `^` with backticks.


## Single-Source Review Packet PDF

The primary review output is now:

```text
single_review_packet.pdf
```

This PDF is intended to be the **single source for finding and reviewing automated findings**. It contains:

1. Cover / review warning
2. Issue index
3. Critical and major findings list
4. Fully marked-up drawing set
5. Rendered reference inputs such as drawing index, valve list, line list, instrument index, and equipment list
6. Source map / how-to-use page

The CSV, Excel, Markdown, and HTML reports are still generated as optional support outputs, but you should be able to review the automated findings directly from the single PDF packet without opening Excel.

Reference-list rows related to automated findings are shaded inside the packet.

## Basic Run

```bash
python -m ng_drawing_qa.cli input.pdf --out-dir outputs
```

## Full Run With Reference Files

```bash
python -m ng_drawing_qa.cli input.pdf ^
  --config config.example.yaml ^
  --profile regulator_station ^
  --drawing-index drawing_index.csv ^
  --valve-list valve_list.csv ^
  --line-list line_list.csv ^
  --instrument-index instrument_index.csv ^
  --equipment-list equipment_list.csv ^
  --out-dir outputs ^
  --export-text ^
  --export-words
```

## Batch Folder Mode

```bash
python -m ng_drawing_qa.cli --batch-folder input_pdfs --out-dir batch_outputs
```

## Create a Project Template

```bash
python -m ng_drawing_qa.cli --create-project-template my_ngqa_project
```

## Write Default Config

```bash
python -m ng_drawing_qa.cli --write-default-config config.yaml
```

## Major Features Implemented

### Reliability and Configuration

- YAML config system
- Rule enable/disable system
- Severity and confidence configuration
- False-positive ignore patterns
- Alias table support
- Run manifest JSON
- Timestamped output folders
- Dry-run mode
- Batch folder mode
- Logging

### PDF and OCR Reliability

- Searchable text quality report
- OCR-needed page report
- Raster/scan-like page detection
- Garbled OCR warning
- Page size/orientation/rotation report
- Extracted text export
- Word coordinate debug export

### Title Block and Index Automation

- Configurable title block crop regions
- Sheet number/title/revision/date/status extraction
- Missing title block field checker
- Duplicate sheet number checker
- Drawing index reconciliation
- Revision/title mismatch checks

### Reference File Support

- CSV and XLSX reference files
- Flexible column mapping
- Fuzzy tag normalization
- Alias table
- Input/reference validation
- Separate missing/extra reports

### Natural Gas QA Rules

- Valve tag reconciliation
- Line number reconciliation
- Instrument tag reconciliation
- Equipment tag reconciliation
- Regulator station checklist
- Relief/vent checklist
- Tie-in checklist
- MAOP/design pressure consistency
- ASME code consistency
- Test pressure check
- Material/spec review
- Coating/CP note review

### Drawing Reference Automation

- Detail reference checker
- Section/reference checker
- Missing target sheet finder
- Dangling callout report
- Hyperlink suggestions CSV

### Markup and Review Outputs

- Standardized issue IDs
- Standardized markup subjects
- Draft status in every markup
- Confidence in every finding
- Severity-based annotation colors
- Sheet-level summary annotations
- Summary page inserted at front
- Spam limiting per rule/page
- Evidence/context in issue log

### Dashboards and Reports

- `issue_log.csv`
- `summary.csv`
- `summary_by_severity.csv`
- `summary_by_rule.csv`
- `discipline_dashboard.csv`
- `sheet_risk_score.csv`
- `critical_major_issues.csv`
- `backcheck_issue_log.csv`
- `review_report.md`
- `review_dashboard.html`
- `issue_dashboard.xlsx`
- `page_quality_report.csv`
- `ocr_needed_pages.csv`
- `powerbi_issues.csv`
- `planner_import.csv`
- `rfi_candidates.csv`
- `ai_comment_drafts.csv`
- `asset_register_draft.csv`
- `symbol_detection_candidates.csv`

### Advanced Hooks Included

The following are included as safe extension hooks or documentation manifests:

- AI comment draft hook
- Symbol recognition hook
- Bluebeam BAX integration notes
- Bluebeam Studio/API integration notes
- Power BI-ready CSV
- Planner/SharePoint/Jira-ready CSV
- Field photo matching manifest

These are intentionally not fully automatic external integrations because they require credentials, organization-specific workflows, or validated model/CV setup.

## Recommended Workflow

1. OCR the PDF in Bluebeam if it is scanned.
2. Run this tool.
3. Open the marked-up PDF in Bluebeam.
4. Review, edit, accept, or reject the draft findings.
5. Use `issue_log.csv` or `issue_dashboard.xlsx` for tracking.
6. Use `review_report.md` for meeting prep or QA summary.

## Known Limitations

- Text-based extraction works best on searchable PDFs.
- Title block extraction requires crop region tuning for your title block.
- Symbol recognition is scaffolded but not real CV counting yet.
- BAX generation is documentation-only in this version.
- Studio/API integration requires credentials and approval.
- AI comments are offline templated suggestions unless you implement a provider-specific integration.
