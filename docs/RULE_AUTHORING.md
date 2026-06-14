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

## Tests

Add tests for normalization, reference parsing, rule output, false-positive suppression, and golden regression behavior.

## Profile Import And Export

Project profile files are JSON exports stored under `profiles/`. The backend exposes:

- `GET /projects/{project_id}/profiles/export/{profile_name}`
- `POST /projects/{project_id}/profiles/import`

Profile payloads include rule settings, regex patterns, title block regions, review settings, and output settings.
