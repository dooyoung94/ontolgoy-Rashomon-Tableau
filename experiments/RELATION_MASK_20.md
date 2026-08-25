# OpenRCA 2.0 Relation-Masking Development Benchmark

This file records the first corrected controlled relation-masking benchmark after code-level validation.

## Protocol

- Dataset: `anon-ops/ops-lite`, 20 attributed cases from the OpenRCA 2.0/PAVE-style causal-process set.
- Input connectivity: service endpoint pairs are reconstructed from normal traces and remain visible.
- Main perturbation: 40% of incident-specific relation labels are hidden (`seed=42`); endpoint pairs are **not removed**.
- Relation target on each observed dependency:
  - `causal_propagates_to` if the observed pair occurs in the gold causal propagation graph.
  - `non_causal_dependency` otherwise.
- Gold causal labels are used only to construct/evaluate the controlled masking task. A masked label is never exposed to the model.
- Telemetry evidence: normal-vs-abnormal trace/log/metric signals produced by the leakage-safe adapter.
- Relation F1 treats `causal_propagates_to` as the positive class.
- This 20-case set is a development/pilot set, not a paper-final test set.

Workflow run: `32881882364`
Commit evaluated: `10b2d228dd694e5df75454c4f5831a70507f9b88`

## Corrected ablations

| Variant | Relation Acc. | Relation Precision | Relation Recall | Relation F1 | Node F1 | Edge F1 | Path Reachability | Root@1 | Root@3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A0 Graph-only | 73.83% | 0.00% | 0.00% | 0.00% | 78.86% | 72.83% | 20% | 10% | 25% |
| A1 Abduction | 32.17% | 21.67% | 50.00% | 29.67% | 69.02% | 61.76% | 30% | 15% | 30% |
| A2 Abduction + DeBERTa | 34.83% | 30.83% | 57.50% | 37.17% | 75.68% | 67.43% | 35% | 20% | 40% |
| A3 Abduction + PSL | 34.83% | 30.83% | 57.50% | 37.17% | 75.68% | 67.43% | 35% | 20% | 40% |
| A4 Abduction + DeBERTa + PSL | 34.83% | 30.83% | 57.50% | 37.17% | 75.68% | 67.43% | **40%** | 15% | **45%** |

## What was fixed before this run

1. **Relation masking replaced edge masking as the main experiment.** Endpoint connectivity remains visible; only relation semantics are masked.
2. **Candidate explosion was removed.** Abduction no longer enumerates all node pairs; it creates hypotheses only for observed masked/unknown endpoint pairs.
3. **Observed structure is not treated as causal evidence.** Connectivity determines candidate eligibility only.
4. **DeBERTa zero-score collapse was fixed.** The previous absolute entailment mixture was replaced by a neutral-preserving, contrastive causal-vs-noncausal NLI score.
5. **PSL structural bias was removed.** Rules no longer contain `STRUCTURAL -> CAUSES`; missing temporal/anomaly evidence can act as negative causal evidence and global reachability only reinforces locally supported hypotheses.
6. **Visible causal/non-causal labels are preserved as hard relation facts; PSL infers only masked relations.**

## Interpretation

- Graph-only obtains high relation accuracy because most masked observed dependencies are non-causal; it predicts no positive causal relation on masked pairs, so positive-class Relation F1 is 0. Accuracy alone is therefore misleading.
- A2 and A3 independently produce the same thresholded relation decisions on this 20-case development set. Their Relation F1 improves from A1's 29.67% to 37.17%.
- The full A4 model does not improve relation classification over A2/A3 on this small development set, but improves process-level Path Reachability from 35% to 40% and Root@3 from 40% to 45%; Root@1 falls from 20% to 15%.
- The next scientific bottleneck is positive-vs-negative relation discrimination from telemetry, not hypothesis count.

## LLM comparison

A fair controlled LLM baseline is implemented in `scripts/run_openrca2_llm_relation_baseline.py`. It receives the same masked relation graph, telemetry evidence, and symptoms, cannot invent endpoint pairs, and is scored by the same evaluator. Running it requires an `OPENAI_API_KEY` (and selected model) in the execution environment.

Direct comparison with the official OpenRCA 2.0 LLM leaderboard must be reported separately using the standard unmasked 500-case protocol; these 20-case controlled relation-masking numbers must not be compared directly with official leaderboard numbers.
