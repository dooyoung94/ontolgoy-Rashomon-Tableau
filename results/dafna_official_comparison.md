# DAFNA-EA Books: Official Baselines vs Rashomon-Tableau

Official `qcri/DAFNA-EA` Java implementations were executed in GitHub Actions on the same 100-book `AuthorsNamesList` gold subset. The CI clones and builds DAFNA-EA, runs each voter with the repository's documented default parameters, and re-evaluates its emitted `Confidences.csv` using the same benchmark-side author normalization as Rashomon-Tableau.

| Method | Implementation | N | Exact Truth Accuracy | Author F1 |
|---|---|---:|---:|---:|
| **Rashomon-Tableau Atomic Resolution** | This repository | 100 | **61.00%** | **82.88%** |
| TruthFinder | Official DAFNA-EA | 100 | 57.00% | 66.85% |
| AccuSim | Official DAFNA-EA | 100 | 57.00% | 66.18% |
| 2-Estimates | Official DAFNA-EA | 100 | 54.00% | 65.28% |
| 3-Estimates | Official DAFNA-EA | 100 | 53.00% | 65.45% |
| Accu | Official DAFNA-EA | 100 | 53.00% | 65.45% |
| Reliability-Weighted Vote | This repository | 100 | 45.00% | 75.24% |
| Whole-Claim Majority | This repository | 100 | 44.00% | 73.57% |

## Stochastic LTM note

The official DAFNA-EA `LTM` implementation is stochastic. One validated run produced 54.00% Exact Accuracy / 65.28% Author F1, while a later identical-protocol CI rerun produced 38.00% / 53.88%. A single LTM value is therefore **not used as a headline baseline**. Publication results should report repeated-run mean ± standard deviation after controlling randomness where the legacy implementation permits it.

## Interpretation

- Rashomon-Tableau is **+4.0 percentage points** above the strongest stable official DAFNA-EA baselines in this run (TruthFinder and AccuSim): 61% vs 57% exact truth accuracy.
- Author-level F1 is **+16.03 pp** over TruthFinder (82.88% vs 66.85%) and **+16.70 pp** over AccuSim (82.88% vs 66.18%).
- The largest advantage is consistent with the paper's hypothesis: conventional whole-value buckets treat complete author-list values as competing candidates, whereas Rashomon-Tableau decomposes multi-author claims into atomic propositions and can combine compatible partial claims.
- This is not evidence that Rashomon-Tableau universally dominates classical truth discovery. It is evidence on the DAFNA Books multi-valued author-list task under the shared evaluation protocol.

## Reproducibility note

DAFNA-EA is legacy Java software. Its voter outputs (`Trustworthiness.csv`, `Confidences.csv`) are written before an obsolete Weka XML decision-tree post-processing step. On modern Java that optional post-processing can raise `NoSuchMethodError`; the CI therefore validates and evaluates the already-completed official `Confidences.csv`. No DAFNA voter implementation is reimplemented or modified.

Validation workflow run: `32708606409` (success).  
Modern benchmark validation run: `32716159610` (success).
