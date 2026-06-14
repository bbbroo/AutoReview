# Training Sets

Training sets are local deterministic regression assets, not black-box AI training.

## Workflow

1. Run a review on an example project.
2. Create a training set from that run.
3. Label findings as correct, false positive, missed issue, needs better wording, or rule needs tuning.
4. Add manual missed findings when the engine missed an expected issue.
5. Run golden comparison after rule/config/code changes.

## Regression Output

Golden comparison reports:

- expected, actual, missing, new, and changed finding counts
- false-positive and missed-finding label counts
- per-rule performance rows with expected, actual, matched, missing, new, changed, false-positive, wording, tuning, and missed counts

The rule summary is intended for practical rule tuning. It is not an AI training score and does not prove engineering correctness.

## Stored Data

Training data lives under the project folder:

```text
training/{training_set_id}/golden_findings.json
project.sqlite
```

SQLite stores labels and missed findings. The golden JSON stores deterministic fingerprints and expected finding attributes.

## Real PDFs

Real client/company PDFs should stay local. Use them as local training inputs only; do not commit them.
