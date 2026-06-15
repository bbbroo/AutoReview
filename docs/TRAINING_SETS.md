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
- per-rule performance rows with expected, actual, accepted count, accepted rate, matched, missing, new, changed, false-positive, wording, tuning, and missed counts

The accepted rate is a reviewer-trust tuning signal. Rules with many findings and low accepted rates should be reviewed for noisy matching, missing profile controls, unclear wording, or suppressions. The rule summary is not an AI training score and does not prove engineering correctness.

For false-positive reduction, inspect low accepted-rate rules and then tune local profile settings such as title-block extraction thresholds, duplicate-sheet trust thresholds, reference-only searchability ratio, tag hit confidence, aliases, ignored phrases, and rule enablement. Keep representative false positives and missed findings in the local training set so future rule changes can prove they reduced noise without hiding true issues.

## Stored Data

Training data lives under the project folder:

```text
training/{training_set_id}/golden_findings.json
project.sqlite
```

SQLite stores labels and missed findings. The golden JSON stores deterministic fingerprints and expected finding attributes.

Golden rows include issue ID, fingerprint, rule ID, severity, status, subject, edited message, sheet number, and found text so regression can detect message/severity drift without relying on unstable database IDs.

## Real PDFs

Real client/company PDFs should stay local. Use them as local training inputs only; do not commit them.
