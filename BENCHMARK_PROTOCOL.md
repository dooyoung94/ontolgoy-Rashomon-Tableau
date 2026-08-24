# Benchmark Protocol — Rashomon-Tableau

이 문서는 논문의 실험 기준을 고정한다. 서로 다른 task의 숫자를 하나의 leaderboard에 섞지 않는다.

## 1. Research questions and datasets

| RQ | Question | Dataset | Primary metric | Direct peer comparison? |
|---|---|---|---|---|
| RQ1 | ontology-guided bidirectional reasoning이 q / ¬q와 multi-hop derivation을 복원하는가? | LogicNLI, FOLIO, MAGIC structured | Accuracy / Macro-F1 / status distribution | LogicNLI/FOLIO는 symbolic component comparison |
| RQ2 | conflict가 어느 source / claim / rule / hop에서 발생했는가? | DAFNA Books, MAGIC | exact-partial-conflict Macro-F1; path/localization metrics | DAFNA claim labels direct; MAGIC는 protocol 차이 명시 |
| RQ3 | localized evidence + source reliability가 truth recovery를 개선하는가? | DAFNA-EA Books | Exact Truth Accuracy, Author F1 | **Yes** — official DAFNA implementations |

## 2. DAFNA-EA Books — direct truth-discovery comparison

동일한 100-book `AuthorsNamesList` gold subset을 사용한다.

- 100 gold books
- 1,999 collapsed source-object claims
- 227 sources
- 동일 benchmark-side author normalization 적용

현재 측정값:

| Method | Exact Truth Accuracy | Author F1 | Comparison status |
|---|---:|---:|---|
| **Rashomon-Tableau Atomic Resolution** | **61.00%** | **82.88%** | measured, this repository |
| TruthFinder | 57.00% | 66.85% | measured, official DAFNA-EA Java |
| AccuSim | 57.00% | 66.18% | measured, official DAFNA-EA Java |
| 2-Estimates | 54.00% | 65.28% | measured, official DAFNA-EA Java |
| 3-Estimates | 53.00% | 65.45% | measured, official DAFNA-EA Java |
| Accu | 53.00% | 65.45% | measured, official DAFNA-EA Java |
| Reliability-weighted whole claim | 45.00% | 75.24% | measured, local ablation |
| Whole-claim majority | 44.00% | 73.57% | measured, local ablation |

`LTM`은 공식 구현이 stochastic하며 동일 protocol 재실행에서 값이 크게 달라졌다. 단일 실행값은 headline table에서 제외하고 향후 repeated-run mean ± std만 보고한다.

### Allowed claim

> On the DAFNA-EA Books AuthorsNamesList gold subset under the shared evaluation protocol, Rashomon-Tableau achieved 61% exact truth accuracy, compared with 57% for TruthFinder and AccuSim.

### Not allowed

- “Rashomon-Tableau is universally better than TruthFinder.”
- “61% is state of the art on modern knowledge-conflict reasoning.”

## 3. MAGIC — modern multi-hop conflict stress test

MAGIC (Findings EMNLP 2025)는 KG 기반 inter-context conflict benchmark이며 single-hop과 multi-hop conflict를 제공한다.

### 3.1 Two evaluators

1. `scripts/evaluate_magic_structured.py`
   - released `original_triplet` / `perturb_triplet` 직접 사용
   - legacy direct pair heuristic
   - 기존 failure analysis를 보존하는 ablation

2. `scripts/evaluate_magic_bidirectional.py`
   - `subgraph + perturb_triplet`을 evidence graph로 구성
   - ontology closure: symmetric / inverse / hierarchy / transitive / declared relation composition
   - forward + reverse candidate path retrieval
   - query q와 opposing evidence를 모두 검증
   - four states: `SUPPORTED / CONTRADICTED / BOTH / UNRESOLVED`
   - closed-world assumption 사용 안 함

### 3.2 Critical distinction

`graph path found`는 `conflict proved`가 아니다.

```text
Candidate retrieval:
subject -> ... -> object
or
object -> ... -> subject

        ↓ ontology validation

SUPPORTED / CONTRADICTED / BOTH / UNRESOLVED
```

관계가 연결되어 있다는 사실만으로 composition을 만들지 않는다. YAML에 선언된 rule만 허용한다.

### 3.3 Peer reference

MAGIC 논문의 published multi-hop scores는 natural-language context를 읽는 LLM의 ID/LOC이다. 우리 structured symbolic evaluator와 입력이 다르므로 **head-to-head ranking으로 표현하지 않는다**.

Published MAGIC multi-hop ID reference:

| Model | N=1 | N=2 | N=3 | N=4 |
|---|---:|---:|---:|---:|
| Mixtral 8x7B | 23.47 | 31.61 | 38.16 | 30.00 |
| Llama 3.1 70B | 59.52 | 78.67 | 70.00 | 73.91 |
| Claude 3.5 Haiku | 41.00 | 44.30 | 63.75 | 86.00 |
| GPT-4o-mini | 70.67 | 84.18 | 86.25 | 94.00 |
| o1 | 36.00 | 58.23 | 71.25 | 62.00 |

Published MAGIC multi-hop LOC reference:

| Model | N=1 | N=2 | N=3 | N=4 |
|---|---:|---:|---:|---:|
| Mixtral 8x7B | 12.59 | 7.10 | 6.58 | 0.00 |
| Llama 3.1 70B | 31.75 | 25.33 | 25.00 | 8.70 |
| Claude 3.5 Haiku | 33.67 | 35.44 | 33.75 | 32.00 |
| GPT-4o-mini | 54.67 | 47.47 | 33.75 | 24.00 |
| o1 | 30.67 | 30.38 | 27.50 | 12.00 |

Source: MAGIC, Findings of EMNLP 2025, Tables 9 and 10.

The repository computes weighted summaries only as a descriptive reference using released subset sizes `[300, 158, 80, 50]`. Such weighted numbers are derived calculations, not metrics printed by the MAGIC paper.

## 4. Ablation plan

MAGIC multi-hop은 다음 순서로 실제 측정한다.

| Version | Purpose | Result |
|---|---|---|
| Direct pair heuristic | 기존 baseline | measured |
| + inverse / symmetric | direction semantics | CI measurement |
| + transitive | declared transitive relations | CI measurement |
| + relation composition | ontology-licensed multi-hop derivation | CI measurement |
| + bidirectional q / ¬q verification | truth state validation | CI measurement |
| + provenance localization | rule/hop/source explanation | CI measurement |

예상값을 표에 미리 넣지 않는다. CI artifact에서 나온 실제 값만 `results/`에 고정한다.

## 5. FOLIO and LogicNLI

- FOLIO 96.43%는 **지원 문법 28/204 fragment**에 대한 결과이며 full-FOLIO 성능으로 표현하지 않는다.
- LogicNLI 98.40%는 official structured `test_logic`에서 symbolic dual-direction reasoning을 평가한 것이며 end-to-end NLP 성능으로 표현하지 않는다.

## 6. Reproducibility

```bash
pip install -e .
python scripts/evaluate_folio_fragment.py
python scripts/evaluate_logicnli.py
python scripts/evaluate_truth_discovery_books.py
python scripts/evaluate_magic_structured.py
python scripts/evaluate_magic_bidirectional.py
pytest -q
```

GitHub Actions는 추가로 official `qcri/DAFNA-EA` Java algorithms를 clone/build/run한다.

## 7. Evaluation rule for publication

모든 표의 각 행은 다음 중 하나를 명시한다.

- **Measured / same protocol**
- **Measured / different input protocol**
- **Published peer reference**
- **Derived calculation from published values**

이 구분이 없는 숫자는 논문 결과표에 넣지 않는다.
