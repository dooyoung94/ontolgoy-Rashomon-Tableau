# 2026-08-26 20-case structural + causal metric run

This commit is the provenance marker for the first metric run after the Stage-1/Stage-2 logic re-audit.

## Stage 1 — Cross-window Structural Consistency

- Dataset: `anon-ops/ops-lite`, first 20 normalized cases selected by the existing deterministic adapter.
- Reference: structural relations recovered from each case's **normal telemetry window**.
- Model input: `RelationObservation` records collected from the corresponding **abnormal/incident telemetry window**.
- Causal gold usage: none.
- Metric: exact typed-triple Precision / Recall / F1, macro and micro.
- Variants: Observation+Abduction; +DeBERTa; +PSL; +DeBERTa+PSL.
- Threshold: 0.5.
- Interpretation: cross-window structural consistency, **not** manually annotated structural ground-truth accuracy.

## Stage 2 — Controlled Incident Causal Qualification

- Same 20-case normalized set.
- 40% causal relation-label masking on observed service pairs.
- Structural endpoint visibility preserved.
- Variants: graph-only, abduction, abduction+DeBERTa, abduction+PSL, full.
- Metrics: causal relation F1, Node/Edge F1, path reachability, Root@1/Root@3.

## Integrity checks before run

- `pytest`: 35 passed.
- Stage-1 real `pslpython` inference smoke: passed on Python 3.10 + Java 17.
- Stage-1 evaluator joins references by `case_id` and fails on missing/duplicate IDs.
- All-pairs structural candidate generation is disabled.
