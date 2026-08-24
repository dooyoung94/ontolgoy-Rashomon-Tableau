# Experiment Datasets and Reference Matrix

본 문서는 Rashomon-Tableau 논문의 외부 검증 데이터셋과 관련 연구를 역할별로 정리한다.

## 1. 권장 실험 데이터셋

| Dataset | Task | 핵심 특징 | Rashomon-Tableau에서의 사용 | RQ |
|---|---|---|---|---|
| **CONAN** | Multi-perspective relationship reasoning | 동일 이야기 내 character별 관점과 관계 Gold label | Primary dataset. Perspective ABox 구성, divergence/inter-contradiction 평가 | RQ1–RQ4 |
| **SNLI** | NLI | 대규모 entailment/neutral/contradiction pair | 기본 Pairwise NLI baseline | RQ3 |
| **MultiNLI** | Multi-genre NLI | 다양한 장르의 NLI | 도메인 변화에 대한 NLI baseline 일반화 | RQ3 |
| **ANLI** | Adversarial NLI | 모델이 어려워하는 adversarial NLI 사례 | 강한 contradiction baseline | RQ3 |
| **LogicNLI** | First-order logical reasoning | 자연어 기반 논리 추론 진단 | implicit contradiction, negation, consistency 검증 | RQ1, RQ3 |
| **FOLIO** | NL + First-Order Logic | 자연어 premise와 FOL annotation | LLM 명제화 정확도 및 deductive proof 평가 | RQ1, RQ3, RQ4 |
| **LogicBench** | Systematic logical reasoning | 다양한 논리 패턴 | ontology/tableau rule robustness | RQ3 |
| **FEVER** | Fact verification | Supported / Refuted / NEI + evidence | evidence-backed contradiction 및 explanation 평가 | RQ3, RQ4 |
| **EX-FEVER** | Multi-hop explainable verification | 다단계 evidence reasoning | multi-hop clash/proof path 평가 | RQ3, RQ4 |
| **AVeriTeC** | Real-world claim verification | 실제 fact-check claim + web evidence | 실제 환경 외부 타당성 검증 | RQ3, RQ4 |
| **FOL-Traces** | Verified FOL reasoning traces | 검증된 논리 추론 trace | Tableau derivation path correctness 비교 | RQ4 |

---

## 2. 가장 추천하는 논문 실험 구성

### 최소 구성

```text
CONAN + ANLI + LogicNLI + FOLIO + FEVER
```

역할:

```text
CONAN    → Multi-perspective reasoning
ANLI     → Strong contradiction baseline
LogicNLI → Logical consistency / implicit contradiction
FOLIO    → Natural language → FOL / proof
FEVER    → Evidence-backed contradiction
```

### 설명가능성 강화

```text
+ EX-FEVER
```

### 실제 환경 확장

```text
+ AVeriTeC
```

---

## 3. RQ별 데이터셋 매핑

### RQ1

> LLM은 다중 관점 자연어 서사를 논리 명제로 얼마나 정확하게 변환하는가?

추천:

```text
CONAN
FOLIO
```

평가:

- Triple Precision / Recall / F1
- Predicate Accuracy
- Argument Alignment
- Negation Accuracy
- Logical Form Exact Match

### RQ2

> 개별 관점 내부 모순과 관점 간 모순을 Tableau로 구분할 수 있는가?

추천:

```text
CONAN Human-annotated Perspective Benchmark
```

평가:

- Consistent
- Divergence
- Intra-Contradiction
- Inter-Contradiction

### RQ3

> Pairwise NLI보다 implicit contradiction을 잘 탐지하는가?

추천:

```text
CONAN
ANLI
LogicNLI
FOLIO
FEVER
```

평가:

- Accuracy
- Macro-F1
- Explicit Contradiction Recall
- Implicit Contradiction Recall
- Negation-sensitive Accuracy

### RQ4

> 논리 경로 제공이 설명가능성을 향상시키는가?

추천:

```text
CONAN
FOLIO
FEVER
EX-FEVER
FOL-Traces
```

평가:

- Proof Validity
- Evidence Faithfulness
- Path Completeness
- MUS Minimality
- Alternative Explanation Coverage

---

## 4. Baseline Matrix

| Model | CONAN | ANLI | LogicNLI | FOLIO | FEVER | EX-FEVER |
|---|---:|---:|---:|---:|---:|---:|
| Pairwise NLI | O | O | O | △ | O | △ |
| LLM Direct Judge | O | O | O | O | O | O |
| Ontology Rule Only | O | X | O | O | △ | △ |
| Vanilla Tableau | O | X | O | O | △ | △ |
| Perspective Tableau | O | X | △ | △ | △ | △ |
| **Rashomon-Tableau** | **O** | △ | **O** | **O** | **O** | **O** |

`△`는 변환 어댑터 또는 별도 prompt/schema가 필요한 경우다.

---

## 5. Reference List

1. Bowman, S. R., Angeli, G., Potts, C., & Manning, C. D. (2015). **A Large Annotated Corpus for Learning Natural Language Inference.** EMNLP 2015.
2. Williams, A., Nangia, N., & Bowman, S. R. (2018). **A Broad-Coverage Challenge Corpus for Sentence Understanding through Inference.** NAACL 2018.
3. Nie, Y. et al. (2020). **Adversarial NLI: A New Benchmark for Natural Language Understanding.** ACL 2020.
4. Tian, J. et al. (2021). **Diagnosing the First-Order Logical Reasoning Ability Through LogicNLI.** EMNLP 2021.
5. Han, S. et al. (2024). **FOLIO: Natural Language Reasoning with First-Order Logic.** EMNLP 2024.
6. Parmar, M. et al. (2024). **LogicBench: Towards Systematic Evaluation of Logical Reasoning Ability of Large Language Models.** ACL 2024.
7. Thorne, J. et al. (2018). **FEVER: a Large-scale Dataset for Fact Extraction and VERification.** NAACL 2018.
8. Ma, H. et al. (2024). **EX-FEVER: A Dataset for Multi-hop Explainable Fact Verification.** Findings of ACL 2024.
9. Schlichtkrull, M. et al. (2024). **The Automated Verification of Textual Claims (AVeriTeC) Shared Task.** FEVER 2024.
10. Kumar, S., & Talukdar, P. (2020). **NILE: Natural Language Inference with Faithful Natural Language Explanations.** ACL 2020.
11. Schuster, T. et al. (2019). **Towards Debiasing Fact Verification Models.** EMNLP-IJCNLP 2019.
12. Portelli, B. et al. (2020). **Distilling the Evidence to Augment Fact Verification Models.** FEVER 2020.
13. Saakyan, A. et al. (2021). **COVID-Fact: Fact Extraction and Verification of Real-World Claims on COVID-19 Pandemic.** ACL 2021.
14. Wang, S. et al. (2022). **Logic-Driven Context Extension and Data Augmentation for Logical Reasoning of Text.** Findings of ACL 2022.
15. Ryb, S. et al. (2022). **AnaLog: Testing Analytical and Deductive Logic Learnability in Language Models.** *SEM 2022.
16. Yuan, Z. et al. (2023). **Can Pretrained Language Models (Yet) Reason Deductively?** EACL 2023.
17. Zhao et al. (2024). **Large Language Models Fall Short: Understanding Complex Relationships in Detective Narratives.** Findings of ACL 2024.
18. Zhao et al. (2026). **SymbolicThought: Integrating Language Models and Symbolic Reasoning for Consistent and Interpretable Human Relationship Understanding.** ACL 2026 Demo.
19. **It Takes Two to Tango: The Rashomon Effect in Machine Translation.** NLPerspectives 2026.
20. Sun et al. (2024). **Think-on-Graph: Deep and Responsible Reasoning of Large Language Model on Knowledge Graph.** ICLR 2024.
21. **FOL-Traces: Verified First-Order Logic Reasoning Traces at Scale.** Findings of EACL 2026.

---

## 6. 실험 범위 권고

첫 논문에서는 데이터셋을 지나치게 많이 사용하는 것보다 역할이 분명한 5개를 선택하는 것이 좋다.

```text
Primary      : CONAN
NLI Baseline : ANLI
Logic        : LogicNLI
NL→Logic     : FOLIO
Evidence     : FEVER
```

후속 연구에서 다음을 추가한다.

```text
Explainability : EX-FEVER
Real-world     : AVeriTeC
Proof Trace    : FOL-Traces
```
