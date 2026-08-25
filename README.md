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
| B | WN18RR, then FB15k-237 / UMLS | main multi-hop missing-relation experiment |
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

The evaluation subset contains held-out test triples whose head and tail remain connected by a directed 2-4 hop path in the train graph. Gold relation labels are evaluation-only.

| Metric | Result |
|---|---:|
| Examples | 50 |
| DeBERTa Top-1 accuracy | **16.0%** |
| Rashomon gold coverage | **42.0%** |
| Path-only Tableau gold retention | **42.0%** |
| Path-only RT marginal Top-1 | **16.0%** |
| Average Rashomon worlds | 3.82 |
| Average path-only Tableau rejected worlds | **0.00** |

Rashomon retained the gold relation for 21/50 examples while Top-1 was correct for 8/50: **13 additional gold relations, +26 percentage points absolute coverage**.

### By hop

| Hop | n | Top-1 | Rashomon gold coverage |
|---:|---:|---:|---:|
| 2 | 19 | 5.3% | **36.8%** |
| 3 | 23 | 30.4% | **47.8%** |
| 4 | 8 | 0.0% | **37.5%** |

Result snapshot:

```text
results/wn18rr_multihop_completion_pilot_50.json
```

## 4. What changed from MAGIC v4?

The v4 improvement was mainly **candidate retrieval + DeBERTa scoring**, not a measured Tableau gain.

- v3 gold-relevant candidate coverage: about 25%
- v4 usable candidate coverage after canonicalization / ontology-aware traversal: about 47-57%
- v4 DeBERTa conditional scoring when the relevant path existed: about 88%
- however, the old final decision still bypassed Rashomon/Tableau marginals

Therefore v4 showed that better multi-hop retrieval and semantic scoring matter. It did **not** establish that Tableau itself improved final accuracy.

## 5. Current Tableau ablation

The first WN18RR pilot sent only the selected evidence path plus proposed relation into Tableau, so cross-path cycles and endpoint-neighborhood conflicts were invisible. This produced zero rejected worlds.

The evaluator now compares two conditions while keeping the same DeBERTa scores and same Rashomon set:

```text
A. Path-only Tableau
   selected path + proposed relation

B. Local-subgraph Tableau
   selected path
   + ontology-relevant train facts touching h/t/path nodes
   + proposed relation
```

The local neighborhood is bounded to keep transitive closure tractable. Current validation workflow: `WN18RR Multi-hop Rashomon-Tableau Pilot`.

Metrics added:

- local Tableau gold retention
- local RT Top-1 accuracy
- wrong-world rejection precision
- gold false-rejection rate
- average rejected worlds
- entropy before/after local logical pruning

## 6. WN18RR peer reference

Our 50-row experiment is a **multi-hop-only relation-masked subset**, so its raw percentages must not be presented as directly comparable to papers using the full WN18RR relation-prediction test protocol. The following values are peer references for the same broad `(h, ?, t)` relation-prediction task.

Scientific Reports 2024, *A novel model for relation prediction in knowledge graphs exploiting semantic and structural feature integration* reports on WN18RR:

| Model | MRR | Hits@1 | Hits@3 |
|---|---:|---:|---:|
| TransE | 78.26 | 67.13 | 87.47 |
| DistMult | 84.83 | 78.82 | 88.85 |
| RotatE | 80.01 | 73.27 | 81.94 |
| SimplE | 73.46 | 66.22 | 75.60 |
| RP-ISS | **98.91** | **97.93** | **99.97** |

Interpretation: generic DeBERTa is currently a weak relation-composition scorer on our hard multi-hop subset. The next controlled baseline must therefore include a trained relation-prediction/KGE scorer rather than treating DeBERTa as the performance ceiling.

Standard WN18RR link-prediction papers that predict missing **entities** use MRR/Hits@K under `(h,r,?)` / `(?,r,t)` and are tracked separately; those scores are not directly comparable to our relation prediction.

## 7. Research questions

**RQ1 - Delayed commitment:** does Rashomon retain the gold relation more often than early Top-1 selection?  
Current pilot: provisionally yes, +26pp coverage.

**RQ2 - Logical filtering:** can Tableau reject wrong near-optimal worlds without rejecting gold worlds?  
Current status: path-only unresolved; local-subgraph ablation in execution.

**RQ3 - Multi-hop difficulty:** how do Top-1, Rashomon coverage, and logical pruning change over 2/3/4 hops?

**RQ4 - Downstream value:** does a verified Rashomon-Tableau state improve MAGIC ID/LOC when supplied to an LLM?

## 8. Implementation

```text
src/rashomon_tableau/multihop_completion.py
src/rashomon_tableau/kg_multihop_benchmark.py
src/rashomon_tableau/ontology.py
src/rashomon_tableau/tableau.py
config/wn18rr_ontology_rules.yaml
scripts/build_multihop_relation_benchmark.py
scripts/evaluate_multihop_relation_completion.py
```

The measured evidence currently supports **Rashomon retention**. Tableau remains an empirical hypothesis until the local-subgraph ablation demonstrates selective pruning.