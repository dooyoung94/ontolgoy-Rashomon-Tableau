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

Rashomon-Tableau keeps every candidate whose score is sufficiently close to the best score:

```text
R_epsilon(q) = { (path, r) | score(path,r) >= best_score - epsilon }
```

Each retained candidate creates one possible world:

```text
W(path,r) = observed_graph + proposed_relation(h,r,t)
```

Only logically satisfiable worlds survive:

```text
W_RT(q) = { W(path,r) | Tableau(ontology + W(path,r)) = SAT }
```

The final relation probability is the sum of the normalized weights of all surviving worlds that imply that relation.

---

## 2. Why Rashomon and Tableau are both needed

They solve different problems.

- **Rashomon:** preserves ambiguity instead of forcing an early Top-1 decision.
- **Tableau:** removes candidates that look plausible to a neural scorer but violate hard ontology constraints.

```text
Semantic plausibility != Logical consistency
```

A high DeBERTa/KGE/LLM score therefore cannot override a logical clash.

---

## 3. Role of DeBERTa

DeBERTa is an interchangeable **semantic compatibility scorer**, not the final reasoner and not the novelty claim.

For each evidence path and candidate relation it produces:

```text
S(path,r) = support probability
C(path,r) = contradiction probability
U(path,r) = unresolved probability
```

For the first relation-completion experiment, `S(path,r)` is used as the candidate plausibility score. Rashomon decides which near-optimal candidates remain possible; Tableau decides which of those worlds are logically valid.

Default NLI model:

```text
MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli
```

---

## 4. Core implementation

```text
src/rashomon_tableau/multihop_completion.py
  RelationCandidate
  RelationWorld
  CompletionResult
  select_rashomon_candidates(...)
  complete_missing_relation(...)
  candidates_from_nli(...)

src/rashomon_tableau/kg_multihop_benchmark.py
  KGTriple
  MultiHopExample
  build_multihop_examples(...)
```

Tableau currently supports:

- explicit positive/negative clashes;
- incompatible relations;
- exclusive relations;
- hierarchy;
- transitivity;
- symmetry;
- inverse relations;
- relation composition;
- irreflexive constraints;
- antisymmetric constraints.

Core and benchmark regression tests run in GitHub Actions.

---

## 5. Experimental program

### Stage A - DAFNA-EA Books: preliminary delayed-commitment evidence

DAFNA is a truth-discovery experiment, not the main missing-relation benchmark.

Measured on the evaluated 100-book `AuthorsNamesList` subset:

| Method | Exact Truth Accuracy | Author F1 |
|---|---:|---:|
| **Rashomon Worlds - Marginal Reliability** | **62.00%** | **84.13%** |
| Rashomon Worlds - Hard Commit | 61.00% | 84.04% |
| Prior Atomic Resolution | 61.00% | 82.88% |
| Rashomon Worlds - Uniform | 58.00% | 80.38% |
| TruthFinder - official DAFNA-EA | 57.00% | 66.85% |
| AccuSim - official DAFNA-EA | 57.00% | 66.18% |

Gold truth is present in the generated candidate worlds for **93%** of the evaluated books. This provides preliminary evidence that delayed commitment is useful.

### Stage B - Multi-hop missing relation: main experiment

Primary dataset: **WN18RR**.

Additional datasets: FB15k-237 and UMLS.

A benchmark example is retained only when the held-out direct triple `(h, r_gold, t)` has an alternative 2-4 hop path between `h` and `t` in the train graph. Gold relation labels are used only after candidate scoring for evaluation.

Controlled comparison:

| Variant | Purpose |
|---|---|
| DeBERTa Top-1 | early semantic commitment |
| DeBERTa + Rashomon | delayed commitment |
| **DeBERTa + Rashomon + Tableau** | proposed method |
| KGE Top-1 / Top-K | embedding baselines |
| Rashomon + LLM + Tableau | scorer-independence test |

Primary metrics:

- Top-1 accuracy;
- Rashomon gold-relation coverage;
- gold retention after Tableau;
- Rashomon-Tableau marginal Top-1 accuracy;
- average Rashomon set size;
- valid/rejected world counts;
- relation entropy;
- 2-hop / 3-hop / 4-hop results.

Pilot runner:

```text
scripts/download_relation_benchmarks.py
scripts/build_multihop_relation_benchmark.py
scripts/evaluate_multihop_relation_completion.py
.github/workflows/wn18rr-multihop-pilot.yml
```

### Stage C - MAGIC: downstream LLM utility

MAGIC is no longer the main algorithm benchmark. It tests whether a verified reasoning state helps natural-language multi-hop contradiction detection and localization.

```text
Natural-language contexts
        ↓
Claim / KG extraction
        ↓
Rashomon-Tableau relation inference
        ↓
valid worlds + rejected worlds + marginals + entropy + proofs
        ↓
LLM
        ↓
ID + LOC + explanation
```

Main comparison:

1. Direct LLM
2. Compute-Matched LLM
3. Rashomon-Tableau only
4. **Rashomon-Tableau -> LLM**

---

## 6. What the previous MAGIC v2-v4 work established

Earlier MAGIC runs are retained only as diagnostic evidence.

- **v2:** provenance metadata leaked into DeBERTa inputs and inflated results.
- **v3:** after removing leakage, gold-relevant candidate-path coverage was about 25%.
- **v4:** canonicalization and ontology-aware traversal raised usable candidate coverage to about 47-57%.
- When a gold-relevant path existed, DeBERTa conditional scoring was about 88% on the usable Command/GPT-OSS pilot rows.
- The previous final binary decision still bypassed Rashomon/Tableau marginals, motivating the current redesign.

The old pipeline therefore does **not** count as validation of the redesigned method.

---

## 7. Research questions

**RQ1 - Delayed commitment**  
Does the Rashomon set preserve the gold relation more often than immediate Top-1 selection?

**RQ2 - Logical filtering**  
Can Tableau remove high-scoring but logically invalid worlds while retaining the gold relation?

**RQ3 - Multi-hop difficulty**  
How do Top-1, Rashomon coverage, and Tableau filtering change from 2-hop to 3-hop to 4-hop evidence?

**RQ4 - Downstream value**  
Does a verified Rashomon-Tableau reasoning state improve MAGIC ID/LOC when given to an LLM?

---

## 8. Intended contribution

```text
Multi-hop evidence
    -> semantic candidate scoring
    -> Rashomon near-optimal worlds
    -> Tableau consistency filtering
    -> relation marginal
    -> downstream reasoning
```

The contribution is the **division of labor** between probabilistic plausibility, uncertainty preservation, and symbolic logical validity. Possible worlds, Tableau, DeBERTa, KGE, and LLMs are not individually claimed as new.

---

## 9. Current status

Completed:

- DAFNA delayed-commitment experiment;
- MAGIC v2-v4 diagnostic experiments;
- model-agnostic Rashomon relation-completion core;
- irreflexive / antisymmetric Tableau constraints;
- WN18RR 2-4 hop benchmark builder;
- DeBERTa Top-1 vs Rashomon vs Rashomon-Tableau evaluator;
- regression CI.

Current empirical milestone:

```text
WN18RR 2-4 hop masked-relation pilot
```

The pilot result is stored under `results/` after the validated workflow completes and is then promoted into the Results section of this README and `RESEARCH_PAPER.md`.
