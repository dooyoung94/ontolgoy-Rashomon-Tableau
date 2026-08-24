# Conan Rashomon-Tableau PoC

CONAN detective-narrative benchmark의 **관점별 관계 명제**를 사용해 다음 연구 흐름을 실제 실행하는 PoC입니다.

`CONAN perspective -> proposition -> ontology closure -> relational Tableau SAT/UNSAT -> Rashomon MUS explanations -> Accuracy/F1`

## 연구 질문 대응

- **RQ1**: LLM이 관점 서사를 `(subject, relation, object)` 명제로 얼마나 정확히 변환하는가? → CONAN perspective gold relation과 micro P/R/F1
- **RQ2**: 내부/관점 간 모순을 Tableau SAT/UNSAT로 구분 가능한가? → `satisfiable_a`, `satisfiable_b`, `satisfiable_union`
- **RQ3**: explicit뿐 아니라 inverse/hierarchy로 생성되는 implicit contradiction을 탐지 가능한가? → subtype별 Accuracy, implicit recall
- **RQ4**: 모순 경로를 설명 가능한가? → clash rule + Minimal Unsatisfiable Subsets(MUS) + Rashomon explanation set

## 중요: 정확도 해석

CONAN의 공식 라벨은 **인물 관계 라벨**이며 contradiction gold label이 아닙니다. 따라서 두 평가를 분리합니다.

1. `controlled` (기본): 실제 CONAN gold proposition에서 explicit/implicit/consistent/divergence 케이스를 재현 가능하게 생성합니다. **reasoner 구현 검증용**입니다.
2. `annotated`: 실제 서로 다른 관점의 proposition pair를 사람이 `consistent/divergence/contradiction`으로 라벨링한 뒤 평가합니다. **논문에서 자연 모순 탐지 정확도를 주장할 때 사용**합니다.

## 1. 설치

```bash
git clone https://github.com/dooyoung94/ontolgoy-Rashomon-Tableau.git
cd ontolgoy-Rashomon-Tableau
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e .
```

## 2. CONAN 다운로드

```bash
python scripts/download_conan.py
```

공식 데이터 구조는 `data/<language>/data_final/<story>/txt/<character>.txt`와 `data/<language>/label/<story>/<character>.json`입니다. 이 저장소에는 CONAN 원본 데이터를 재배포하지 않고 다운로드 스크립트만 포함합니다.

## 3. API 없이 GOLD/Tableau 실험

```bash
python run_experiment.py --mode gold --benchmark controlled --max-stories 3
```

생성물:

- `results/relation_inventory.json`: 실제 CONAN 관계 predicate 빈도
- `results/predictions.csv`: case별 gold/prediction
- `results/predictions.json`: clash, rule, Rashomon explanation 상세
- `results/metrics.json`: Accuracy, macro-F1, class별 P/R/F1, subtype별 Accuracy, implicit contradiction recall

## 4. RQ1: 원문 -> LLM 명제화 정확도

```bash
pip install -r requirements-llm.txt
# OPENAI_API_KEY 환경변수 설정
python run_experiment.py --mode llm --benchmark controlled --max-stories 1 --llm-model gpt-5-mini
```

`results/rq1_llm_extraction.json`에 CONAN gold triple 대비 micro Precision/Recall/F1이 저장됩니다.

## 5. 실제 관점 간 모순 gold set 만들기

```bash
python scripts/build_annotation_set.py --max-stories 3 --max-pairs-per-story 100
```

생성된 `data/annotations/contradiction_candidates.csv`의 `label`을 다음 중 하나로 작성합니다.

- `consistent`: 두 명제가 동일/양립
- `divergence`: 서로 다른 정보를 말하지만 동시에 참일 수 있음
- `contradiction`: ontology를 포함했을 때 동시에 참일 수 없음

그 다음:

```bash
python run_experiment.py --benchmark annotated --annotation-file data/annotations/contradiction_candidates.csv
```

## Tableau 판정식

각 관점 ABox를 `A_i`, 공통 ontology를 `T`라고 하면:

- 내부 모순: `SAT(T U A_i) = 0`
- 관점 간 모순: `SAT(T U A_i)=1`, `SAT(T U A_j)=1`, `SAT(T U A_i U A_j)=0`
- divergence: `A_i != A_j`이지만 `SAT(T U A_i U A_j)=1`

현재 reasoner는 CONAN의 binary relation 실험을 위한 **lightweight relational Tableau**입니다. ontology forward closure 후 다음 clash를 검사합니다.

- literal vs negated literal
- incompatible relation pair
- exclusive/functional relation violation
- hierarchy/inverse/symmetry로 유도된 implicit clash

> 이 구현은 전체 OWL-DL reasoner가 아닙니다. 논문 확장 단계에서 Pellet/HermiT/OWLReady2로 교체 가능한 구조입니다.

## Rashomon 구현

UNSAT이 발생하면 bounded MUS enumeration으로 여러 최소 모순 근거를 구합니다.

`R_epsilon = { explanation | score(explanation) >= best_score - epsilon }`

즉 하나의 원인 경로만 선택하지 않고, 거의 동등하게 짧고 타당한 **복수의 모순 설명 경로**를 보존합니다.

## Ontology 수정

`config/ontology_rules.yaml`에서 `symmetric`, `inverse`, `hierarchy`, `incompatible`, `exclusive`를 편집합니다.

먼저 `results/relation_inventory.json`으로 실제 CONAN predicate를 확인한 뒤 규칙을 늘리는 방식을 권장합니다.

## 테스트

```bash
pip install pytest
pytest -q
```

## 논문용 권장 비교

- LLM direct contradiction judge
- Pairwise NLI (DeBERTa/RoBERTa)
- Ontology rule only
- Vanilla merged-ABox Tableau
- **Perspective-separated Rashomon-Tableau (proposed)**

NLI 의존성 템플릿은 `requirements-nli.txt`, baseline wrapper는 `src/rashomon_tableau/nli_baseline.py`에 있습니다.

## References

- Zhao et al., *Large Language Models Fall Short: Understanding Complex Relationships in Detective Narratives*, Findings of ACL 2024.
- Zhao et al., *SymbolicThought: Integrating Language Models and Symbolic Reasoning for Consistent and Interpretable Human Relationship Understanding*, ACL 2026 Demo.
- Official Conan: https://github.com/BLPXSPG/Conan
