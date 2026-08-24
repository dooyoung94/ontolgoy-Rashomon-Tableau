# Rashomon-Tableau

## Provenance-Aware Logical Conflict Localization and Truth Resolution from Conflicting Sources

> **핵심 연구 질문:** 서로 상충하는 source를 먼저 합치거나 버리지 않고, 각 claim의 논리적 의미와 provenance를 유지한 채 conflict를 분석하면 실제 truth를 더 잘 찾을 수 있는가?

Rashomon-Tableau는 세 문제를 분리한다.

```text
1. Logical Reasoning
   Claim + Ontology / Rules
              ↓
   Implicit entailment / contradiction

2. Conflict Localization
   Source → Claim → Rule → Derived Claim → Conflict
              ↓
   Exact / Partial / Conflict

3. Rashomon Truth Resolution
   Source reliability
        + atomic proposition support
        + logical compatibility
        + provenance
              ↓
   Candidate truth + confidence
```

여기서 **Rashomon**은 ML의 near-optimal model set을 의미하지 않는다. 동일 사건에 대한 상충된 관점을 성급히 제거하지 않고 함께 분석한 뒤, 어떤 주장이 truth에 더 잘 정당화되는지 판정한다는 문제의식을 의미한다.

---

# Current Evidence

## 1. Direct Truth-Discovery Comparison — DAFNA-EA Books

공개 DAFNA-EA Books에서 동일한 100-book `AuthorsNamesList` gold subset을 사용해 우리 방법과 **공식 qcri/DAFNA-EA Java 구현**을 실제 실행하여 비교한다.

- Gold books: **100**
- Source-object claims: **1,999**
- Sources: **227**

| Method | Implementation | Exact Truth Accuracy | Author F1 |
|---|---|---:|---:|
| **Rashomon-Tableau Atomic Resolution** | this repo | **61.00%** | **82.88%** |
| TruthFinder | official DAFNA-EA | 57.00% | 66.85% |
| AccuSim | official DAFNA-EA | 57.00% | 66.18% |
| 2-Estimates | official DAFNA-EA | 54.00% | 65.28% |
| 3-Estimates | official DAFNA-EA | 53.00% | 65.45% |
| Accu | official DAFNA-EA | 53.00% | 65.45% |
| Reliability-Weighted Whole Claim | this repo | 45.00% | 75.24% |
| Whole-Claim Majority | this repo | 44.00% | 73.57% |

`LTM` is stochastic in the official implementation and showed unstable single-run values, so it should be reported as repeated-run mean ± standard deviation rather than used as a headline single number.

The key modeling difference is that a multi-valued claim is not treated as one indivisible string.

```text
Gold candidate = {A, B}

Source 1 = {A, B} → exact
Source 2 = {A}    → partial support
Source 3 = {C}    → conflict
```

Measured outputs:

- [`results/truth_discovery_books_metrics.json`](./results/truth_discovery_books_metrics.json)
- [`results/dafna_official_comparison.md`](./results/dafna_official_comparison.md)
- [`results/dafna_official_comparison.json`](./results/dafna_official_comparison.json)

---

## 2. Modern Conflict Stress Test — MAGIC (Findings EMNLP 2025)

MAGIC is a KG-derived benchmark for **inter-context conflict detection/localization**, including explicit single-hop and indirect multi-hop conflicts.

A reproducible diagnostic is included:

```bash
python scripts/evaluate_magic_structured.py
```

Current result over all **1,080** released conflict examples:

| Type | Detection |
|---|---:|
| 1 single-hop | 98.56% |
| 2 single-hop | 98.70% |
| 3 single-hop | 100.00% |
| 4 single-hop | 100.00% |
| 1 multi-hop | 27.00% |
| 2 multi-hop | 41.14% |
| 3 multi-hop | 37.50% |
| 4 multi-hop | 38.00% |
| **Overall** | **63.15%** |

This result is intentionally treated as a **failure analysis**, not a headline SOTA claim.

- direct conflict patterns are recognized well;
- MAGIC multi-hop conflicts are built from 2–3 logically connected triplets;
- the current local pairwise rules cannot reconstruct enough relation-composition semantics;
- graph-path / ontology composition is therefore the next reasoning gap to solve.

**Important:** the evaluator uses the released structured `original_triplet` / `perturb_triplet` fields. It is not directly comparable to MAGIC's natural-language LLM ID/LOC scores. Also, `pair_localization_coverage=1.0` is not 100% localization accuracy; it only means a best pair can always be selected from benchmark-provided structured fields.

---

## 3. Logical Core — FOLIO

Current parser-supported FOLIO validation fragment: **28 / 204** examples.

| Method | Accuracy | Macro-F1 |
|---|---:|---:|
| Forward Horn | 75.00% | 74.18% |
| Semantic Clause Tableau | **96.43%** | **96.33%** |

**96.43% is not full-FOLIO accuracy.** Grammar coverage is 13.73%.

---

## 4. Dual-Direction Contradiction — LogicNLI

Official structured `test_logic`: **2,000 statements**.

| Method | Accuracy | Macro-F1 | Paradox F1 |
|---|---:|---:|---:|
| Single-Path Forward | 74.00% | 65.78% | 0.00% |
| Dual-Direction Proof Check | **98.40%** | **98.40%** | **97.92%** |

This is a symbolic reasoning-layer evaluation, not an end-to-end NLP comparison.

---

# 2025–2026 Research Positioning

The closest recent work changes the novelty boundary substantially.

| Work | Venue | Main idea | Difference from Rashomon-Tableau |
|---|---|---|---|
| MAGIC | Findings EMNLP 2025 | KG-based inter-context conflict detection/localization benchmark | benchmark/stress test; does not estimate source reliability or truth from source histories |
| FaithfulRAG | ACL 2025 | fact-level conflict modeling for context-faithful RAG | parametric-vs-retrieved conflict and answer generation, not source-level truth discovery |
| DRAGged into CONFLICTS | 2025 | realistic conflicting search sources + correct answer | closest future end-to-end dataset; requires a frozen claim-extraction layer first |
| TCR | AAAI 2026 | transparent semantic/factual/self-answerability signals | neural RAG conflict handling, primarily parametric-vs-context |
| When Facts Change | Findings ACL 2026 | temporal knowledge conflict benchmark | temporal conflict special case; reinforces separation of detection and truth selection |
| **KCR** | **ACL 2026** | text/KG reasoning traces + RLVR for logical conflict adjudication | **strongest conceptual overlap**; learned LLM adjudication vs symbolic source-provenance/reliability adjudication |

Detailed comparison: **[`MODERN_BASELINES.md`](./MODERN_BASELINES.md)**

## Updated novelty boundary

This project does **not** claim novelty for any one of these in isolation:

- multi-perspective reasoning;
- graph-based conflict representation;
- reasoning-trace decomposition;
- multiple logical justifications;
- fact-level conflict modeling;
- logic-guided conflict resolution;
- truth discovery from conflicting sources.

After KCR/TCR/MAGIC/FaithfulRAG, the defensible target is narrower:

> **Source identity and reliability remain attached to symbolic/ontology derivations; conflicts are localized as provenance paths; partial support is separated from incompatibility; and the localized evidence is reused for truth adjudication.**

```text
Source
  ↓
Claim
  ↓
Symbolic / Ontology Derivation
  ↓
Exact / Partial / Conflict
  ↓
Provenance-preserving Conflict Graph
  ↓
Source Reliability + Logical Support
  ↓
Truth Adjudication
```

---

# Repository

```text
src/rashomon_tableau/
├── clause_tableau.py
├── tableau.py
├── ontology.py
├── rashomon.py
└── truth_resolution.py

scripts/
├── evaluate_folio_fragment.py
├── evaluate_logicnli.py
├── evaluate_truth_discovery_books.py
├── evaluate_dafna_official_outputs.py
├── prepare_dafna_official_books.py
├── merge_truth_discovery_comparison.py
└── evaluate_magic_structured.py

results/
├── folio_fragment_metrics.json
├── logicnli_metrics.json
├── truth_discovery_books_metrics.json
├── dafna_official_comparison.json
└── magic_structured_metrics.json   # generated by CI / branch benchmark
```

---

# Reproduce

```bash
pip install -e .
python scripts/evaluate_folio_fragment.py
python scripts/evaluate_logicnli.py
python scripts/evaluate_truth_discovery_books.py
python scripts/evaluate_magic_structured.py
```

GitHub Actions additionally clones and executes the official DAFNA-EA Java algorithms.

---

# Evaluation Policy

Do not place unrelated tasks into one leaderboard.

1. **DAFNA Books** → direct truth-discovery comparison (Exact Truth / Author F1)
2. **MAGIC** → modern conflict detection/localization stress test
3. **CONFLICTS / DRAGged** → next end-to-end truth-resolution benchmark after claim extraction is frozen
4. **FaithfulRAG / KCR / TCR** → execute only when their task/input/model setup can be reproduced fairly; otherwise use as related-work positioning rather than copying incompatible paper numbers into our leaderboard

---

# Current Limitations

- FOLIO full grammar is not supported.
- LogicNLI evaluation uses structured logic input.
- DAFNA Books has source-level truth labels but no rich ontology/rule chains.
- MAGIC exposes a clear weakness on multi-hop graph-composed conflicts: current local pairwise reasoning drops to 27–41%.
- Current MAGIC diagnostic uses structured gold conflict triplets and is not a natural-language ID/LOC reproduction.
- A relation-composition / graph-path reasoner is required before claiming robust multi-hop conflict localization.
- The recent KCR result means generic “reasoning-trace-based conflict resolution” cannot be claimed as novel; source-provenance + symbolic derivation + source reliability must remain central.
- CONFLICTS / DRAGged requires a non-leaking claim extraction and normalization layer before fair end-to-end evaluation.

---

# Paper and research notes

- [`paper.md`](./paper.md) — manuscript draft
- [`MODERN_BASELINES.md`](./MODERN_BASELINES.md) — 2025–2026 comparison and novelty boundary
- [`report.md`](./report.md) — development / experiment history
