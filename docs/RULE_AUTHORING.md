# Rule Authoring

Rules must be deterministic, traceable, and testable.

## Rule Metadata

Add rule metadata in `ng_drawing_qa/rules/registry.py`:

- `rule_id`
- `name`
- `description`
- `discipline`
- `default_severity`
- `default_confidence`
- `required_inputs`
- `profiles`
- `output_type`
- `false_positive_notes`
- `enabled_by_default`

The UI reads this metadata from `GET /rules`.

## Rule Logic

Existing rules live in `ng_drawing_qa/rules/core_rules.py`. New production rules should be split into focused modules and exposed through the registry/run orchestration.

Every finding should include:

- stable rule ID
- clear message
- matched text or reference value
- sheet/page
- context/evidence
- confidence
- coordinates when available
- false-positive notes in metadata that tell reviewers when the rule is likely to be noisy

## False-Positive Controls

Rules that depend on OCR text, title-block extraction, or reference reconciliation must separate confirmed drawing errors from weak-evidence review prompts. Use `review` settings in the profile for thresholds rather than hard-coding local assumptions.

Current noisy-rule controls include:

- `title_block_min_extracted_fields` and `title_block_min_words`: suppress missing title-block-field comments unless the title block was actually readable.
- `sheet_number_min_title_fields` and `sheet_number_min_words`: require trusted sheet extraction before duplicate-sheet and drawing-index checks treat a sheet number as reliable.
- `reference_only_min_searchable_page_ratio`: downgrade reference-only "listed but not found" mismatches when the drawing set is not searchable enough to prove absence.
- `min_tag_hit_confidence` and `min_tag_length`: suppress ambiguous OCR/tag hits before comparing to reference lists.
- `coating_note_min_distinct_terms`: keep coating/CP review prompts informational and avoid one-word noise.
- `regulator_detector_terms`: require explicit regulator-station context before checklist prompts run.

When evidence is weak, prefer one of these outcomes: suppress the finding, emit an informational review warning, lower confidence, or require a profile to enable the rule. Do not mark weak OCR/reference-only evidence as a confirmed engineering error.

## Tests

Add tests for normalization, reference parsing, rule output, evidence fields, false-positive suppression, packet wording where applicable, and golden regression behavior. For rules that can create noisy findings, add at least one labeled false-positive or suppression-oriented test fixture.

## Reviewer Trust Requirements

Before enabling a new deterministic natural gas rule by default, confirm:

- the rule has metadata, required inputs, and false-positive notes
- findings include enough evidence for the UI trust panel
- profile controls can disable or tune the rule
- golden regression covers expected findings and missed/false-positive examples
- packet output uses edited reviewer wording and remains traceable by issue ID/fingerprint

## Profile Import And Export

Project profile files are JSON exports stored under `profiles/`. The backend exposes:

- `GET /projects/{project_id}/profiles/export/{profile_name}`
- `POST /projects/{project_id}/profiles/import`

Profile payloads include rule settings, regex patterns, title block regions, review settings, and output settings.
