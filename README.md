# Rashomon-Tableau

## Uncertainty-Aware Multi-Hop Relation Completion over Incomplete Ontologies

> **Core thesis:** when an ontology or knowledge graph contains a missing or ambiguous relation, a reasoner should not commit immediately to one Top-1 relation. It should preserve multiple near-optimal `(multi-hop path, relation)` interpretations as Rashomon Worlds, reject logically inconsistent worlds with Tableau reasoning, and marginalize the surviving worlds into a calibrated relation belief.

```text
Observed KG / Ontology
        ↓
Multi-hop paths between h and t
        ↓
Candidate relations r1 ... rk
        ↓
Semantic plausibility scorer
(DeBERTa / KGE / LLM; interchangeable)
        ↓
Rashomon set of near-optimal
(path, relation) candidates
        ↓
Possible worlds W1 ... Wn
        ↓
Ontology + Tableau SAT filtering
        ↓
Valid worlds only
        ↓
Relation marginal / uncertainty
        ↓
Verified relation inference
        ↓
Downstream LLM reasoning (MAGIC)
```

---

# 1. Research problem

The target is **not ordinary Top-1 knowledge-graph completion** and not merely contradiction detection.

We study the case where observed facts form one or more multi-hop paths:

\[
h \xrightarrow{r_1} e_1 \xrightarrow{r_2} \cdots \xrightarrow{r_k} t
\]

but the direct relation between `h` and `t` is missing or ambiguous:

\[
(h, ?, t).
\]

Conventional completion commits to a single relation:

\[
(h,?,t) \rightarrow r^*.
\]

Rashomon-Tableau instead preserves a set of near-optimal interpretations:

\[
\mathcal R_\epsilon(q)=\{(p,r): s(p,r) \ge s^* - \epsilon\},
\]

constructs one possible world per retained `(path, relation)` interpretation, and keeps only worlds satisfying the ontology:

\[
\mathcal W_{RT}(q)=\{W_{p,r}: SAT(O \cup G_{obs} \cup W_{p,r})\}.
\]

The final relation belief is obtained by marginalizing valid worlds rather than forcing an early single-world decision.

---

# 2. Why Rashomon + Tableau

The two components solve opposite problems.

- **Rashomon:** preserve ambiguity and avoid premature Top-1 commitment.
- **Tableau:** remove plausible-looking but logically impossible worlds.

Therefore:

\[
\text{Semantic Plausibility} \neq \text{Logical Consistency}.
\]

A candidate can receive a high neural/NLI score and still violate ontology constraints. Conversely, several candidates can be similarly plausible and all remain logically possible. The method explicitly represents both cases.

---

# 3. Role of DeBERTa

DeBERTa is **not the novelty and not the final reasoner**.

`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` is used as one possible semantic compatibility scorer for a candidate relation against its multi-hop evidence path.

For candidate `(p,r)` it can produce:

\[
S(p,r), C(p,r), U(p,r)
\]

for support, contradiction, and unresolved mass. The Rashomon-Tableau core only consumes a normalized plausibility score; the scorer can be replaced by KGE, another NLI model, or an LLM without changing the symbolic method.

---

# 4. New core implementation

```text
src/rashomon_tableau/multihop_completion.py
  RelationCandidate
  RelationWorld
  CompletionResult
  select_rashomon_candidates(...)
  complete_missing_relation(...)
  candidates_from_nli(...)
```

The core algorithm is:

1. collect candidate `(path, relation)` interpretations;
2. retain near-optimal candidates using an epsilon Rashomon set;
3. construct `W = G_obs ∪ {(h,r,t)}` for each retained candidate;
4. run ontology-aware `RelationalTableau.check(W)`;
5. discard UNSAT worlds;
6. normalize semantic weights over SAT worlds;
7. marginalize worlds that imply the same relation;
8. return relation marginal, entropy, valid-world ratio, and rejected-world explanations.

Regression tests:

```text
tests/test_multihop_completion.py
```

cover delayed commitment, Tableau rejection of incompatible completions, and marginalization across multiple paths supporting the same relation.

---

# 5. Experimental program

The paper is now organized as **three linked validation stages**, not one MAGIC-only benchmark.

## Stage A — DAFNA-EA Books: does delayed commitment have value?

DAFNA is the preliminary truth-discovery experiment.

Multiple sources support competing author truths. Rashomon Worlds preserves several plausible truth assignments instead of committing early to one MAP truth.

Measured on the 100-book `AuthorsNamesList` subset:

| Method | Exact Truth Accuracy | Author F1 |
|---|---:|---:|
| **Rashomon Worlds — Marginal Reliability** | **62.00%** | **84.13%** |
| Rashomon Worlds — Hard Commit | 61.00% | 84.04% |
| Prior Atomic Resolution | 61.00% | 82.88% |
| Rashomon Worlds — Uniform | 58.00% | 80.38% |
| TruthFinder — official DAFNA-EA | 57.00% | 66.85% |
| AccuSim — official DAFNA-EA | 57.00% | 66.18% |

Candidate generation contains the gold truth world for **93%** of books. This supports the preliminary claim that delayed commitment can be useful, but DAFNA is not the main missing-relation benchmark.

## Stage B — Multi-hop missing relation: main experiment

This is the **main algorithmic evaluation**.

Candidate datasets:

- FB15k-237
- WN18RR
- UMLS

The evaluation should use relation-masked examples where `h` and `t` remain connected by 2–4 hop evidence paths. The central query is not merely whether a Top-1 relation is predicted, but whether the gold relation survives the Rashomon set and Tableau filtering.

Planned baselines / ablations:

| Variant | Purpose |
|---|---|
| KGE Top-1 | conventional early commitment |
| KGE Top-K | simple candidate retention |
| DeBERTa Top-1 | semantic scorer without Rashomon |
| DeBERTa + Rashomon | effect of delayed commitment |
| **DeBERTa + Rashomon + Tableau** | proposed method |
| Rashomon + LLM + Tableau | scorer replacement / robustness |

Primary metrics:

- MRR / Hits@1 / Hits@3 / Hits@10 where applicable;
- Gold Relation Coverage in the candidate set;
- Gold Relation Retention after Tableau;
- Rashomon set size;
- Tableau rejection rate;
- valid-world ratio;
- relation-marginal calibration / entropy;
- performance by hop count (2-hop / 3-hop / 4-hop).

## Stage C — MAGIC: downstream LLM utility

MAGIC is **not the main Rashomon benchmark anymore**. It becomes a downstream test:

> Does verified multi-hop possible-world information improve natural-language contradiction identification and localization?

Target comparison:

1. Direct LLM;
2. Compute-Matched LLM;
3. Rashomon-Tableau only;
4. **Rashomon-Tableau values → LLM**.

The LLM receives structured evidence such as:

```text
candidate relations / paths
valid and rejected worlds
relation marginal
support / contradiction / unresolved mass
world entropy
Tableau rejection reasons
```

and returns MAGIC ID / LOC / explanation.

---

# 6. What the previous MAGIC v2–v4 experiments established

The earlier natural-language MAGIC experiments are retained as **diagnostic evidence**, not as the final method.

Key findings:

- v2 exposed provenance-metadata leakage in DeBERTa input.
- v3 removed that leakage and revealed candidate-path recall of only about 25%.
- v4 improved candidate retrieval using entity canonicalization, symmetric/inverse relation semantics, structural reverse traversal, and signed evidence.
- In v4, gold-relevant candidate coverage rose to roughly 47–57% on the usable Command/GPT-OSS rows.
- Conditional DeBERTa scoring was about 88% when the gold-relevant candidate path was available.
- Rashomon/Tableau world marginals remained disconnected from the final binary decision, which motivated the present redesign.

Therefore the v2–v4 result should be interpreted as:

> **ontology-aware candidate retrieval + DeBERTa is promising, but a pipeline where the scorer directly decides conflict is not the intended Rashomon-Tableau method.**

The redesigned core moves Rashomon and Tableau **before** downstream LLM decision-making.

---

# 7. Research questions

### RQ1 — Rashomon retention
Does retaining multiple near-optimal `(path, relation)` interpretations improve gold-relation coverage and recovery compared with early Top-1 commitment?

### RQ2 — Tableau filtering
Can ontology-guided Tableau reasoning reject semantically plausible but logically inconsistent multi-hop completion worlds while retaining the gold relation?

### RQ3 — Downstream value
Does providing verified Rashomon-Tableau world information improve LLM multi-hop contradiction ID/LOC over raw-context and compute-matched LLM baselines?

---

# 8. Intended contribution

The intended contribution is an **uncertainty-aware multi-hop relation reasoning framework** for incomplete ontologies:

> **Multi-hop evidence → semantic candidate scoring → Rashomon near-optimal worlds → Tableau consistency filtering → relation marginal → downstream reasoning.**

This work does not claim that possible worlds, Tableau, DeBERTa, KGE, or LLMs are individually new. The contribution is their specific division of labor:

1. neural/KGE models estimate plausibility;
2. Rashomon preserves several near-optimal interpretations;
3. Tableau enforces hard ontology consistency;
4. valid worlds are marginalized instead of prematurely collapsed;
5. the resulting verified reasoning state can be consumed by an LLM.

---

# 9. Current research status

**Completed / measured**

- DAFNA-EA Books delayed-commitment experiment;
- MAGIC structured possible-world diagnostics;
- DeBERTa world-scoring ablations;
- MAGIC natural-language v2–v4 engineering pilots;
- ontology-aware multi-hop path retrieval fixes.

**Implemented in the redesign**

- model-agnostic `RelationCandidate`;
- epsilon Rashomon candidate retention;
- per-candidate relation-world construction;
- ontology-aware Tableau SAT filtering;
- marginalization across valid `(path, relation)` worlds;
- entropy / valid-world diagnostics.

**Next empirical milestone**

Construct a reproducible 2–4 hop relation-masking benchmark on FB15k-237 / WN18RR / UMLS and run the controlled ablations before returning to the final MAGIC downstream experiment.
