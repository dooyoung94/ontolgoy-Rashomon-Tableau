# Audited Metrics — 2026-08-26

This file is the metric provenance record after the structural/causal logic re-audit.

## Protocol boundary

### Stage 1 — Cross-window Structural Consistency

- Run: `32941786967`
- Code SHA: `7d7a1665b9cd926a91cd3a465f2e9ef044556e62`
- N: 20 OpenRCA/ops-lite cases.
- Reference: structural relations recovered from each case's **normal telemetry window**.
- Model input: `RelationObservation` records from the corresponding **abnormal/incident telemetry window**.
- Causal gold usage: **none**.
- `HAS_SERVICE`: excluded from the primary metric because case-level `system` metadata would create a trivial persistent membership relation in both windows.
- Metric: exact typed-triple Precision / Recall / F1.
- Interpretation: **cross-window structural consistency**, not manually annotated structural ground-truth accuracy.

Confirmed results:

| Variant | Macro P | Macro R | Macro F1 | Micro P | Micro R | Micro F1 | TP | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S-A0 Observation + Abduction | 98.68% | 96.17% | 97.34% | 98.65% | 96.15% | 97.39% | 950 | 13 | 38 |
| S-A2 Observation + Abduction + PSL | 98.68% | 96.17% | 97.34% | 98.65% | 96.15% | 97.39% | 950 | 13 | 38 |

Per relation type:

| Relation | Precision | Recall | F1 | TP | FP | FN |
|---|---:|---:|---:|---:|---:|---:|
| CALLS | 98.08% | 92.73% | 95.33% | 153 | 3 | 12 |
| DEPLOYED_ON | 97.42% | 93.55% | 95.44% | 377 | 10 | 26 |
| RUNS_ON | 100.00% | 100.00% | 100.00% | 420 | 0 | 0 |

Mean abnormal-window observations/candidates/selected relations: **48.15** per case.  
Mean normal-window reference relations: **49.40** per case.

Current interpretation: Stage-1 PSL produces no measurable gain on this 20-case protocol because these relation types are already strongly identified by OpenTelemetry fields and ontology type constraints. This is a negative/neutral result, not an error.

### Stage 2 — Controlled Incident Causal Qualification

- Run: `32920790878`
- Manifest cases scanned: **500**.
- Adapter-valid/evaluable controlled cases: **343**.
- Observed service-pair endpoints remain visible.
- A controlled fraction of `causal_propagates_to` vs `non_causal_dependency` labels is hidden.
- Therefore this is a **controlled causal-qualification ablation**, not a standard end-to-end OpenRCA run.

A0–A5 definitions:

- A0: graph / visible causal facts
- A1: Abduction
- A2: Abduction + DeBERTa
- A3: Abduction + PSL
- A4: Abduction + DeBERTa + PSL
- A5: A4 + constrained Qwen final adjudication

### 20% causal-relation mask

| Method | Root F1 | Exact Root | AnySvc | Node F1 | Edge F1 | Path | Causal Rel F1 | Root@1 | Root@3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A0 | 17.35% | 0.00% | 34.69% | 66.29% | 78.82% | 31.20% | 0.00% | 17.20% | 34.69% |
| A1 | 38.73% | 12.24% | 61.22% | 67.43% | 64.11% | 59.48% | 21.49% | 37.32% | 61.22% |
| A2 | 38.29% | 11.37% | 61.22% | 67.82% | 65.05% | 59.18% | 23.79% | 35.57% | 61.22% |
| A3 | 42.03% | 10.20% | 69.68% | 67.05% | 64.36% | 67.93% | 24.16% | 52.77% | 69.68% |
| **A4** | **43.29%** | 9.91% | **72.59%** | 66.82% | 63.98% | **70.85%** | **24.36%** | **52.77%** | **72.59%** |
| A5 | 39.36% | 8.45% | 66.76% | **75.25%** | **74.53%** | 63.27% | 12.43% | 49.27% | 66.76% |

### 40% causal-relation mask

| Method | Root F1 | Exact Root | AnySvc | Node F1 | Edge F1 | Path | Causal Rel F1 | Root@1 | Root@3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A0 | 17.35% | 0.00% | 34.69% | 61.90% | 66.69% | 28.57% | 0.00% | 17.20% | 34.69% |
| A1 | 31.63% | 9.33% | 51.02% | 58.97% | 52.28% | 48.69% | 23.68% | 31.20% | 51.02% |
| A2 | 30.56% | 7.87% | 50.44% | 59.12% | 52.97% | 48.10% | **25.73%** | 30.90% | 50.44% |
| A3 | 34.50% | 6.41% | 59.48% | 58.26% | 52.13% | 57.14% | 25.32% | 45.19% | 59.48% |
| **A4** | **35.81%** | 6.41% | **62.39%** | 58.10% | 51.96% | **60.35%** | 25.63% | **48.10%** | **62.39%** |
| A5 | 33.19% | 6.71% | 57.14% | **68.03%** | **63.21%** | 49.56% | 14.48% | 44.90% | 57.14% |

### 60% causal-relation mask

| Method | Root F1 | Exact Root | AnySvc | Node F1 | Edge F1 | Path | Causal Rel F1 | Root@1 | Root@3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A0 | 17.35% | 0.00% | 34.69% | 53.20% | 47.24% | 26.24% | 0.00% | 17.20% | 34.69% |
| A1 | 25.90% | 6.41% | 42.86% | 52.68% | 42.57% | 38.48% | 27.01% | 25.95% | 42.86% |
| A2 | 24.64% | 5.25% | 41.69% | 52.46% | 43.38% | 37.61% | 28.62% | 26.53% | 41.69% |
| A3 | 27.11% | 4.08% | 47.81% | 51.56% | 42.67% | 44.90% | 28.43% | 37.32% | 47.81% |
| **A4** | **29.35%** | 4.08% | **52.48%** | 51.57% | 42.79% | **49.85%** | **28.75%** | **42.27%** | **52.48%** |
| A5 | 26.68% | 3.50% | 47.81% | **59.62%** | 43.79% | 34.40% | 9.29% | 38.48% | 47.81% |

## Main findings

1. **A4 is the primary model.** Across 20/40/60% masking it gives the strongest root/path behavior among A0–A4.
2. **DeBERTa primarily helps local causal semantic discrimination.** Its standalone effect on root/path is small or sometimes negative, while relation F1 generally improves over pure abduction.
3. **PSL/joint soft-logic selection primarily improves root/path coherence.** A4 vs A3 improves Path Reachability by +2.92, +3.21, and +4.95 percentage points at 20/40/60% masking, respectively.
4. **A5 is a mixed/negative result for causal RCA.** It increases Node/Edge F1 but degrades Root F1, Path Reachability, and causal-relation F1. It must not be presented as the final winning model.
5. A2 and A3 hypothesis scores are highly correlated (Pearson approximately 0.99) but their threshold decisions disagree on about 4.1–4.3% of candidate pairs, so they are not identical signals.

## Validation status

Before the corrected metric run:

- `pytest`: **35 passed**.
- Actual Stage-1 `pslpython` inference smoke: passed on Python 3.10 + Java 17.
- Stage-1 reference join is by `case_id`; missing/duplicate references fail fast.
- Structural all-pairs candidate generation is disabled.
- Only `CALLS` is projected to Stage-2 service propagation eligibility and its direction is intentionally reversed from caller→callee to callee→caller.
