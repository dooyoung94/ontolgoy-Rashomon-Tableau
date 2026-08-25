# Rashomon-Tableau

## Uncertainty-Aware Multi-Hop Relation Completion over Incomplete Ontologies

**Core thesis:** when a knowledge graph or ontology is incomplete, a reasoner should not commit immediately to one Top-1 relation. It should preserve several near-optimal `(multi-hop path, relation)` interpretations as Rashomon Worlds, reject logically impossible worlds with Tableau reasoning, and marginalize the surviving worlds into a verified relation belief.

```text
Observed KG / Ontology
        ↓
2-4 hop evidence paths between h and t
        ↓
Candidate direct relations
        ↓
Semantic plausibility scorer
(DeBERTa / KGE / LLM; interchangeable)
        ↓
Rashomon near-optimal set
        ↓
(path, relation) Possible Worlds
        ↓
Ontology + Tableau SAT filtering
        ↓
Valid worlds only
        ↓
Relation marginal + uncertainty
        ↓
Verified relation inference
        ↓
Downstream LLM reasoning (MAGIC)
```

---

## 1. Research problem

Observed graph:

```text
h --r1--> e1 --r2--> ... --rk--> t
```

Missing direct relation:

```text
q = (h, ?, t)
```

Conventional completion commits early:

```text
r* = argmax_r score(path, r)
```

Rashomon retention:

```text
R_epsilon(q) = { (path, r) | score(path,r) >= best_score - epsilon }
```

Possible world:

```text
W(path,r) = observed_graph + proposed_relation(h,r,t)
```

Logical filtering:

```text
W_RT(q) = { W(path,r) | Tableau(ontology + W(path,r)) = SAT }
```

The final relation probability is obtained by summing the normalized weights of all surviving worlds that imply the same relation.

---

## 2. Why Rashomon + Tableau

- **Rashomon:** preserves ambiguity instead of forcing an early Top-1 decision.
- **Tableau:** removes candidates that look plausible to a neural scorer but violate hard ontology constraints.

```text
Semantic plausibility != Logical consistency
```

DeBERTa is therefore an interchangeable semantic compatibility scorer, not the final reasoner.

---

## 3. Current core

```text
src/rashomon_tableau/multihop_completion.py
src/rashomon_tableau/kg_multihop_benchmark.py
src/rashomon_tableau/ontology.py
src/rashomon_tableau/tableau.py

scripts/download_relation_benchmarks.py
scripts/build_multihop_relation_benchmark.py
scripts/evaluate_multihop_relation_completion.py

config/wn18rr_ontology_rules.yaml
```

Tableau supports explicit negation clashes, incompatible/exclusive relations, hierarchy, transitivity, symmetry, inverse relations, relation composition, irreflexive constraints, and antisymmetric constraints.

---

## 4. Experimental program

### Stage A - DAFNA-EA Books

Preliminary delayed-commitment evidence on the evaluated 100-book `AuthorsNamesList` subset:

| Method | Exact Truth Accuracy | Author F1 |
|---|---:|---:|
| **Rashomon Worlds - Marginal Reliability** | **62.00%** | **84.13%** |
| Rashomon Worlds - Hard Commit | 61.00% | 84.04% |
| Prior Atomic Resolution | 61.00% | 82.88% |
| Rashomon Worlds - Uniform | 58.00% | 80.38% |
| TruthFinder - official DAFNA-EA | 57.00% | 66.85% |
| AccuSim - official DAFNA-EA | 57.00% | 66.18% |

Gold truth is present in generated candidate worlds for **93%** of evaluated books.

### Stage B - WN18RR multi-hop missing relation

This is the current main algorithmic experiment. A target triple is used only when its head and tail remain connected by a 2-4 hop directed path in the train graph. The held-out gold relation is evaluation-only.

Controlled comparison:

```text
DeBERTa Top-1
    vs
DeBERTa + Rashomon
    vs
DeBERTa + Rashomon + Tableau
```

### Stage C - MAGIC downstream validation

MAGIC is no longer the core benchmark. It will test:

```text
Direct LLM
vs Compute-Matched LLM
vs Rashomon-Tableau
vs Rashomon-Tableau -> LLM
```

---

## 5. Executed WN18RR 50-row pilot

Validated GitHub Actions run: **32799621678**  
Artifact: **9546119681**  
Scorer: `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`  
Candidate relations: **11**  
Rashomon epsilon: **0.05**

Result summary:

| Metric | Result |
|---|---:|
| Examples | 50 |
| DeBERTa Top-1 accuracy | **16.0%** |
| Rashomon gold-relation coverage | **42.0%** |
| Gold retention after Tableau | **42.0%** |
| Rashomon-Tableau marginal Top-1 accuracy | **16.0%** |
| Average Rashomon set size | **3.82** |
| Average valid worlds | **3.82** |
| Average rejected worlds | **0.00** |
| Average relation entropy | **1.066** |

Rashomon retained the gold relation for **21/50** examples, while Top-1 was correct for **8/50**. Therefore delayed commitment preserved **13 additional gold relations**, an absolute coverage increase of **+26 percentage points** over early Top-1 commitment.

### By hop count

| Hop | n | Top-1 | Rashomon gold coverage | Tableau retention | RT Top-1 | Avg worlds |
|---:|---:|---:|---:|---:|---:|---:|
| 2-hop | 19 | 5.3% | **36.8%** | 36.8% | 5.3% | 5.26 |
| 3-hop | 23 | 30.4% | **47.8%** | 47.8% | 30.4% | 2.91 |
| 4-hop | 8 | 0.0% | **37.5%** | 37.5% | 0.0% | 3.00 |

Full summary:

```text
results/wn18rr_multihop_completion_pilot_50.json
```

### What this result actually means

**Supported by the pilot:**

- Early Top-1 commitment loses many gold relations.
- Rashomon retention materially increases gold candidate coverage: **16% -> 42%**.
- The effect is especially visible where Top-1 fails: 4-hop Top-1 is 0%, while the gold relation remains inside the Rashomon set for 37.5% of examples.

**Not supported yet:**

- Tableau did not reject a single world in this pilot.
- Therefore final marginal Top-1 remains identical to DeBERTa Top-1: **16%**.
- This pilot does **not** yet establish a Tableau performance gain.

Two concrete bottlenecks are exposed:

1. **Semantic scorer limitation:** generic NLI support is weak as a direct composition model for arbitrary WN18RR relation chains. DeBERTa Top-1 is only 16%.
2. **Tableau context limitation:** the current pilot sends only the selected evidence path plus the proposed relation into Tableau. Ontology-relevant neighboring graph facts are absent, so reverse-edge conflicts, cycles, and cross-path clashes are often invisible. This explains the observed `0.00` rejected worlds.

The next core experiment should therefore keep the positive Rashomon result but test Tableau with a bounded ontology-relevant local subgraph around `h` and `t`, and compare DeBERTa against a relation-composition/KGE scorer rather than assuming DeBERTa must remain the primary scorer.

---

## 6. Previous MAGIC diagnostics

Earlier MAGIC runs remain diagnostic evidence only:

- v2 exposed provenance-metadata leakage.
- v3 removed leakage and revealed about 25% gold-relevant candidate-path coverage.
- v4 raised usable candidate coverage to roughly 47-57% through canonicalization and ontology-aware traversal.
- Conditional DeBERTa scoring was about 88% when a gold-relevant path existed on usable Command/GPT-OSS pilot rows.
- The old final binary decision bypassed Rashomon/Tableau marginals, motivating the redesign.

---

## 7. Research questions after the pilot

**RQ1 - Delayed commitment:** supported provisionally. Does the +26pp gold-coverage effect persist on larger/stratified evaluation and with stronger scorers?

**RQ2 - Logical filtering:** unresolved. Does Tableau add value when each world is checked against an ontology-relevant local graph rather than one path only?

**RQ3 - Multi-hop difficulty:** open. Why does 4-hop Top-1 collapse while Rashomon still retains part of the gold set?

**RQ4 - Downstream value:** open. Does the verified world state improve MAGIC ID/LOC when supplied to an LLM?

---

## 8. Intended contribution

```text
Multi-hop evidence
    -> semantic candidate scoring
    -> Rashomon uncertainty preservation
    -> Tableau logical consistency
    -> relation marginal
    -> downstream reasoning
```

The contribution is the division of labor between statistical plausibility, uncertainty preservation, and symbolic logical validity. The current measured evidence supports the **Rashomon retention** part; the **Tableau gain remains to be empirically established**.
