# Rashomon-Tableau: Uncertainty-Aware Multi-Hop Relation Completion over Incomplete Ontologies

## Abstract

Knowledge graphs and ontologies are incomplete by construction. Two entities can be connected through several intermediate relations while their direct relation remains missing or ambiguous. Conventional completion methods typically rank candidate relations and commit to one Top-1 prediction. This early commitment can discard plausible alternatives and can also select a high-scoring relation that violates hard ontology constraints.

We propose **Rashomon-Tableau**, an uncertainty-aware multi-hop relation reasoning framework. The method keeps near-optimal `(multi-hop path, candidate relation)` interpretations as possible worlds, preserves them through an adaptive Rashomon set, rejects logically inconsistent worlds through ontology-guided Tableau reasoning, and marginalizes the surviving worlds into a relation belief. Semantic plausibility and logical validity are deliberately separated: DeBERTa-v3 is one interchangeable semantic scorer, while Tableau enforces ontology consistency.

The empirical program has three linked stages. DAFNA-EA Books provides preliminary evidence that delayed commitment can improve truth adjudication. The main experiment evaluates 2-4 hop relation-masked knowledge-graph examples, beginning with WN18RR and later extending to FB15k-237 and UMLS. MAGIC is then used only as a downstream natural-language test of whether the verified Rashomon-Tableau reasoning state improves LLM contradiction identification and localization.

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

The value of uncertainty preservation should increase as path ambiguity and hop count increase.

### H4 - Downstream utility

Supplying valid/rejected worlds, relation marginals, uncertainty, and proof information to an LLM should improve multi-hop contradiction ID/LOC relative to raw-context and compute-matched LLM baselines.

---

## 3. Method

### 3.1 Candidate space

For a query `q=(h,?,t)`, candidate generation produces items of the form:

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

`S(path,r)` is used as semantic plausibility in the first relation-completion pilot. DeBERTa does not generate worlds and does not determine logical validity.

### 3.3 Rashomon set

Let `best_score` be the maximum candidate score. The adaptive epsilon set is:

```text
R_epsilon(q) = {
  candidate |
  score(candidate) >= best_score - epsilon
  and score(candidate) >= min_score
}
```

Unlike fixed Top-K retention, the number of worlds depends on score ambiguity.

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

The current relational Tableau supports:

- explicit negation clashes;
- incompatible relations;
- exclusive relations;
- hierarchy;
- transitivity;
- symmetry;
- inverse relations;
- relation composition;
- irreflexive constraints;
- antisymmetric constraints.

The two central operations therefore have different roles:

```text
Rashomon = ambiguity preservation
Tableau  = logical pruning
```

### 3.6 Relation marginal

For all valid worlds, semantic scores are normalized into world weights:

```text
P(W_i | q) = score_i / sum(score_j over valid worlds)
```

If multiple worlds imply the same relation, their mass is summed:

```text
P(r | q) = sum P(W_i | q) for every valid world whose relation is r
```

Residual uncertainty is reported with entropy:

```text
H(q) = - sum_r P(r|q) * log(P(r|q))
```

---

## 4. Implementation

Core:

```text
src/rashomon_tableau/multihop_completion.py
```

Benchmark construction:

```text
src/rashomon_tableau/kg_multihop_benchmark.py
scripts/download_relation_benchmarks.py
scripts/build_multihop_relation_benchmark.py
scripts/evaluate_multihop_relation_completion.py
```

WN18RR ontology rules:

```text
config/wn18rr_ontology_rules.yaml
```

The WN18RR pilot declares conservative semantics including:

- `_hypernym` as transitive, irreflexive, antisymmetric;
- `_instance_hypernym` as irreflexive;
- selected symmetric relations such as `_similar_to`;
- composition of `_instance_hypernym` followed by `_hypernym`.

These constraints are independent of test labels and are used only by Tableau.

---

## 5. Experimental Program

### 5.1 Stage A - DAFNA-EA Books

DAFNA is a preliminary truth-discovery experiment rather than a missing-relation benchmark.

Measured on the evaluated 100-book `AuthorsNamesList` subset:

| Method | Exact Truth Accuracy | Author F1 |
|---|---:|---:|
| **Rashomon Worlds - Marginal Reliability** | **62.00%** | **84.13%** |
| Rashomon Worlds - Hard Commit | 61.00% | 84.04% |
| Prior Atomic Resolution | 61.00% | 82.88% |
| Rashomon Worlds - Uniform | 58.00% | 80.38% |
| TruthFinder - official DAFNA-EA | 57.00% | 66.85% |
| AccuSim - official DAFNA-EA | 57.00% | 66.18% |

Gold truth is present in the candidate-world set for 93% of evaluated books. The measured interpretation is limited: delayed marginal commitment improves exact truth recovery over early hard commitment by 1 percentage point on this subset.

### 5.2 Stage B - Multi-hop missing relation: main experiment

Primary dataset: **WN18RR**.

Additional planned datasets: FB15k-237 and UMLS.

A benchmark example is retained only if:

1. the target direct triple is in the held-out dev/test split;
2. the target head and tail are connected by a 2-4 hop directed path in the train graph;
3. the gold direct relation is not injected into path discovery or scoring;
4. gold is used only after prediction for evaluation.

Controlled comparison:

| Variant | Question |
|---|---|
| DeBERTa Top-1 | What happens under early semantic commitment? |
| DeBERTa + Rashomon | Does delayed commitment preserve the gold relation? |
| **DeBERTa + Rashomon + Tableau** | Does logical filtering improve final inference? |
| KGE Top-1 / Top-K | Embedding baseline |
| Rashomon + LLM + Tableau | Scorer-independence test |

Primary metrics:

- Top-1 accuracy;
- Rashomon gold coverage;
- gold retention after Tableau;
- Rashomon-Tableau marginal Top-1 accuracy;
- average Rashomon set size;
- valid and rejected world counts;
- entropy;
- 2-hop / 3-hop / 4-hop results.

The main ablation is:

```text
Top-1 -> Rashomon -> Rashomon + Tableau
```

### 5.3 Stage C - MAGIC downstream validation

MAGIC is no longer the core benchmark. It tests whether a verified world state helps an LLM reason over natural-language multi-hop conflicts.

```text
context1 / context2
      ↓
claim and KG extraction
      ↓
missing / ambiguous relation queries
      ↓
Rashomon-Tableau inference
      ↓
valid worlds + rejected worlds + relation marginal + entropy + proofs
      ↓
LLM
      ↓
ID + LOC + explanation
```

Primary comparisons:

1. Direct LLM
2. Compute-Matched LLM
3. Rashomon-Tableau only
4. **Rashomon-Tableau -> LLM**

The key comparison is Compute-Matched LLM vs Rashomon-Tableau -> LLM.

---

## 6. Prior MAGIC Diagnostics

The previous MAGIC work is retained as diagnostic evidence only.

- v2 showed provenance-metadata leakage in DeBERTa input.
- v3 removed leakage and exposed gold-relevant candidate-path coverage of about 25%.
- v4 improved retrieval with canonicalization and ontology-aware traversal; usable candidate coverage rose to roughly 47-57%.
- Conditional DeBERTa scoring was about 88% when a gold-relevant path was present on usable Command/GPT-OSS pilot rows.
- The previous binary decision still bypassed Rashomon/Tableau marginals.

Therefore the earlier MAGIC pipeline does not validate the redesigned method. It motivates the redesign.

---

## 7. Results

### 7.1 DAFNA preliminary result

The DAFNA result supports H1 weakly but measurably: preserving and marginalizing multiple truth worlds produced a small gain over early hard commitment on the evaluated subset.

### 7.2 WN18RR multi-hop pilot

The active pilot evaluates held-out WN18RR targets that remain connected by 2-4 hop train-graph paths. It compares DeBERTa Top-1, epsilon Rashomon retention, and Rashomon-Tableau marginal inference under the same candidate relation vocabulary.

The validated result JSON is stored at:

```text
results/wn18rr_multihop_completion_pilot.json
```

This section is updated only from the executed workflow artifact; planned or simulated values are not reported.

---

## 8. Scientific Contribution

The intended contribution is not a new NLI model, KGE architecture, possible-world formalism, or Tableau algorithm in isolation.

The proposed mechanism is:

```text
Multi-hop evidence
    -> semantic candidate scoring
    -> Rashomon uncertainty preservation
    -> Tableau logical consistency
    -> relation marginal
    -> downstream reasoning
```

The significance is threefold:

1. **Uncertainty-preserving ontology completion:** near-optimal alternatives survive until evidence or logic can eliminate them.
2. **Separation of plausibility and validity:** neural scores estimate semantic fit, while Tableau enforces hard constraints.
3. **Verified reasoning state for LLMs:** downstream LLMs receive structured candidate worlds, rejected clashes, relation marginals, and uncertainty rather than inventing the reasoning space from raw text alone.

---

## 9. Falsification Criteria

The framework should be rejected or narrowed if the main experiment shows any of the following:

- Rashomon gold coverage is not meaningfully higher than Top-1 accuracy;
- Tableau removes gold worlds at a similar or higher rate than incorrect worlds;
- final Rashomon-Tableau marginal accuracy does not improve over the semantic baseline;
- apparent gains disappear under a stronger KGE or compute-matched control;
- downstream MAGIC ID/LOC does not improve when verified world information is supplied.

The method is retained only if the measured data justify each claimed component.
