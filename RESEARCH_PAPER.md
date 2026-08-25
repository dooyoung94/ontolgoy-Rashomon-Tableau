# Rashomon-Tableau: Uncertainty-Aware Multi-Hop Relation Completion over Incomplete Ontologies

## Abstract

Knowledge graphs and ontologies are incomplete by construction: a relation between two entities may be unobserved even when the entities are connected through several intermediate relations. Conventional knowledge-graph completion typically ranks candidate relations and commits to a single Top-1 prediction. This early commitment is problematic when multiple multi-hop explanations are similarly plausible and when a high-scoring neural prediction violates hard ontology constraints. We propose **Rashomon-Tableau**, an uncertainty-aware relation-reasoning framework that represents near-optimal `(multi-hop path, candidate relation)` interpretations as alternative possible worlds, preserves them using a Rashomon set, rejects logically inconsistent worlds through ontology-guided Tableau reasoning, and marginalizes the surviving worlds into a relation belief rather than immediately collapsing to a single interpretation. Semantic plausibility is deliberately separated from logical validity: a DeBERTa-v3 NLI model is one interchangeable scorer, while Tableau is the consistency mechanism. The empirical program has three stages. First, DAFNA-EA Books provides preliminary evidence that delayed commitment can improve truth adjudication: marginal Rashomon inference achieves 62% exact truth accuracy and 84.13% author F1 on the evaluated 100-book subset, compared with 61%/84.04% for early hard commitment and 57% exact for official TruthFinder and AccuSim. Second, the main experiment evaluates 2–4 hop relation-masked subsets of FB15k-237, WN18RR, and UMLS, measuring not only Hits/MRR but gold-relation coverage, Tableau retention, valid-world ratio, and calibration. Third, MAGIC is used as a downstream natural-language test of whether verified Rashomon-Tableau world information improves multi-hop contradiction identification and localization when supplied to an LLM. Earlier MAGIC v2–v4 pilots are retained as diagnostics: after correcting representation leakage and candidate retrieval, DeBERTa reached roughly 88% conditional scoring on gold-relevant paths, while the previous pipeline still failed to make Tableau world marginals control the final decision. This motivated the present redesign in which Rashomon and Tableau become the core reasoning mechanism rather than an auxiliary diagnostic.

---

## 1. Research Problem

The target problem is **uncertainty-aware multi-hop relation completion under incomplete ontology semantics**.

Let an observed graph contain one or more paths between entities `h` and `t`:

\[
p=(h \xrightarrow{r_1} e_1 \xrightarrow{r_2} \cdots \xrightarrow{r_k} t),
\]

while the direct relation is missing:

\[
q=(h, ?, t).
\]

A standard completion system ranks candidate relations and returns:

\[
r^*=\arg\max_r s(p,r).
\]

This formulation hides two distinct uncertainties:

1. **path uncertainty:** several 2–4 hop paths may connect `h` and `t`;
2. **relation uncertainty:** several relations may receive near-identical semantic scores for the same path.

A third issue is logical consistency. A neural or embedding model can assign a high score to a relation that conflicts with hard ontology axioms, explicit negation, incompatibility, exclusivity, symmetry/inverse constraints, or derived closure.

The research question is therefore:

> **Can multi-hop relation completion improve when near-optimal path/relation interpretations are preserved as alternative worlds, logically invalid worlds are removed by Tableau reasoning, and final belief is obtained by marginalizing the surviving worlds instead of committing early to one Top-1 prediction?**

---

## 2. Central Hypotheses

### H1 — Delayed commitment
Retaining multiple near-optimal `(path, relation)` interpretations should preserve the gold relation more often than immediate Top-1 selection.

### H2 — Logical filtering
Ontology-guided Tableau should reject high-scoring but logically inconsistent relation worlds while retaining logically compatible gold worlds.

### H3 — Multi-hop benefit
The value of Rashomon retention should increase with path ambiguity and hop count because longer paths create more competing interpretations and spurious explanations.

### H4 — Downstream utility
Providing verified relation marginals, valid/rejected worlds, uncertainty, and proof information to an LLM should improve natural-language multi-hop contradiction identification/localization relative to raw-context and compute-matched LLM baselines.

The hypotheses are falsifiable. H1 fails if Rashomon retention does not improve gold coverage; H2 fails if Tableau removes gold worlds as often as it removes incorrect worlds; H3 fails if gains do not vary with ambiguity/hop count; H4 fails if verified world information does not improve MAGIC ID/LOC.

---

## 3. Method

### 3.1 Candidate space

For each missing-relation query `q=(h,?,t)`, candidate generation provides a set:

\[
\mathcal C(q)=\{c_i=(p_i,r_i,s_i)\}_{i=1}^{n},
\]

where:

- `p_i` is a multi-hop evidence path;
- `r_i` is a candidate direct relation between `h` and `t`;
- `s_i∈[0,1]` is semantic plausibility.

Candidate generation is intentionally modular. Paths can come from deterministic graph traversal; candidate relations can come from the relation vocabulary, KGE Top-K predictions, ontology rules, or an LLM proposal mechanism.

### 3.2 Semantic plausibility

The core does not require one scoring model. A scorer estimates how compatible a candidate relation is with the evidence path.

For the NLI condition, DeBERTa-v3 receives a naturalized path as premise and the candidate relation as hypothesis:

\[
Score_{NLI}(p,r)=\big(S(p,r),C(p,r),U(p,r)\big).
\]

`S` is used as semantic plausibility for relation completion; `C` and `U` remain diagnostic/calibration signals. DeBERTa does not create worlds and does not determine logical validity.

### 3.3 Rashomon relation set

Let:

\[
s^*=\max_{c\in\mathcal C(q)}s(c).
\]

The epsilon Rashomon set is:

\[
\mathcal R_\epsilon(q)=\{c\in\mathcal C(q): s(c)\ge s^*-\epsilon \land s(c)\ge\tau\}.
\]

This differs from ordinary Top-K retention. The set size adapts to score ambiguity: a clear winner can yield one world, while a flat score landscape retains several plausible interpretations.

### 3.4 Relation worlds

Each retained candidate defines a world:

\[
W_{p,r}=G_{obs}\cup\{r(h,t)\}.
\]

Path provenance is retained as evidence for that world, while the proposed direct relation is the world variable.

### 3.5 Tableau consistency filtering

Given ontology `O`, each world is checked:

\[
Tableau(O\cup W_{p,r})\in\{SAT,UNSAT\}.
\]

UNSAT worlds are rejected. The current relational Tableau detects/derives explicit negation clashes, ontology-declared incompatible predicates, exclusive-relation conflicts, hierarchy, transitivity, symmetry, inverse relations, and configured composition rules.

The valid set is:

\[
\mathcal W_{RT}(q)=\{W_{p,r}:W_{p,r}\in\mathcal R_\epsilon(q)\land SAT(O\cup W_{p,r})\}.
\]

This gives the two key operations complementary roles:

\[
Rashomon = ambiguity\ preservation,
\]

\[
Tableau = logical\ pruning.
\]

### 3.6 World posterior and relation marginal

A valid world receives normalized weight:

\[
P(W_i\mid q)=\frac{s_i}{\sum_{W_j\in\mathcal W_{RT}(q)}s_j}.
\]

Multiple paths can support the same relation. The relation posterior is therefore marginalized:

\[
P(r\mid q)=\sum_{W_i\in\mathcal W_{RT}(q)}P(W_i\mid q)\mathbf 1[r_i=r].
\]

The method also reports entropy:

\[
H(q)=-\sum_r P(r\mid q)\log P(r\mid q),
\]

which quantifies residual relation uncertainty after logical filtering.

---

## 4. Implementation

The redesigned model-agnostic core is implemented in:

```text
src/rashomon_tableau/multihop_completion.py
```

Main objects:

```text
RelationCandidate
RelationWorld
CompletionResult
```

Main functions:

```text
select_rashomon_candidates(...)
complete_missing_relation(...)
candidates_from_nli(...)
```

The implementation separates semantic scoring from symbolic reasoning. `RelationCandidate.score` can be supplied by DeBERTa, KGE, LLM, or another calibrated scorer without changing Rashomon/Tableau logic.

Unit tests in:

```text
tests/test_multihop_completion.py
```

verify:

1. near-optimal candidates survive epsilon selection;
2. a high-scoring ontology-incompatible world is rejected by Tableau;
3. multiple paths supporting the same relation are marginalized into one relation posterior.

---

## 5. Experimental Program

The empirical design contains **three linked stages with different purposes**.

### 5.1 Stage A — DAFNA-EA Books: preliminary delayed-commitment evidence

DAFNA evaluates competing truth assignments rather than missing KG relations. It is therefore used as preliminary evidence for the value of preserving multiple plausible worlds.

On the evaluated `AuthorsNamesList` 100-book subset:

- 100 gold books;
- 1,999 collapsed source-object claims;
- 227 sources;
- gold truth excluded from candidate generation and source-reliability updates.

Measured results:

| Method | Exact Truth Accuracy | Author F1 |
|---|---:|---:|
| **Rashomon Worlds — Marginal Reliability** | **62.00%** | **84.13%** |
| Rashomon Worlds — Hard Commit | 61.00% | 84.04% |
| Prior Atomic Resolution | 61.00% | 82.88% |
| Rashomon Worlds — Uniform | 58.00% | 80.38% |
| TruthFinder — official DAFNA-EA | 57.00% | 66.85% |
| AccuSim — official DAFNA-EA | 57.00% | 66.18% |

Candidate generation includes the gold truth world for **93%** of books. The primary interpretation is modest but useful: posterior/marginal delayed commitment improves exact recovery over early hard commitment by 1 pp and over the evaluated TruthFinder/AccuSim baselines by 5 pp exact. DAFNA does not by itself validate multi-hop relation completion.

### 5.2 Stage B — Multi-hop missing-relation benchmark: main experiment

This is the main evaluation of the proposed method.

Candidate datasets:

- **FB15k-237** — heterogeneous real-world relation vocabulary;
- **WN18RR** — lexical/semantic relation structure with inverse leakage reduced relative to WN18;
- **UMLS** — smaller ontology-rich biomedical relation graph suitable for symbolic constraints.

For each dataset, construct a relation-masked evaluation subset satisfying:

1. the gold direct relation `(h,r_gold,t)` is held out from the observed graph;
2. `h` and `t` remain connected through at least one evidence path;
3. examples are stratified by minimum path length: 2-hop, 3-hop, 4-hop;
4. gold labels are never used in candidate generation, scoring, epsilon selection, or Tableau filtering.

#### Baselines and ablations

| Variant | Question |
|---|---|
| KGE Top-1 | standard early commitment |
| KGE Top-K | is simple candidate retention enough? |
| DeBERTa Top-1 | semantic scoring without Rashomon |
| DeBERTa Top-K | fixed-size semantic retention |
| DeBERTa + Rashomon | effect of adaptive delayed commitment |
| **DeBERTa + Rashomon + Tableau** | full proposed method |
| Rashomon + LLM + Tableau | scorer robustness / model independence |
| Rashomon without ontology constraints | contribution of Tableau ontology knowledge |

#### Metrics

Standard ranking metrics:

- MRR;
- Hits@1;
- Hits@3;
- Hits@10.

Rashomon-specific diagnostics:

\[
GoldCoverage=\mathbf 1[r_{gold}\in\mathcal R_\epsilon],
\]

\[
GoldRetention=\mathbf 1[r_{gold}\in\mathcal W_{RT}],
\]

plus:

- Rashomon set size;
- number of candidate paths;
- Tableau rejection rate;
- valid-world ratio;
- false-rejection rate of gold worlds;
- relation entropy;
- calibration of `P(r|q)`;
- results by 2/3/4-hop stratum.

The critical ablation is:

\[
Top1 \rightarrow Rashomon \rightarrow Rashomon+Tableau.
\]

This separately tests whether gains come from preserving ambiguity and whether logical pruning adds value beyond candidate retention.

### 5.3 Stage C — MAGIC: downstream natural-language utility

MAGIC is repositioned as a downstream evaluation. It tests whether verified world information helps an LLM reason over natural-language multi-hop conflicts.

The target pipeline is:

```text
context1 / context2
      ↓
claim / KG extraction
      ↓
missing or ambiguous multi-hop relation queries
      ↓
semantic candidate scoring
      ↓
Rashomon Worlds
      ↓
Tableau filtering
      ↓
relation marginal + entropy + proofs
      ↓
LLM
      ↓
ID + LOC + explanation
```

Primary comparisons:

1. **Direct LLM:** raw contexts → answer;
2. **Compute-Matched LLM:** extra LLM reasoning budget without Rashomon/Tableau;
3. **Rashomon-Tableau Only:** symbolic/world decision without final LLM;
4. **Rashomon-Tableau → LLM:** raw context plus verified world information.

The key methodological comparison is (2) vs (4), because it controls for additional inference budget.

---

## 6. What Earlier MAGIC Experiments Established

The previous MAGIC work is retained as diagnostic evidence, not presented as the final architecture.

### 6.1 Structured MAGIC

Earlier experiments showed that static hard-ontology reasoning verified only a small fraction of released structured conflicts, while broader candidate-world generation retained substantially more gold-compatible explanations. A DeBERTa-v3 world scorer improved structured row conflict recall and exact localization over a weak lexical scorer. These results motivated semantic scoring but did not prove the redesigned missing-relation method.

### 6.2 Natural-language v2–v4 pilots

The paired natural-language experiments identified three engineering/methodological issues:

1. **v2 representation leakage:** provenance metadata in DeBERTa inputs artificially inflated contradiction performance;
2. **v3 candidate bottleneck:** after removing leakage, gold-relevant path coverage was only around 25%;
3. **v4 retrieval repair:** entity canonicalization, symmetric/inverse semantics, structural reverse traversal, and signed evidence increased gold-relevant candidate coverage to roughly 47–57% on usable Command/GPT-OSS rows.

When a gold-relevant candidate path was available in v4, DeBERTa conditional contradiction scoring was approximately **88%**. However, the previous final decision was still based directly on DeBERTa/LLM path scores while Rashomon/Tableau marginals remained diagnostic and often unresolved.

Therefore the correct conclusion is not that the old MAGIC pipeline validated Rashomon-Tableau. It demonstrated that:

> **candidate retrieval and semantic scoring can recover useful multi-hop evidence, but the final decision must be reorganized so that Rashomon world construction and Tableau consistency actually determine the verified reasoning state.**

This is the reason for the present redesign.

---

## 7. Expected Scientific Contribution

The intended contribution is not a new NLI model, KGE architecture, possible-world semantics, or Tableau algorithm in isolation.

The contribution is the following uncertainty-aware reasoning mechanism:

\[
\boxed{
MultiHopEvidence
\rightarrow SemanticCandidates
\rightarrow RashomonSet
\rightarrow TableauSAT
\rightarrow RelationMarginal
\rightarrow DownstreamReasoning
}
\]

Its significance is threefold.

### 7.1 Uncertainty-preserving ontology completion

Instead of forcing an incomplete ontology into a deterministic completion, the method preserves several near-optimal interpretations until logical evidence is sufficient to remove them.

### 7.2 Separation of statistical plausibility and logical validity

Neural/KGE models answer:

> “How plausible is this relation given the evidence?”

Tableau answers:

> “Can this relation coexist with the ontology and observed facts?”

A high neural score therefore cannot override hard logical inconsistency.

### 7.3 Verified reasoning state for LLMs

The downstream LLM does not need to invent the reasoning space from scratch. It receives a structured state containing:

- plausible relations;
- supporting paths;
- rejected worlds and clash reasons;
- relation marginals;
- residual uncertainty/entropy;
- derivation/proof information.

The hypothesis is that verified reasoning context can improve multi-hop natural-language decisions while reducing reliance on unconstrained latent reasoning.

---

## 8. Research Questions

### RQ1
Does adaptive Rashomon retention improve multi-hop gold-relation recovery over Top-1 and fixed Top-K completion?

### RQ2
Does ontology-guided Tableau improve precision/calibration by removing logically inconsistent worlds without materially reducing gold-relation retention?

### RQ3
How do the effects of Rashomon retention and Tableau filtering vary with hop count, number of alternative paths, and score ambiguity?

### RQ4
Does a downstream LLM achieve better MAGIC ID/LOC when given verified Rashomon-Tableau evidence than when given equivalent additional compute without that structure?

---

## 9. Research Boundary

This work does **not** claim:

- that DeBERTa is a new relation-completion architecture;
- that all missing KG relations should be inferred from text alone;
- that logical satisfiability alone determines truth;
- that DAFNA results constitute a multi-hop KGC benchmark;
- that the earlier MAGIC v2–v4 conflict recalls are final Rashomon-Tableau performance;
- global SOTA before the relation-masked benchmark is executed.

The paper's main empirical claim will be made only after the Stage B benchmark is built and the controlled `Top-1 → Rashomon → Rashomon+Tableau` ablations are run.

---

## 10. Current Status and Next Experiment

### Already measured

- DAFNA-EA delayed-commitment results;
- structured MAGIC candidate-world/scorer diagnostics;
- natural-language MAGIC v2–v4 candidate/scoring pilots.

### Implemented in the redesigned core

- model-agnostic relation candidates;
- adaptive epsilon Rashomon retention;
- `(path, relation)` possible worlds;
- ontology-guided Tableau SAT filtering;
- rejection explanations;
- marginalization across multiple valid paths;
- relation posterior entropy.

### Immediate next experiment

Build a reproducible 2–4 hop relation-masking protocol for FB15k-237, WN18RR, and UMLS, then measure:

```text
KGE Top-1
DeBERTa Top-1
DeBERTa Top-K
DeBERTa + Rashomon
DeBERTa + Rashomon + Tableau
```

Only after this core experiment is validated should the final MAGIC downstream pipeline be rebuilt around `Rashomon-Tableau → LLM` rather than `LLM/NLI → direct conflict decision`.
