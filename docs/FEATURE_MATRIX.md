# Feature Matrix

This file maps the requested feature IDs to implementation status.

## Implemented as working code

1-48, 51-55, 57-80

## Implemented as safe extension hooks / documentation outputs

49, 50, 56, 72, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90

## Why some are hooks

Some features require external credentials, validated company templates, DWG/CAD access, model/API setup, or computer-vision training data. The app includes extension points and output files so those can be connected safely later without blocking the core review automation.


## Single-source packet upgrade

Added after initial implementation:

- `single_review_packet.pdf`
- Issue index inside PDF
- Critical/Major findings inside PDF
- Marked-up drawings inside same PDF
- Rendered reference input files inside same PDF
- Reference rows shaded when tied to findings
- CSV/Excel outputs retained as optional support files only
