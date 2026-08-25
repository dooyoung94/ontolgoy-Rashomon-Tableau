# Peer Group and Comparison Protocol

## 1. Why two comparison layers are required

The current project has two evaluation settings:

1. **WN18RR search-policy stress test** — controlled iterative path search with a held-out target relation/entity pair.
2. **MAGIC conflict preservation** — external-gold competing-evidence preservation.

Most closest published peers are evaluated as **KGQA / GraphRAG systems** on WebQSP, CWQ, HotpotQA, or similar tasks. Their published answer accuracy must therefore not be numerically compared with our WN18RR search-success percentage.

The paper should use:

```text
Layer A: Methodological peer comparison
Layer B: Apples-to-apples shared-benchmark performance comparison
```

---

## 2. Methodological peer group

| Method | Venue/year | Search unit | Pruning / scale policy | Main goal | Key distinction |
|---|---|---|---|---|---|
| Think-on-Graph (ToG) | ICLR 2024 | relation/entity reasoning paths | iterative fixed Top-N beam pruning | training-free KGQA reasoning | canonical fixed-width baseline |
| Think-on-Graph 2.0 | ICLR 2025 | graph + document context | alternating graph/context retrieval and pruning | deep faithful RAG | broader hybrid retrieval architecture |
| Paths-over-Graph (PoG) | 2024 | multi-hop paths | three-stage graph/LLM/PLM pruning | faithful path reasoning | multi-stage relevance filtering |
| FastToG | AAAI 2025 | graph communities | coarse/fine community pruning | wider/deeper/faster KG reasoning | community-level rather than path-boundary pruning |
| Query-Driven Adaptive Graph Retrieval | Electronics 2026 | heterogeneous graph paths | adaptive K from query complexity and path-score distribution | multi-hop QA evidence control | establishes that adaptive retrieval scale is prior work |
| Flow-RAG | Knowledge-Based Systems 2026 | time-state graph flow | distribution-aware adaptive decision boundary | KGQA retrieval efficiency/generalization | strong recent peer for adaptive score-distribution pruning |
| **BADP (ours)** | — | partial reasoning paths | Top-K core + paths within delta of K-th score boundary | reduce irreversible pruning regret | isolates Top-K boundary uncertainty and evaluates validity/cost jointly |

---

## 3. What is and is not novel

### Do not claim

```text
first adaptive pruning
first dynamic beam width
first multi-path KG reasoning
first score-distribution-aware pruning
Rashomon always beats Top-K
```

Those claims conflict with existing literature.

### Intended novelty

```text
1. Treat the K/K+1 cutoff as an uncertainty boundary.
2. Define pruning regret as irreversible loss of all viable prefixes.
3. Delay pruning locally at that boundary rather than globally widening the search.
4. Evaluate preserved-state validity, not survival alone.
5. Compare policies under matched search budgets / Pareto trade-offs.
```

---

## 4. Core comparison metrics

### Search correctness / preservation

- Search Success
- Gold/Viable Path Survival
- Conflict Path Survival (MAGIC)
- Conflict Information Loss
- Query Pruning Regret
- Depth-wise Viable Prefix Survival

### Retained-set quality

- Viability Precision
- Viability Recall
- Viability F1
- External-gold Precision / Recall / F1 on MAGIC
- Invalid Retention Rate

### Efficiency

- Average Active Width
- Average Expanded Candidates
- Unique scorer calls
- LLM calls when applicable
- Retrieved context tokens on KGQA
- Retrieval latency / end-to-end latency

### Robustness / regime analysis

- Hop depth
- Candidate branching factor
- Top-K boundary margin `Delta_K = s_(K)-s_(K+1)`
- Top-2/global score margin
- Score entropy or concentration

### Trade-off analysis

Primary figures should show:

```text
Search Success vs Expanded Candidates
Pruning Regret vs Active Width
Viability F1 vs Active Width
Answer F1/EM vs Context Tokens   (shared KGQA benchmark)
```

Pareto-frontier reporting is preferred to a single unconstrained accuracy number.

---

## 5. Fair-comparison protocol

When comparing pruning policies inside our framework:

```text
same graph
same query
same scorer
same expansion operator
same hop limit
same candidate generation
only pruning policy changes
```

When comparing adaptive methods with Top-K:

```text
Top-3 and Top-5 = budget anchors
adaptive parameter sweep on development data
choose nearest-cost configuration
freeze parameter
report held-out test result
```

The current automated WN18RR experiment performs the exploratory version of this matching using average active width and expansion cost. The final publication experiment must separate development and test selection.

---

## 6. Shared-benchmark direct peer experiment

To compare against ToG-family systems directly, add a KGQA benchmark such as:

```text
WebQSP
CWQ
```

Recommended experiment matrix:

| System | Scorer/retriever | Pruning |
|---|---|---|
| ToG-style control | same LLM/relevance scorer where possible | fixed Top-N |
| Global band | same scorer | best-minus-epsilon |
| Relative-loss | same scorer | loss-relative band |
| BADP | same scorer | boundary-aware delayed pruning |
| No-prune / high-budget ceiling | same scorer | minimal pruning |

Report final-answer and search-state metrics together.

---

## 7. References

1. Sun, J. et al. Think-on-Graph: Deep and Responsible Reasoning of Large Language Model on Knowledge Graph. ICLR 2024. arXiv:2307.07697.
2. Ma, S. et al. Think-on-Graph 2.0: Deep and Faithful Large Language Model Reasoning with Knowledge-guided Retrieval Augmented Generation. ICLR 2025. arXiv:2407.10805.
3. Tan, X. et al. Paths-over-Graph: Knowledge Graph Empowered Large Language Model Reasoning. arXiv:2410.14211, 2024.
4. Liang, X.; Gu, Z. Fast Think-on-Graph: Wider, Deeper and Faster Reasoning of Large Language Model on Knowledge Graph. AAAI 2025. DOI:10.1609/aaai.v39i23.34635.
5. Wang, H. et al. A Query-Driven Graph Retrieval Framework with Adaptive Pruning for Multi-Hop Question Answering. Electronics 2026, 15(6),1263. DOI:10.3390/electronics15061263.
6. Zhang, W. et al. Flow-RAG: Retrieval-augmented generation for knowledge graph question answering via gated flow propagation. Knowledge-Based Systems 348 (2026),116400. DOI:10.1016/j.knosys.2026.116400.
