# Rashomon-Tableau

## Uncertainty-Aware Multi-Hop Relation Completion over Incomplete Ontologies

**Core thesis:** for a missing direct relation `(h, ?, t)` supported by one or more multi-hop paths, do not commit immediately to one Top-1 relation. Preserve near-optimal `(path, relation)` interpretations as Rashomon Worlds, reject logically inconsistent worlds with ontology-guided Tableau reasoning, and marginalize the surviving worlds.

```text
Observed KG / Ontology
        ↓
2-4 hop evidence paths
        ↓
Candidate direct relations
        ↓
Semantic scorer (DeBERTa / KGE / LLM)
        ↓
Rashomon near-optimal set
        ↓
(path, relation) Worlds
        ↓
Ontology + Tableau SAT filtering
        ↓
Relation marginal + uncertainty
        ↓
Downstream LLM reasoning (MAGIC)
```

## 1. Core definitions

```text
q = (h, ?, t)
r* = argmax_r score(path, r)
R_epsilon(q) = { (path,r) | score(path,r) >= best_score - epsilon }
W(path,r) = observed_graph + proposed_relation(h,r,t)
W_RT(q) = { W(path,r) | Tableau(ontology + W(path,r)) = SAT }
```

Rashomon preserves ambiguity; Tableau performs hard logical pruning. Semantic plausibility and logical consistency are intentionally separated.

## 2. Experimental program

| Stage | Dataset | Purpose |
|---|---|---|
| A | DAFNA-EA Books | preliminary delayed-commitment evidence |
| B1 | WN18RR | multi-hop relation scoring + Rashomon retention |
| B2 | ontology-rich dataset / controlled contradiction set | Tableau consistency contribution |
| C | MAGIC | downstream LLM ID/LOC validation |

### DAFNA preliminary result

| Method | Exact Truth Accuracy | Author F1 |
|---|---:|---:|
| **Rashomon Worlds - Marginal Reliability** | **62.00%** | **84.13%** |
| Rashomon Worlds - Hard Commit | 61.00% | 84.04% |
| Prior Atomic Resolution | 61.00% | 82.88% |
| TruthFinder - official DAFNA-EA | 57.00% | 66.85% |
| AccuSim - official DAFNA-EA | 57.00% | 66.18% |

Gold truth is present in generated candidate worlds for 93% of evaluated books.

## 3. Executed WN18RR 50-row pilot

Run: `32799621678`  
Artifact: `9546119681`  
Scorer: `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`  
Candidate relations: 11  
Rashomon epsilon: 0.05

| Metric | Result |
|---|---:|
| Examples | 50 |
| DeBERTa Top-1 accuracy | **16.0%** |
| Rashomon gold coverage | **42.0%** |
| Path-only Tableau gold retention | **42.0%** |
| Path-only RT marginal Top-1 | **16.0%** |
| Average Rashomon worlds | 3.82 |
| Average rejected worlds | 0.00 |

Rashomon retained 21/50 gold relations while Top-1 recovered 8/50: **13 additional gold relations, +26 percentage points absolute coverage**.

| Hop | n | Top-1 | Rashomon gold coverage |
|---:|---:|---:|---:|
| 2 | 19 | 5.3% | **36.8%** |
| 3 | 23 | 30.4% | **47.8%** |
| 4 | 8 | 0.0% | **37.5%** |

Stored result:

```text
results/wn18rr_multihop_completion_pilot_50.json
```

## 4. Frozen-score Tableau-only ablation

To isolate Tableau from the scorer, the executed DeBERTa scores from Run `32799621678` were frozen and reused. Candidate scores and the Rashomon set are therefore identical; only Tableau context changes.

Ablation Run: `32802219346`  
Artifact: `9546885491`  
Local context: selected path + ontology-relevant train facts touching query/path nodes, capped at 16 facts.

| Metric | Path-only | Local-subgraph |
|---|---:|---:|
| Rashomon gold coverage | 42.0% | 42.0% |
| Tableau gold retention | 42.0% | 42.0% |
| RT Top-1 accuracy | 16.0% | 16.0% |
| Avg rejected worlds | **0.00** | **0.00** |
| Gold false-rejection rate | - | 0.0% |
| Avg entropy | 1.066 | 1.066 |
| Avg local fact count | - | 14.82 |

**Conclusion:** adding local graph context still produced no logical pruning. The bottleneck is not only missing context. WN18RR contains mostly positive lexical relations and provides few explicit negative, disjoint, incompatible, or other hard constraints capable of making a plausible candidate world UNSAT. Under the conservative ontology used here, most near-optimal candidates remain logically satisfiable.

Therefore:

```text
WN18RR -> good for relation prediction / path reasoning / Rashomon retention
WN18RR -> weak benchmark for measuring Tableau pruning contribution
```

Stored result:

```text
results/wn18rr_tableau_only_ablation_50.json
```

## 5. What MAGIC v4 actually showed

The v4 improvement was mainly **candidate retrieval + DeBERTa scoring**, not Tableau.

- v3 gold-relevant candidate coverage: about 25%
- v4 coverage after canonicalization / ontology-aware traversal: about 47-57%
- v4 DeBERTa conditional scoring when a relevant path existed: about 88%
- the final MAGIC binary decision still bypassed Rashomon/Tableau marginals

Thus v4 established that retrieval and semantic scoring matter. It did not establish a causal Tableau gain.

## 6. WN18RR peer relation-prediction reference

Our 50-row set is a **hard multi-hop-only subset**, so its values are not apples-to-apples with papers evaluating the full WN18RR relation-prediction split. Peer results are used as scorer references, not as direct leaderboard claims.

### Structure Enhanced Path Reasoning (2023)

| Model | MRR | Hits@1 | Hits@3 |
|---|---:|---:|---:|
| TransE | 0.639 | 0.385 | 0.850 |
| RotatE | 0.903 | 0.857 | 0.934 |
| HAKE | 0.887 | 0.832 | 0.935 |
| PathCon | 0.867 | 0.786 | 0.942 |
| APR | 0.937 | 0.910 | 0.953 |
| APR_Unified | **0.989** | **0.981** | **0.999** |
| SPR_LSTM | 0.958 | 0.935 | 0.977 |

### RP-ISS (Scientific Reports, 2024)

| Model | MRR | Hits@1 | Hits@3 |
|---|---:|---:|---:|
| TransE | 78.26 | 67.13 | 87.47 |
| DistMult | 84.83 | 78.82 | 88.85 |
| RotatE | 80.01 | 73.27 | 81.94 |
| SimplE | 73.46 | 66.22 | 75.60 |
| RP-ISS | **98.91** | **97.93** | **99.97** |

The peer literature makes one point clear: **generic DeBERTa at 16% Top-1 is not a competitive relation-prediction scorer.** The next WN18RR experiment must include a task-trained structural/path scorer such as RotatE/PathCon-style or another KGE/relation-composition baseline. Rashomon should then be tested on top of that stronger scorer.

Note: standard WN18RR **entity link prediction** `(h,r,?)` / `(?,r,t)` is a different task and is not directly compared here.

## 7. Current research decision

**Retain Rashomon.** The +26pp gold-retention signal is worth validating with stronger scorers and larger samples.

**Do not claim Tableau gain on WN18RR.** Two controlled Tableau contexts both reject zero worlds.

**Move Tableau validation to an ontology-rich setting.** The next Tableau-specific benchmark should expose explicit hard constraints (incompatibility, disjointness, negative assertions, cardinality/type restrictions) through UMLS-derived semantics or a controlled contradiction-injection ablation.

**Keep MAGIC downstream.** Once a verified reasoning state exists, test whether it improves LLM ID/LOC.

## 8. Implementation

```text
src/rashomon_tableau/multihop_completion.py
src/rashomon_tableau/kg_multihop_benchmark.py
src/rashomon_tableau/ontology.py
src/rashomon_tableau/tableau.py
scripts/evaluate_multihop_relation_completion.py
scripts/reevaluate_tableau_from_pilot.py
config/wn18rr_ontology_rules.yaml
```
