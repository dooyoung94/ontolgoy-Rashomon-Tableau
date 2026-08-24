# Rashomon-Tableau

## Ontology-Guided Bidirectional Tableau for Provenance-Aware Multi-Hop Truth Adjudication

> 서로 상충하는 source를 먼저 버리거나 합치지 않고, **forward/reverse multi-hop candidate를 찾은 뒤 ontology가 허용한 관계만 q / ¬q 양방향으로 검증하고, 그 provenance를 source reliability와 결합해 truth를 판정할 수 있는가?**

## Core architecture

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

중요한 원칙:

> **Graph path는 후보(hypothesis)일 뿐 truth/causality가 아니다.**  
> inverse, symmetric, hierarchy, transitive, relation-composition은 명시적 ontology rule이 있을 때만 적용한다.

이 구조는 knowledge conflict뿐 아니라 RCA에서도 동일하게 사용할 수 있다. Reverse path는 upstream cause candidate를 찾고, forward path는 impact candidate를 찾으며, Tableau는 각 hypothesis의 논리적 support / contradiction을 검증한다.

---

# Research questions

1. **RQ1 — Ontology-Guided Bidirectional Reasoning**  
   Direct matching이 놓치는 multi-hop support/conflict를 ontology 기반 q / ¬q 검증으로 복원할 수 있는가?

2. **RQ2 — Provenance-Aware Conflict Localization**  
   어느 source / claim / relation / hop에서 conflict가 발생하는지 추적할 수 있는가?

3. **RQ3 — Truth Adjudication**  
   localized conflict evidence와 source reliability를 결합하면 실제 gold truth recovery가 개선되는가?

---

# Current measured evidence

## DAFNA-EA Books — direct truth-discovery comparison

동일 100-book `AuthorsNamesList` gold subset, 1,999 source-object claims, 227 sources.

| Method | Exact Truth Accuracy | Author F1 | Status |
|---|---:|---:|---|
| **Rashomon-Tableau Atomic Resolution** | **61.00%** | **82.88%** | measured |
| TruthFinder | 57.00% | 66.85% | official DAFNA-EA measured |
| AccuSim | 57.00% | 66.18% | official DAFNA-EA measured |
| 2-Estimates | 54.00% | 65.28% | official DAFNA-EA measured |
| 3-Estimates | 53.00% | 65.45% | official DAFNA-EA measured |
| Accu | 53.00% | 65.45% | official DAFNA-EA measured |

`LTM`은 stochastic official implementation이라 single-run headline에서 제외하고 repeated-run mean ± std 대상으로 둔다.

## LogicNLI — dual-direction reasoning

| Method | Accuracy | Macro-F1 | Paradox F1 |
|---|---:|---:|---:|
| Single-path Forward | 74.00% | 65.78% | 0.00% |
| **Dual-Direction Proof Check** | **98.40%** | **98.40%** | **97.92%** |

Structured symbolic evaluation이며 end-to-end NLP score가 아니다.

## FOLIO — supported fragment only

| Method | Accuracy | Macro-F1 |
|---|---:|---:|
| Forward Horn | 75.00% | 74.18% |
| Semantic Clause Tableau | **96.43%** | **96.33%** |

현재 parser 지원 범위는 validation **28/204**이다. Full-FOLIO 성능으로 표현하지 않는다.

## MAGIC — modern multi-hop stress test

기존 direct structured diagnostic은 single-hop 98.56–100%였지만 multi-hop은 27–41%로 하락했다. 따라서 새 evaluator는 다음을 분리한다.

```text
1. Direct pair heuristic
2. Forward / Reverse candidate path coverage
3. Ontology closure
4. q / NOT q Tableau verification
5. Conflict provenance
```

실행:

```bash
python scripts/evaluate_magic_structured.py
python scripts/evaluate_magic_bidirectional.py
```

새 결과는 CI가 `results/magic_bidirectional_tableau_metrics.json`으로 생성한다.

**주의:** MAGIC published peer는 natural-language context를 읽는 LLM의 ID/LOC이고, 현재 우리 evaluator는 released structured triplet을 사용한다. 숫자는 참고 peer track으로만 병기하며 동일 protocol head-to-head로 주장하지 않는다.

---

# Repository structure

```text
README.md
RESEARCH_PAPER.md         # 논문 본문
BENCHMARK_PROTOCOL.md     # 데이터셋 / peer / 공정 비교 규칙

config/
├── ontology_rules.yaml
└── magic_ontology_rules.yaml

src/rashomon_tableau/
├── ontology.py           # inverse/symmetric/hierarchy/transitive/composition closure
├── graph_paths.py        # forward/reverse bounded candidate paths
├── tableau.py            # clash + q/¬q four-state verification
├── truth_resolution.py   # source reliability + atomic truth resolution
└── ...

scripts/
├── evaluate_truth_discovery_books.py
├── evaluate_dafna_official_outputs.py
├── evaluate_logicnli.py
├── evaluate_folio_fragment.py
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

GitHub Actions는 동일 benchmark들과 official `qcri/DAFNA-EA` Java algorithms를 실행한다.

---

# Documentation

- **[`RESEARCH_PAPER.md`](./RESEARCH_PAPER.md)** — 일관된 논문 본문
- **[`BENCHMARK_PROTOCOL.md`](./BENCHMARK_PROTOCOL.md)** — 데이터셋, metric, peer group, 직접/간접 비교 기준

결과 JSON/Markdown은 `results/` 아래의 측정 산출물만 사용한다.
