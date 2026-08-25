# Rashomon-Tableau: Uncertainty-Aware Multi-Hop Relation Completion over Incomplete Ontologies

## Abstract

Knowledge graphs and ontologies are incomplete by construction. Two entities can be connected through several intermediate relations while their direct relation remains missing or ambiguous. Conventional completion methods typically rank candidate relations and commit to one Top-1 prediction. This can discard plausible alternatives and can also select a high-scoring relation that violates hard ontology constraints.

We propose **Rashomon-Tableau**, an uncertainty-aware multi-hop relation reasoning framework. The method keeps near-optimal `(multi-hop path, candidate relation)` interpretations as possible worlds, preserves them through an adaptive Rashomon set, checks them with ontology-guided Tableau reasoning, and marginalizes surviving worlds into a relation belief. Semantic plausibility and logical validity are deliberately separated: DeBERTa, KGE, path-reasoning models, or LLMs may provide candidate scores, while Tableau is used only for hard consistency filtering.

The empirical program has three stages. DAFNA-EA Books supplies preliminary delayed-commitment evidence. WN18RR is used to study multi-hop relation scoring and Rashomon retention. In an executed 50-example hard multi-hop subset, DeBERTa Top-1 accuracy is 16%, while the epsilon Rashomon set contains the gold relation for 42% of examples, preserving 13 additional gold relations (+26 percentage points). A scorer-frozen Tableau-only ablation then compares path-only and bounded local-subgraph contexts under identical candidates and scores. Both reject zero worlds and remain at 16% final Top-1, showing that WN18RR under conservative lexical ontology rules does not provide enough hard inconsistency to demonstrate Tableau pruning. Tableau contribution must therefore be evaluated separately on an ontology-rich or controlled contradiction benchmark. MAGIC remains a downstream natural-language validation.

---

## 1. Research Problem

Observed graph:

```text
h --r1--> e1 --r2--> ... --rk--> t
```

Missing direct relation:

```text
q = (h, ?, t)
```

Early commitment:

```text
r* = argmax_r score(path, r)
```

Rashomon retention:

```text
R_epsilon(q) = {
  candidate |
  score(candidate) >= best_score - epsilon
}
```

World construction and logical filtering:

```text
W(path,r) = observed_graph + proposed_relation(h,r,t)
W_RT(q)   = { W(path,r) | Tableau(ontology + W(path,r)) = SAT }
```

The central question is whether preserving near-optimal interpretations, followed by logical consistency filtering where hard constraints are available, yields a better and more faithful reasoning state than immediate Top-1 collapse.

---

## 2. Hypotheses

### H1 - Delayed commitment
Rashomon retention preserves the gold relation more often than immediate Top-1 selection.

### H2 - Logical filtering
When the ontology contains discriminative hard constraints, Tableau rejects high-scoring but logically inconsistent worlds while retaining valid gold worlds.

### H3 - Multi-hop difficulty
The value of uncertainty preservation remains observable as multi-hop relation prediction becomes harder.

### H4 - Downstream utility
A verified world state improves LLM multi-hop contradiction ID/LOC relative to raw-context and compute-matched baselines.

H2 is intentionally conditional on the benchmark exposing relevant logical constraints. A dataset on which all plausible candidates remain satisfiable cannot establish the value of a consistency checker.

---

## 3. Method

### 3.1 Candidate representation

```text
candidate_i = (path_i, relation_i, semantic_score_i)
```

Candidate paths are obtained from the observed graph. Candidate relations may come from the full relation vocabulary, KGE/path models, ontology rules, or LLM proposals.

### 3.2 Semantic scorer

The first pilot uses DeBERTa NLI:

```text
Premise    = natural-language rendering of the multi-hop path
Hypothesis = candidate direct relation between h and t

S(path,r) = support
C(path,r) = contradiction
U(path,r) = unresolved
```

`S(path,r)` supplies the initial plausibility. This scorer is interchangeable and is not the novelty claim.

### 3.3 Rashomon set

```text
R_epsilon(q) = {
  candidate |
  score(candidate) >= best_score - epsilon
  and score(candidate) >= min_score
}
```

The set adapts to score ambiguity instead of fixing one prediction prematurely.

### 3.4 Tableau filtering

Each retained candidate defines a possible world. Tableau tests the world against configured ontology semantics.

Current implementation supports:

- positive/negative clashes;
- incompatible and exclusive relations;
- hierarchy;
- transitivity;
- symmetry and inverse relations;
- relation composition;
- irreflexivity;
- antisymmetry.

```text
Rashomon = uncertainty preservation
Tableau  = hard logical pruning
```

### 3.5 Relation marginal

For valid worlds:

```text
P(W_i | q) = score_i / sum(score_j over valid worlds)
P(r | q)   = sum P(W_i | q) for valid worlds whose relation is r
H(q)       = - sum_r P(r|q) * log(P(r|q))
```

---

## 4. Experimental Program

### Stage A - DAFNA-EA Books

Preliminary truth-discovery experiment:

| Method | Exact Truth Accuracy | Author F1 |
|---|---:|---:|
| **Rashomon Worlds - Marginal Reliability** | **62.00%** | **84.13%** |
| Rashomon Worlds - Hard Commit | 61.00% | 84.04% |
| Prior Atomic Resolution | 61.00% | 82.88% |
| TruthFinder - official DAFNA-EA | 57.00% | 66.85% |
| AccuSim - official DAFNA-EA | 57.00% | 66.18% |

Gold truth occurs in the generated candidate-world set for 93% of the evaluated books. DAFNA supports the delayed-commitment motivation but is not a multi-hop relation benchmark.

### Stage B1 - WN18RR multi-hop relation prediction

A held-out target is retained only when its head/tail remain connected through a directed 2-4 hop train-graph path. Gold relation is evaluation-only.

Primary comparison:

```text
Top-1 scorer
    -> scorer + Rashomon
    -> scorer + Rashomon + Tableau
```

WN18RR is now treated primarily as a **relation prediction / path reasoning / Rashomon retention** benchmark rather than the sole Tableau benchmark.

### Stage B2 - Tableau-specific logical benchmark

Because WN18RR contains mostly positive lexical relation facts and few explicit hard constraints, Tableau contribution will be evaluated in an ontology-rich setting exposing incompatibility, disjointness, negative assertions, type restrictions, or controlled contradictions. Candidate directions include UMLS-derived semantics and a label-blind contradiction-injection ablation.

### Stage C - MAGIC downstream validation

```text
Natural-language contexts
      -> claim / KG extraction
      -> Rashomon-Tableau reasoning state
      -> LLM
      -> ID + LOC + explanation
```

Key comparison:

```text
Direct LLM
vs Compute-Matched LLM
vs Rashomon-Tableau only
vs Rashomon-Tableau -> LLM
```

---

## 5. Executed WN18RR Results

### 5.1 Multi-hop 50-row pilot

Workflow Run: `32799621678`  
Artifact: `9546119681`  
Candidate relations: 11  
Scorer: `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`  
Epsilon: 0.05

| Metric | Result |
|---|---:|
| DeBERTa Top-1 accuracy | **16.0% (8/50)** |
| Rashomon gold coverage | **42.0% (21/50)** |
| Path-only Tableau retention | 42.0% |
| Path-only RT Top-1 | 16.0% |
| Average Rashomon set size | 3.82 |
| Average rejected worlds | 0.00 |

The Rashomon set retains **13 gold relations that Top-1 loses**, corresponding to **+26 percentage points** absolute gold coverage.

By hop:

| Hop | n | Top-1 | Rashomon coverage |
|---:|---:|---:|---:|
| 2 | 19 | 5.3% | **36.8%** |
| 3 | 23 | 30.4% | **47.8%** |
| 4 | 8 | 0.0% | **37.5%** |

Stored result:

```text
results/wn18rr_multihop_completion_pilot_50.json
```

### 5.2 Scorer-frozen Tableau-only ablation

To isolate Tableau, all DeBERTa candidate scores from Run `32799621678` are frozen. Thus candidate rankings and Rashomon membership are identical between conditions.

Workflow Run: `32802219346`  
Artifact: `9546885491`  
Artifact SHA-256: `88d8a5ed9e1fd430f90ba3b68f0666b9bfa2ffcc8313a1a4697d536a01c4a973`

Conditions:

```text
Path-only:
  selected evidence path + proposed relation

Local-subgraph:
  same path
  + ontology-relevant train facts touching h/t/path nodes
  + proposed relation
  local cap = 16 facts
```

| Metric | Path-only | Local-subgraph |
|---|---:|---:|
| Rashomon gold coverage | 42.0% | 42.0% |
| Tableau gold retention | 42.0% | 42.0% |
| RT Top-1 | 16.0% | 16.0% |
| Avg rejected worlds | **0.00** | **0.00** |
| Gold false rejection | - | 0.0% |
| Avg entropy | 1.066 | 1.066 |
| Avg local fact count | - | 14.82 |

The local-subgraph condition changes neither validity nor posterior ranking. This eliminates the simple explanation that path-only context alone caused the absence of pruning.

The stronger diagnosis is **benchmark/ontology mismatch for H2**: WN18RR provides mainly positive WordNet relation triples. Candidate relations such as `_also_see`, `_similar_to`, domain relations, meronymy, and hypernymy often coexist without violating the conservative transitivity/symmetry/irreflexivity/antisymmetry rules. There are few explicit negative or disjoint facts that would make a near-optimal world UNSAT.

Therefore no Tableau performance gain is claimed on WN18RR.

Stored result:

```text
results/wn18rr_tableau_only_ablation_50.json
```

---

## 6. WN18RR Peer Group

The present 50-row set is deliberately restricted to targets with 2-4 hop alternative paths, so its percentages are **not directly leaderboard-comparable** with full-test WN18RR relation-prediction papers. Peer results serve as reference baselines for scorer strength.

### 6.1 Structure Enhanced Path Reasoning, 2023

This work explicitly evaluates relation prediction on WN18RR and reports:

| Model | MRR | Hits@1 | Hits@3 | Hits@5 |
|---|---:|---:|---:|---:|
| TransE | 0.639 | 0.385 | 0.850 | 0.943 |
| RotatE | 0.903 | 0.857 | 0.934 | 0.960 |
| HAKE | 0.887 | 0.832 | 0.935 | 0.953 |
| PathCon | 0.867 | 0.786 | 0.942 | 0.975 |
| APR | 0.937 | 0.910 | 0.953 | 0.969 |
| APR_Unified | **0.989** | **0.981** | **0.999** | **0.999** |
| SPR_LSTM | 0.958 | 0.935 | 0.977 | 0.992 |

This peer is particularly relevant because it uses relation paths and relational contexts rather than treating relation prediction as plain text NLI.

### 6.2 RP-ISS, Scientific Reports 2024

Full WN18RR relation-prediction results include:

| Model | MRR | Hits@1 | Hits@3 |
|---|---:|---:|---:|
| TransE | 78.26 | 67.13 | 87.47 |
| DistMult | 84.83 | 78.82 | 88.85 |
| RotatE | 80.01 | 73.27 | 81.94 |
| SimplE | 73.46 | 66.22 | 75.60 |
| RP-ISS | **98.91** | **97.93** | **99.97** |

The absolute scales differ across protocols, but the scientific conclusion is robust: **a generic DeBERTa NLI scorer at 16% Top-1 is not a competitive WN18RR relation-prediction baseline.** The next experiment must incorporate a task-trained structural/path scorer such as RotatE, PathCon-style reasoning, or another relation-composition/KGE model, then ask whether Rashomon retention adds value on top of that stronger scorer.

Standard WN18RR entity link prediction `(h,r,?)` / `(?,r,t)` is a different task and is not mixed with these relation-prediction comparisons.

---

## 7. Relation to Previous MAGIC v4

The previous MAGIC v4 gains came from **better candidate retrieval and DeBERTa path scoring**, not a demonstrated Tableau effect.

- v3 relevant-path coverage: ~25%
- v4 relevant candidate coverage: ~47-57%
- v4 conditional DeBERTa scoring when a relevant path was present: ~88%
- final binary decision still bypassed Rashomon/Tableau marginals

Thus the WN18RR result does not contradict v4. They measure different components:

```text
MAGIC v4: retrieval/scoring improved
WN18RR:   Rashomon retention improves coverage
WN18RR:   Tableau pruning not activated by available hard constraints
```

---

## 8. Current Scientific Evidence Boundary

Supported provisionally:

- delayed commitment can preserve additional gold interpretations;
- on the WN18RR hard subset, Rashomon coverage is +26pp above DeBERTa Top-1.

Not supported yet:

- Tableau improves WN18RR relation-prediction accuracy;
- final Rashomon marginal beats strong task-trained relation-prediction peers;
- redesigned pipeline improves MAGIC ID/LOC.

Next controlled sequence:

```text
1. Replace/augment DeBERTa with strong path/KGE relation scorer on WN18RR.
2. Re-test Top-1 vs scorer+Rashomon on a larger stratified multi-hop subset.
3. Validate Tableau separately on ontology-rich / contradiction-bearing data.
4. Feed verified world state to MAGIC LLM downstream evaluation.
```

---

## 9. Falsification Criteria

Narrow or reject the framework if:

- Rashomon coverage gain disappears with strong scorers;
- an ontology-rich benchmark still yields no useful Tableau pruning;
- Tableau pruning removes gold worlds as often as wrong worlds;
- final marginal ranking cannot improve against strong relation-prediction controls;
- MAGIC downstream utility is absent.
