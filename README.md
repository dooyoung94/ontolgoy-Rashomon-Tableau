# Rashomon-Tableau

## Ontology-Guided Bidirectional Tableau for Provenance-Aware Multi-Hop Truth Adjudication

> 서로 상충하는 source를 먼저 버리거나 합치지 않고, **forward/reverse multi-hop candidate를 찾은 뒤 ontology가 허용한 관계만 q / opposing evidence 양방향으로 검증하고, 그 provenance를 source reliability와 결합해 truth를 판정할 수 있는가?**

## Architecture

```text
Multiple Sources
      ↓
Atomic Claims
      ↓
Ontology / Knowledge Graph
      ↓
Forward + Reverse Candidate Paths
      ↓
Ontology-Guided Bidirectional Tableau
      ↓
SUPPORTED / CONTRADICTED / BOTH / UNRESOLVED
      ↓
Source → Claim → Rule → Derived Claim → Conflict Provenance
      ↓
Source Reliability + Proposition Support
      ↓
Truth Adjudication + Confidence
```

**원칙:** `Graph path != Truth / Conflict / Causality`.  
Inverse, symmetric, hierarchy, transitive, relation-composition은 명시적 ontology rule이 있을 때만 적용한다.

이 구조는 RCA에서도 동일하게 해석할 수 있다. Reverse path는 upstream cause candidate, forward path는 impact candidate이며 Tableau는 각 hypothesis의 support / contradiction을 검증한다.

---

# Research Questions

1. **RQ1 — Ontology-Guided Bidirectional Reasoning**: direct matching이 놓치는 multi-hop support/conflict를 복원·검증할 수 있는가?
2. **RQ2 — Provenance-Aware Conflict Localization**: 어느 source / claim / relation / hop에서 conflict가 발생하는가?
3. **RQ3 — Truth Adjudication**: localized conflict evidence + source reliability가 gold truth recovery를 개선하는가?

---

# Validated Results

## 1. DAFNA-EA Books — same-protocol truth discovery

100 gold books / 1,999 source-object claims / 227 sources.

| Method | Exact Truth Accuracy | Author F1 | Status |
|---|---:|---:|---|
| **Rashomon-Tableau Atomic Resolution** | **61.00%** | **82.88%** | measured |
| TruthFinder | 57.00% | 66.85% | official DAFNA-EA measured |
| AccuSim | 57.00% | 66.18% | official DAFNA-EA measured |
| 2-Estimates | 54.00% | 65.28% | official DAFNA-EA measured |
| 3-Estimates | 53.00% | 65.45% | official DAFNA-EA measured |
| Accu | 53.00% | 65.45% | official DAFNA-EA measured |

`LTM`은 stochastic official implementation이라 repeated-run mean ± std 전까지 headline에서 제외한다.

## 2. LogicNLI — dual-direction proof

| Method | Accuracy | Macro-F1 | Paradox F1 |
|---|---:|---:|---:|
| Single-path Forward | 74.00% | 65.78% | 0.00% |
| **Dual-Direction Proof Check** | **98.40%** | **98.40%** | **97.92%** |

Structured symbolic evaluation이다.

## 3. FOLIO — supported fragment only

현재 grammar coverage: 28/204 validation examples.

| Method | Accuracy | Macro-F1 |
|---|---:|---:|
| Forward Horn | 75.00% | 74.18% |
| Semantic Clause Tableau | **96.43%** | **96.33%** |

Full-FOLIO 성능으로 표현하지 않는다.

## 4. MAGIC — actual multi-hop validation

Validated workflow: **32720349460**  
Artifact: **9517514860**

| Track | Single-hop | Multi-hop | 의미 |
|---|---:|---:|---|
| Legacy direct heuristic | 97.56% | 33.16% | permissive relation-replacement cue |
| **Bidirectional candidate-path coverage** | **61.38%** | **68.03%** | forward/reverse path 존재; **정확도 아님** |
| **Ontology-verified contradiction** | **42.68%** | **5.44%** | 명시적 ontology semantics로 실제 contradiction 증명 |

Multi-hop detail:

| MAGIC subset | N | Direct heuristic | Candidate path | Verified contradiction |
|---|---:|---:|---:|---:|
| 1 conflict | 300 | 27.00% | 57.33% | 1.33% |
| 2 conflicts | 158 | 41.14% | 73.42% | 10.76% |
| 3 conflicts | 80 | 37.50% | 82.50% | 7.50% |
| 4 conflicts | 50 | 38.00% | 92.00% | 10.00% |
| **Weighted** | **588** | **33.16%** | **68.03%** | **5.44%** |

### Interpretation

- 양방향 graph 탐색으로 **후보 경로 누락은 크게 완화**됐다.
- 그러나 path가 있다고 conflict가 되는 것은 아니다.
- 보수적 ontology로 실제 contradiction까지 닫히는 비율은 아직 낮다.
- 따라서 다음 병목은 graph traversal보다 **relation semantics / ontology coverage**다.

MAGIC published peers는 natural-language context를 읽고 ID/LOC를 평가한다. 현재 우리 evaluator는 released structured triplet을 사용하므로 직접 head-to-head ranking하지 않는다.

Published N별 값을 공식 subset size로 가중한 참고값(논문 직접 표기 metric이 아니라 파생 계산):

| Published peer | Weighted ID* | Weighted LOC* |
|---|---:|---:|
| Mixtral 8x7B | 28.21% | 9.23% |
| Claude 3.5 Haiku | 48.81% | 34.01% |
| o1 | 48.98% | 28.57% |
| Llama 3.1 70B | 67.32% | 27.15% |
| GPT-4o-mini | 78.40% | 47.28% |
| **5-model mean** | **54.34%** | **29.25%** |

`*` 참고용 published-value aggregation이며 **68.03% candidate coverage / 5.44% formal contradiction과 직접 비교하지 않는다**.

Measured output: [`results/magic_bidirectional_tableau_metrics.json`](./results/magic_bidirectional_tableau_metrics.json)

---

# Repository

```text
README.md
RESEARCH_PAPER.md
BENCHMARK_PROTOCOL.md

config/
├── ontology_rules.yaml
└── magic_ontology_rules.yaml

src/rashomon_tableau/
├── ontology.py
├── graph_paths.py
├── tableau.py
├── truth_resolution.py
└── ...

scripts/
├── evaluate_folio_fragment.py
├── evaluate_logicnli.py
├── evaluate_truth_discovery_books.py
├── evaluate_magic_structured.py
└── evaluate_magic_bidirectional.py

results/
└── measured benchmark outputs
```

---

# Reproduce

```bash
pip install -e .
python scripts/evaluate_folio_fragment.py
python scripts/evaluate_logicnli.py
python scripts/evaluate_truth_discovery_books.py
python scripts/evaluate_magic_structured.py
python scripts/evaluate_magic_bidirectional.py
pytest -q
```

GitHub Actions는 official `qcri/DAFNA-EA` Java algorithms까지 clone/build/run한다.

---

# Documentation

- **[`RESEARCH_PAPER.md`](./RESEARCH_PAPER.md)** — 논문 본문
- **[`BENCHMARK_PROTOCOL.md`](./BENCHMARK_PROTOCOL.md)** — dataset / metric / peer / fair-comparison 규칙

상위 연구 문서는 위 두 파일과 README만 유지하며, 측정 결과는 `results/` 아래에 둔다.
