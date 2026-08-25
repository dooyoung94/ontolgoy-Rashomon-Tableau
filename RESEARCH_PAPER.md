# Rashomon-Tableau: Uncertainty-Aware Multi-Hop Relation Completion over Incomplete Ontologies

## Abstract

Knowledge graphs and ontologies are incomplete by construction. Two entities can be connected through several intermediate relations while their direct relation remains missing or ambiguous. Conventional completion methods typically rank candidate relations and commit to one Top-1 prediction. This early commitment can discard plausible alternatives and can also select a high-scoring relation that violates hard ontology constraints.

We propose **Rashomon-Tableau**, an uncertainty-aware multi-hop relation reasoning framework. The method keeps near-optimal `(multi-hop path, candidate relation)` interpretations as possible worlds, preserves them through an adaptive Rashomon set, rejects logically inconsistent worlds through ontology-guided Tableau reasoning, and marginalizes the surviving worlds into a relation belief. Semantic plausibility and logical validity are deliberately separated: DeBERTa-v3 is one interchangeable semantic scorer, while Tableau is the intended consistency mechanism.

The empirical program has three linked stages. DAFNA-EA Books provides preliminary evidence that delayed commitment can improve truth adjudication. The main experiment evaluates 2-4 hop relation-masked knowledge-graph examples, beginning with WN18RR. In an executed 50-example WN18RR pilot, DeBERTa Top-1 relation accuracy is **16%**, while the epsilon Rashomon set contains the gold relation for **42%** of examples, preserving 13 additional gold relations (+26 percentage points). However, the current Tableau condition rejects no worlds, so final Rashomon-Tableau Top-1 remains 16%. The result supports uncertainty preservation but does not yet establish a Tableau gain; it also exposes two concrete limitations: generic NLI is a weak direct relation-composition scorer on this task, and Tableau currently receives too little local graph context to expose many logical clashes. MAGIC remains a downstream natural-language test rather than the main benchmark.

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

A conventional system returns:

```text
r* = argmax_r score(path, r)
```

This hides three sources of uncertainty:

1. multiple 2-4 hop evidence paths may connect `h` and `t`;
2. several candidate relations may receive similar semantic scores;
3. a high-scoring relation may be logically incompatible with the ontology.

The central research question is:

> Can multi-hop relation completion improve when near-optimal path/relation interpretations are preserved as alternative worlds, logically invalid worlds are removed by Tableau reasoning, and final belief is marginalized over the surviving worlds instead of collapsing immediately to one Top-1 prediction?

---

## 2. Hypotheses

### H1 - Delayed commitment

Rashomon retention should preserve the gold relation more often than immediate Top-1 selection.

### H2 - Logical filtering

Ontology-guided Tableau should reject high-scoring but logically inconsistent relation worlds while retaining logically compatible gold worlds.

### H3 - Multi-hop difficulty

The value of uncertainty preservation should remain observable when Top-1 performance degrades with multi-hop reasoning difficulty.

### H4 - Downstream utility

Supplying valid/rejected worlds, relation marginals, uncertainty, and proof information to an LLM should improve multi-hop contradiction ID/LOC relative to raw-context and compute-matched LLM baselines.

---

## 3. Method

### 3.1 Candidate space

For a query `q=(h,?,t)`, candidate generation produces:

```text
candidate_i = (path_i, relation_i, semantic_score_i)
```

Paths are discovered from the observed graph. Candidate relations may come from the full relation vocabulary, a KGE Top-K model, ontology rules, or an LLM proposal mechanism.

### 3.2 Semantic scoring

For the first NLI condition, DeBERTa receives:

```text
Premise    = natural-language rendering of the multi-hop evidence path
Hypothesis = candidate direct relation between h and t
```

and returns:

```text
S(path,r) = support
C(path,r) = contradiction
U(path,r) = unresolved
```

`S(path,r)` is used as semantic plausibility in the WN18RR pilot. DeBERTa does not generate worlds and does not determine logical validity.

### 3.3 Rashomon set

```text
R_epsilon(q) = {
  candidate |
  score(candidate) >= best_score - epsilon
  and score(candidate) >= min_score
}
```

Unlike fixed Top-K retention, the number of worlds adapts to score ambiguity.

### 3.4 Possible worlds

Each retained candidate creates one world:

```text
W(path,r) = observed_graph + proposed_relation(h,r,t)
```

Multiple paths supporting the same relation remain distinct worlds until marginalization.

### 3.5 Tableau filtering

Each world is checked with the ontology:

```text
Tableau(ontology + W(path,r)) -> SAT or UNSAT
```

UNSAT worlds are discarded.

The current relational Tableau supports explicit negation clashes, incompatible/exclusive relations, hierarchy, transitivity, symmetry, inverse relations, composition, irreflexivity, and antisymmetry.

```text
Rashomon = ambiguity preservation
Tableau  = logical pruning
```

### 3.6 Relation marginal

For valid worlds:

```text
P(W_i | q) = score_i / sum(score_j over valid worlds)
```

Relations receive the sum of the mass of all valid worlds that imply them:

```text
P(r | q) = sum P(W_i | q) for valid worlds whose relation is r
```

Residual uncertainty:

```text
H(q) = - sum_r P(r|q) * log(P(r|q))
```

---

## 4. Implementation

Core:

```text
src/rashomon_tableau/multihop_completion.py
src/rashomon_tableau/kg_multihop_benchmark.py
src/rashomon_tableau/ontology.py
src/rashomon_tableau/tableau.py
```

Benchmark scripts:

```text
scripts/download_relation_benchmarks.py
scripts/build_multihop_relation_benchmark.py
scripts/evaluate_multihop_relation_completion.py
```

The evaluator batches all `(example, candidate relation)` NLI pairs while keeping the logical experimental protocol unchanged.

WN18RR ontology:

```text
config/wn18rr_ontology_rules.yaml
```

Current conservative rules include `_hypernym` transitivity/irreflexivity/antisymmetry, `_instance_hypernym` irreflexivity, selected symmetric relations, and `_instance_hypernym + _hypernym -> _instance_hypernym` composition.

---

## 5. Experimental Program

### 5.1 Stage A - DAFNA-EA Books

DAFNA is preliminary evidence for delayed commitment rather than a missing-relation benchmark.

| Method | Exact Truth Accuracy | Author F1 |
|---|---:|---:|
| **Rashomon Worlds - Marginal Reliability** | **62.00%** | **84.13%** |
| Rashomon Worlds - Hard Commit | 61.00% | 84.04% |
| Prior Atomic Resolution | 61.00% | 82.88% |
| Rashomon Worlds - Uniform | 58.00% | 80.38% |
| TruthFinder - official DAFNA-EA | 57.00% | 66.85% |
| AccuSim - official DAFNA-EA | 57.00% | 66.18% |

Gold truth occurs in the generated candidate-world set for 93% of evaluated books.

### 5.2 Stage B - WN18RR multi-hop missing relation

Primary dataset: **WN18RR**. Additional planned datasets are FB15k-237 and UMLS.

Pilot construction policy:

1. target direct triple comes from the held-out test split;
2. target head/tail must remain connected through a 2-4 hop directed train-graph path;
3. gold direct relation is unavailable to path discovery and scoring;
4. the same 11 candidate relations are scored for every example;
5. gold is attached only after scoring for evaluation.

Main comparison:

```text
DeBERTa Top-1
    -> DeBERTa + Rashomon
    -> DeBERTa + Rashomon + Tableau
```

### 5.3 Stage C - MAGIC downstream validation

MAGIC evaluates whether the verified world state helps an LLM reason over natural-language multi-hop conflicts.

```text
context1 / context2
      ↓
claim and KG extraction
      ↓
Rashomon-Tableau inference
      ↓
valid/rejected worlds + relation marginal + entropy + proofs
      ↓
LLM
      ↓
ID + LOC + explanation
```

Primary comparison:

```text
Direct LLM
vs Compute-Matched LLM
vs Rashomon-Tableau only
vs Rashomon-Tableau -> LLM
```

---

## 6. Executed Results

### 6.1 DAFNA preliminary result

Marginal delayed commitment achieves 62% exact truth accuracy versus 61% for early hard commitment on the evaluated 100-book subset. This is a modest preliminary result, not evidence about multi-hop relation completion by itself.

### 6.2 WN18RR 50-row multi-hop pilot

Validated workflow run: **32799621678**  
Artifact: **9546119681**  
Artifact SHA-256: `14d6fd5fd5d1bd55ee69ca8c4e1a65715e315ef1fd2238a6337e965e6bc66320`

Protocol:

- n = 50 held-out relation queries;
- 11 candidate relations;
- 2-4 hop directed train-graph evidence;
- DeBERTa-v3 NLI scorer;
- epsilon = 0.05;
- gold evaluation-only.

Overall result:

| Metric | Result |
|---|---:|
| DeBERTa Top-1 accuracy | **16.0% (8/50)** |
| Rashomon gold coverage | **42.0% (21/50)** |
| Tableau gold retention | **42.0% (21/50)** |
| Rashomon-Tableau marginal Top-1 | **16.0% (8/50)** |
| Average Rashomon worlds | **3.82** |
| Average valid worlds | **3.82** |
| Average rejected worlds | **0.00** |
| Average entropy | **1.066** |

The Rashomon set preserves **13 gold relations that would be lost by Top-1 commitment**, producing an absolute retention gain of **+26 percentage points**.

By hop:

| Hop | n | Top-1 | Rashomon coverage | Tableau retention | RT Top-1 | Avg worlds |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | 19 | 5.3% | **36.8%** | 36.8% | 5.3% | 5.26 |
| 3 | 23 | 30.4% | **47.8%** | 47.8% | 30.4% | 2.91 |
| 4 | 8 | 0.0% | **37.5%** | 37.5% | 0.0% | 3.00 |

Stored result summary:

```text
results/wn18rr_multihop_completion_pilot_50.json
```

### 6.3 Interpretation

The pilot provides **positive evidence for H1** but **no evidence yet for H2**.

For H1, Top-1 selects only 8 gold relations, while Rashomon retains 21. The strongest descriptive example is the 4-hop stratum: Top-1 accuracy is 0%, while 37.5% of gold relations remain inside the near-optimal set. This supports the claim that early commitment discards potentially useful interpretations.

For H2, Tableau rejects zero worlds. Therefore:

```text
Rashomon gold coverage = Tableau gold retention = 42%
Top-1 accuracy         = RT marginal Top-1     = 16%
```

No Tableau gain can be claimed from this experiment.

Two limitations explain the result and define the next controlled experiments:

**Semantic scorer limitation.** Generic NLI support is not a strong direct relation-composition model for arbitrary WN18RR chains. A 16% Top-1 score is too low to make DeBERTa the assumed final scorer. KGE/relation-composition scorers must be tested as first-class alternatives.

**Tableau context limitation.** The pilot passes the selected evidence path plus the proposed relation into Tableau, not a broader ontology-relevant local graph. As a result, many reverse-edge conflicts, cycles, and cross-path inconsistencies cannot be observed. The zero rejection count is therefore a limitation of the current world context, not evidence that logical filtering is unnecessary.

The next Tableau ablation should compare:

```text
Path-only world context
vs
Bounded ontology-relevant local subgraph context
```

without changing candidate scores. This isolates whether additional graph context allows symbolic consistency filtering to contribute.

---

## 7. Prior MAGIC Diagnostics

Previous MAGIC experiments are diagnostic only:

- v2: provenance-metadata leakage;
- v3: about 25% gold-relevant candidate-path coverage after leakage removal;
- v4: about 47-57% usable candidate coverage after canonicalization and ontology-aware traversal;
- about 88% conditional DeBERTa contradiction scoring when a gold-relevant path was present on usable Command/GPT-OSS pilot rows;
- final decisions still bypassed Rashomon/Tableau marginals.

These findings motivated the current missing-relation-centered architecture.

---

## 8. Scientific Contribution and Current Evidence Boundary

Proposed mechanism:

```text
Multi-hop evidence
    -> semantic candidate scoring
    -> Rashomon uncertainty preservation
    -> Tableau logical consistency
    -> relation marginal
    -> downstream reasoning
```

Current evidence supports only part of this chain:

- **Rashomon retention:** provisionally supported by WN18RR 50-row pilot (+26pp gold coverage over Top-1).
- **Tableau filtering gain:** not yet supported; zero worlds were rejected under path-only context.
- **Final relation-ranking gain:** not yet supported; RT Top-1 remains 16%.
- **Downstream MAGIC gain:** not yet evaluated under the redesigned method.

This boundary is intentional. Components remain in the claimed method only if controlled experiments establish their contribution.

---

## 9. Falsification Criteria

The framework should be narrowed or rejected if larger controlled experiments show that:

- Rashomon coverage gains disappear under stronger scorers;
- Tableau local-subgraph filtering still rejects no useful incorrect worlds or disproportionately rejects gold worlds;
- final marginal ranking cannot improve on strong semantic/KGE baselines;
- downstream MAGIC ID/LOC does not improve when verified world information is supplied.

The paper does not claim a Tableau performance gain until that gain is measured.
