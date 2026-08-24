# Rashomon-Tableau: Perspective-Indexed Satisfiability Reasoning for Contradiction Localization and Multi-Justification Preservation

## 라쇼몽-태블로: 모순 발생 위치 식별과 다중 정당화 보존을 위한 관점 인덱스 기반 만족가능성 추론

**Author:** [Author Name]  
**Affiliation:** [Affiliation]  
**Corresponding Author:** [Email]

---

## Abstract

Logical reasoners traditionally determine whether a knowledge base is satisfiable or whether a proposition is entailed. In multi-source settings, however, a single SAT/UNSAT decision is often insufficient. A contradiction may already exist inside one source, or may emerge only after two individually consistent sources are combined. Furthermore, an inconsistency can admit multiple independent minimal explanations, and presenting only one proof may conceal alternative causes that are equally valid. We propose **Rashomon-Tableau**, a perspective-indexed reasoning framework that reuses satisfiability reasoning rather than introducing a new logical calculus. The framework has three separable components: (1) semantic satisfiability reasoning for logical inference, (2) perspective-indexed SAT tests for localizing contradiction scope, and (3) preservation of multiple minimal justifications using a Rashomon-inspired proof-set selection principle.

We evaluate each component with a distinct experiment. On the strictly supported Horn/explicit-negation fragment of the official FOLIO v0.0 validation set, semantic clause-tableau reasoning obtains 96.43% accuracy and 96.33% Macro-F1, compared with 75.00% accuracy and 74.18% Macro-F1 for a forward-Horn baseline. On the official structured LogicNLI `test_logic` split containing 2,000 statements, a dual-proof decision procedure that checks both a proposition and its negation achieves 98.40% accuracy and 98.40% Macro-F1, whereas a single-path forward reasoner obtains 74.00% and 65.78%; the F1 score for the paradox/self-contradiction class increases from 0.00% to 97.92%. In a controlled four-class multi-context benchmark, perspective indexing improves contradiction-scope accuracy from 75.00% to 100.00% by distinguishing intra-perspective from inter-perspective inconsistency. Finally, on cases containing two independent minimal contradiction explanations, multi-justification preservation raises explanation coverage from 50.00% to 100.00%.

The proposed framework is closely related to Standpoint Logic, Multi-Context Systems, and axiom pinpointing. Consequently, we do not claim the first perspective-aware logic, the first tableau for multi-perspective reasoning, or the first method for enumerating multiple justifications. The narrower contribution is an operational protocol that combines provenance-preserving SAT calls with contradiction-scope semantics and a proof-space Rashomon selection layer. CONAN detective narratives are used as a multi-perspective case study rather than as the definition of the task. The framework is intended for broader settings where provenance matters, including conflicting documents, multi-agent hypotheses, temporal snapshots, and heterogeneous operational evidence.

**Keywords:** Tableau Reasoning; Multi-Perspective Reasoning; Contradiction Localization; Axiom Pinpointing; Minimal Unsatisfiable Subset; Rashomon Set; LogicNLI; FOLIO; Explainable Reasoning

---

## 초록

전통적인 논리 reasoner는 지식베이스의 만족가능성 또는 특정 명제의 entailment를 판정한다. 그러나 서로 다른 화자, 문서, 에이전트, 센서 또는 시점에서 생성된 정보를 함께 다루는 환경에서는 하나의 SAT/UNSAT 판정만으로 충분하지 않다. 모순은 하나의 출처 내부에 이미 존재할 수도 있고, 각각은 일관적인 두 출처가 결합될 때만 발생할 수도 있다. 또한 동일한 inconsistency가 여러 개의 독립적인 최소 설명으로 정당화될 수 있으므로 하나의 proof만 제시하면 동등하게 타당한 대안 원인을 숨길 수 있다. 본 연구는 새로운 논리 calculus를 제안하기보다 기존 satisfiability reasoning을 관점 단위로 조직하는 **Rashomon-Tableau** 프레임워크를 제안한다. 제안 방법은 (1) 논리 추론을 위한 semantic satisfiability reasoning, (2) 모순의 발생 범위를 식별하기 위한 perspective-indexed SAT 검사, (3) 여러 최소 정당화를 하나로 축약하지 않고 보존하기 위한 Rashomon-inspired proof-set selection의 세 구성요소로 이루어진다.

각 구성요소는 서로 다른 실험으로 평가하였다. FOLIO v0.0 validation 중 현재 구현이 엄격하게 지원하는 Horn/explicit-negation fragment에서 semantic clause-tableau는 Accuracy 96.43%, Macro-F1 96.33%를 기록하여 forward-Horn baseline의 75.00%, 74.18%보다 높았다. LogicNLI 공식 structured `test_logic` 2,000개 statement에서는 명제와 그 부정의 양쪽 증명 가능성을 모두 검사하는 dual-proof 방식이 Accuracy 98.40%, Macro-F1 98.40%를 기록한 반면 single-path forward 방식은 각각 74.00%, 65.78%를 기록하였다. 특히 paradox/self-contradiction 클래스의 F1은 0.00%에서 97.92%로 향상되었다. 네 개 클래스의 controlled multi-context benchmark에서는 perspective indexing을 통해 contradiction-scope Accuracy가 75.00%에서 100.00%로 향상되었다. 마지막으로 두 개의 독립적인 최소 모순 설명이 존재하는 controlled benchmark에서 하나의 proof만 반환할 경우 explanation coverage는 50.00%였으나 복수 정당화를 보존할 경우 100.00%를 기록하였다.

본 연구는 Standpoint Logic, Multi-Context Systems, Axiom Pinpointing과 밀접한 관련이 있다. 따라서 최초의 다중 관점 논리, 최초의 perspective-aware tableau, 또는 최초의 multiple-justification enumeration을 주장하지 않는다. 본 연구의 제한된 기여는 기존 satisfiability reasoner를 provenance-aware하게 호출하여 contradiction scope를 정의하고, 그 결과의 여러 justification을 proof-space Rashomon set으로 조직하는 실행 가능한 reasoning protocol에 있다. CONAN 탐정 서사는 방법론 자체가 아니라 multi-perspective case study로 사용된다.

**주요어:** Tableau Algorithm, Multi-Perspective Reasoning, Contradiction Scope, Axiom Pinpointing, Minimal Unsatisfiable Subset, Rashomon Set, LogicNLI, FOLIO

---

# 1. 서론

논리적 추론의 가장 기본적인 질문 중 하나는 “주어진 명제들이 동시에 참일 수 있는가?”이다. Tableau 계열 알고리즘은 논리식을 규칙에 따라 확장하고 가능한 해석의 branch를 구성한 뒤, branch 안에서 어떤 명제 $\phi$와 그 부정 $\neg\phi$가 동시에 나타나는 clash를 탐지한다. 모든 branch가 닫히면 지식베이스는 unsatisfiable하며, 하나 이상의 open branch가 남으면 satisfiable하다. 이러한 방식은 Description Logic과 ontology reasoning의 satisfiability, consistency, subsumption, entailment 판정에 오랫동안 활용되어 왔다 [1].

그러나 실세계의 지식은 흔히 하나의 균질한 출처에서 생성되지 않는다. 증인마다 사건을 다르게 기억할 수 있고, 뉴스 매체마다 동일 사건의 일부 사실만 관찰할 수 있으며, 두 센서는 서로 다른 상태를 보고할 수 있다. 멀티에이전트 시스템에서는 각 agent가 독립적인 가설을 형성할 수 있고, 운영 시스템에서는 서로 다른 로그, 메트릭, 데이터 스냅샷이 동일 장애에 대해 상이한 증거를 제공한다. 이때 모든 명제를 하나의 ABox로 즉시 병합하면 전체 일관성은 확인할 수 있지만 “어디에서 모순이 시작되었는가”라는 provenance 정보가 사라질 수 있다.

예를 들어 첫 번째 관점 $P_1$ 안에 이미 $p(a)$와 $\neg p(a)$가 함께 존재하는 경우와, $P_1$은 $p(a)$를 주장하고 $P_2$가 $\neg p(a)$를 주장하는 경우를 생각할 수 있다. 두 경우 모두 병합된 지식베이스는 UNSAT이다. 그러나 전자는 하나의 source 내부 consistency 문제이고, 후자는 두 source 사이의 충돌이다. 두 종류의 오류는 동일한 대응으로 처리하기 어렵다. 전자는 해당 source의 데이터 품질이나 추론 규칙을 조사해야 하고, 후자는 source 간 신뢰도, 시점, 범위 또는 관점 차이를 조사해야 한다.

두 번째 문제는 explanation multiplicity이다. 하나의 모순 결론은 한 가지 이유만으로 발생한다고 보장할 수 없다. 서로 독립적인 두 규칙 체인이 동일 clash로 이어질 수 있고, ontology entailment에는 여러 개의 최소 justification이 존재할 수 있다. 이 문제는 Axiom Pinpointing 및 ontology debugging 문헌에서 이미 잘 알려져 있다 [2,3]. 따라서 본 연구는 “여러 proof를 찾을 수 있다”는 사실 자체를 신규성으로 주장하지 않는다. 대신 여러 proof를 하나의 대표 설명으로 조기 축약하지 않고, 어떤 관점의 어떤 명제가 각 proof에 기여했는지 provenance를 유지한 상태로 여러 설명을 보존하는 데 초점을 둔다.

이 두 문제는 사실 하나의 공통된 정보 손실에서 출발한다. **병합은 source boundary를 잃게 만들고, 단일 proof 선택은 explanation boundary를 잃게 만든다.** 본 연구는 이 두 종류의 손실을 피하면서 기존 satisfiability reasoning을 재사용하는 방법을 제안한다.

본 논문의 연구 질문은 다음과 같다.

- **RQ1 — Logical inference:** semantic satisfiability reasoning은 단순 lookup 또는 forward-only reasoning보다 논리적으로 더 완전한 판정을 제공하는가?
- **RQ2 — Dual-proof contradiction:** $q$의 proof 하나를 찾은 뒤 종료하는 방식보다 $q$와 $\neg q$를 모두 검사하는 방식이 paradox/self-contradiction을 더 잘 식별하는가?
- **RQ3 — Contradiction scope:** 관점별 SAT와 union SAT를 분리하면 intra-perspective와 inter-perspective contradiction을 구분할 수 있는가?
- **RQ4 — Explanation preservation:** 하나의 proof만 반환하는 방식과 비교해 복수의 최소 justification을 보존하면 설명 coverage가 향상되는가?

본 연구의 기여는 새로운 logical connective나 tableau expansion rule이 아니다. 대신 기존 SAT oracle을 provenance-aware하게 사용하기 위한 **Perspective-Indexed Satisfiability Protocol**, local/merged SAT 상태로 모순의 범위를 구분하는 **Contradiction Scope Localization**, 양방향 proof 검사를 통한 paradox 보존, 그리고 여러 최소 explanation을 near-equivalent proof set으로 제시하는 **Rashomon-inspired selection layer**를 하나의 프레임워크로 정리한다.

---

# 2. 관련 연구

## 2.1 Tableau와 Hypertableau

Tableau reasoning은 satisfiability 문제를 branch expansion과 clash detection으로 환원한다. Description Logic reasoner에서는 표현력이 증가함에 따라 blocking, role restriction, dependency management 등의 기법이 발전했으며, HermiT의 Hypertableau와 같은 방식은 hyperresolution과 tableau의 장점을 결합하여 불필요한 nondeterminism을 줄이는 데 초점을 두었다 [1]. 이러한 연구에서 중심적인 평가지표는 새로운 논리 표현을 sound하고 complete하게 처리할 수 있는지, termination과 complexity가 어떠한지, 대규모 ontology에서 얼마나 효율적으로 동작하는지이다.

본 연구는 이러한 calculus를 대체하지 않는다. Semantic Tableau는 제안 방법의 reasoning oracle일 뿐이다. 핵심 차이는 **어떤 명제 집합을 한 번에 reasoner에 투입할 것인가**에 있다.

## 2.2 Axiom Pinpointing과 Multiple Justifications

Axiom Pinpointing은 특정 entailment를 야기하는 ontology axiom의 최소 집합을 찾는 문제이다. Baader와 Peñaloza는 일반 tableau를 axiom pinpointing이 가능하도록 확장하는 방법을 제시했고 [2], EL 계열에서도 하나의 consequence를 만드는 모든 minimal axiom set을 찾는 연구가 진행되었다 [3]. 이후 OWL ontology debugging 연구에서도 한 entailment가 여러 justification을 가질 수 있다는 점과 이들을 사용자에게 설명하는 문제가 중요한 inference service로 다뤄졌다 [4].

이 연구 계보는 본 논문의 multi-proof 부분과 가장 직접적으로 겹친다. 따라서 **multiple justification 자체는 본 연구의 신규성이 아니다.** 본 연구가 추가하는 요소는 justification을 perspective provenance와 함께 유지하고, 설명의 길이와 관점 다양성을 기준으로 하나의 justification만 선택하지 않는 proof-set presentation이다. 이 아이디어는 논리적 필요조건이라기보다 explanation policy에 가깝다.

## 2.3 Multi-Context Systems

Multi-Context Systems(MCS)는 서로 다른 logic을 사용하는 분산 knowledge base를 context 단위로 유지하고 bridge rule을 통해 정보를 교환하는 일반적 프레임워크이다 [5]. Eiter 등은 context 간 정보 교환으로 발생하는 inconsistency를 어떤 bridge rule 조합이 유발했는지 설명하는 방법을 제안하였다 [6]. 이는 “각 context는 독립적으로 의미가 있지만 상호 연결에서 conflict가 발생할 수 있다”는 점에서 본 연구의 inter-perspective contradiction과 매우 가깝다.

MCS는 본 연구보다 훨씬 일반적이다. heterogeneous logic, non-monotonic bridge rule, equilibrium semantics와 repair까지 다룬다. 반면 본 연구는 동일하거나 호환 가능한 logical vocabulary로 정규화된 perspective-specific proposition set을 대상으로 한다. 이 제한 덕분에 별도의 MCS semantics 없이 기존 SAT reasoner를 그대로 사용할 수 있지만, 표현력 측면에서는 MCS보다 좁다.

## 2.4 Standpoint Logic과 다중 관점 Tableau

본 연구와 가장 가까운 선행축 중 하나는 Standpoint Logic이다. Standpoint Logic은 서로 다른 agent 또는 ontology author가 서로 다른, 심지어 충돌하는 semantic commitment를 가질 수 있음을 명시적으로 표현하기 위해 standpoint modality를 도입한다 [7]. Standpoint EL은 Description Logic EL을 여러 관점으로 확장하면서도 tractable reasoning을 유지하는 것을 목표로 하고 [8], Standpoint EL+은 axiom negation과 role-chain 등을 추가한 deduction calculus를 제안한다 [9]. 또한 Standpoint Linear Temporal Logic은 시간적 추론과 다중 관점을 결합하고 이를 위한 terminating tableau calculus를 제시하였다 [10]. 최근에는 SHIQ과 standpoint modality의 결합도 연구되었다 [11].

따라서 본 연구는 “최초의 perspective-aware logic”이나 “최초의 multi-perspective tableau”를 주장할 수 없다. Standpoint Logic이 **관점을 논리의 syntax와 semantics 안에 넣는 접근**이라면, 본 연구는 관점이 이미 metadata로 주어진 환경에서 **기존 reasoner를 반복 호출하는 protocol**이다. 즉 표현력과 이론적 완결성에서는 Standpoint Logic이 더 강하고, 기존 시스템에 대한 적용 단순성 측면에서 본 연구가 더 가벼운 접근이라고 볼 수 있다.

## 2.5 Rashomon Set

Rashomon effect는 동일 데이터에 대해 거의 비슷하게 우수한 성능을 내는 여러 모델이 존재할 수 있다는 문제를 지칭한다. Fisher, Rudin, Dominici는 하나의 잘 맞는 모델만 해석하기보다 전체 well-performing model class를 함께 분석해야 한다고 주장하며 Model Class Reliance를 제안하였다 [12]. 이때 Rashomon set은 일반적으로 다음과 같이 정의할 수 있다.

\[
\mathcal{R}_{\epsilon}=\{f \in \mathcal{F}: L(f) \leq L(f^*)+\epsilon\}.
\]

본 연구는 이 개념을 그대로 theorem proving semantics로 사용하지 않는다. 대신 **하나의 contradiction에 여러 최소 justification이 존재할 때, 설명 품질이 최고 설명과 충분히 가까운 여러 proof를 함께 보존한다**는 selection principle로 전이한다.

\[
\mathcal{R}^{proof}_{\epsilon}(c)=
\{\pi: \pi \vdash c,\ Score(\pi) \ge Score(\pi^*)-\epsilon\}.
\]

따라서 “Proof Rashomon Set”은 본 연구가 제안하는 conceptual transfer이며, 기존 Rashomon 연구가 논리 proof에 동일한 정의를 사용했다는 의미는 아니다. 또한 모든 minimal justification을 무조건 출력하는 Axiom Pinpointing과도 구분된다. Pinpointing은 **무엇이 최소 정당화인가**를 계산하고, Rashomon layer는 **그 중 어떤 설명 집합을 사용자에게 함께 보존·제시할 것인가**를 다룬다.

## 2.6 Neuro-Symbolic Logical Reasoning

LogicNLI는 자연어 모델의 first-order logical reasoning을 entailment, contradiction, neutral, paradox 관점에서 진단하며, BERT, RoBERTa, XLNet이 복잡한 FOL 추론에 한계를 보임을 보고하였다 [13]. FOLIO는 자연어 premise와 FOL annotation을 함께 제공하여 복잡한 FOL reasoning 및 NL-to-FOL 변환을 평가한다 [14]. LINC와 같은 neuro-symbolic 접근은 LLM을 semantic parser로 사용하고 실제 deduction은 외부 theorem prover에 위임함으로써 language-only reasoning의 오류를 줄이는 방향을 제시한다 [15].

본 연구도 자연어가 입력일 경우 formalization layer를 필요로 하지만, 본 논문의 핵심 실험은 **reasoner layer를 분리하여 평가**한다. 따라서 LogicNLI의 structured logical representation과 FOLIO의 FOL annotation을 활용하며, 자연어 parsing 성능과 논리 reasoning 성능을 혼합하지 않는다.

## 2.7 선행연구 대비 연구 위치

| 연구 계열 | 다중 관점 | SAT/Tableau | 모순 원인/범위 | 복수 justification | 본 연구와의 관계 |
|---|---:|---:|---:|---:|---|
| Classical Tableau / Hypertableau | X | O | 전체 KB clash | 보통 X | reasoning core |
| Axiom Pinpointing | X | O | axiom-level cause | **O** | multi-proof의 직접 선행연구 |
| Multi-Context Systems | **O** | 별도 semantics | context/bridge inconsistency | O | inter-context inconsistency의 직접 선행연구 |
| Standpoint Logic / EL / SLTL | **O** | O/전용 calculus | viewpoint-aware reasoning | 부분적 | perspective logic의 가장 가까운 선행연구 |
| Rashomon Set | X | X | X | 모델 대안 집합 | proof-set selection의 개념적 기반 |
| LogicNLI / FOLIO | X | benchmark | contradiction/paradox | proof trace 일부 | reasoning evaluation |
| **Rashomon-Tableau** | **O** | **기존 SAT oracle 재사용** | **Intra/Inter scope** | **O + provenance + selection** | 제안 프레임워크 |

이 표에서 보듯 본 연구의 각 구성요소는 개별적으로 완전히 새로운 것이 아니다. 연구의 의미는 **기존 SAT reasoning, perspective provenance, contradiction localization, multiple justification, Rashomon-style preservation을 하나의 operational pipeline으로 연결하고 그 효과를 분리 평가한다는 점**에 있다.

---

# 3. 문제 정의

관점 집합을

\[
\mathcal{P}=\{P_1,P_2,\dots,P_m\}
\]

이라고 하자. 관점 $P_i$에서 얻은 assertion 집합은

\[
A_i=\{\phi_{i1},\phi_{i2},\dots,\phi_{in_i}\}
\]

이며 모든 관점이 공유하는 domain rule 또는 ontology를 $\mathcal{T}$라 한다. 각 관점의 knowledge base는

\[
K_i=\mathcal{T}\cup A_i
\]

로 정의한다.

SAT 판정 함수는

\[
SAT(K)=
\begin{cases}
1, & K\text{에 model이 존재}\cr
0, & K\text{가 inconsistent}
\end{cases}
\]

이다.

## 3.1 Intra-Perspective Contradiction

하나의 관점 자체가 inconsistent한 경우:

\[
C_{intra}(P_i)=1-SAT(\mathcal{T}\cup A_i).
\]

## 3.2 Inter-Perspective Contradiction

두 관점은 각각 satisfiable하지만 결합했을 때만 inconsistent한 경우:

\[
SAT(K_i)=1,\quad SAT(K_j)=1,
\]

\[
SAT(\mathcal{T}\cup A_i\cup A_j)=0.
\]

이를 inter-perspective contradiction으로 정의한다.

## 3.3 Divergence

관점이 서로 다른 명제를 갖더라도 union이 satisfiable하면 contradiction이 아니다.

\[
A_i \neq A_j \land SAT(\mathcal{T}\cup A_i\cup A_j)=1
\Rightarrow Divergence.
\]

따라서 최종 scope label은 다음 네 가지이다.

\[
Y(P_i,P_j) \in
\{Consistent, Divergence, Intra, Inter\}.
\]

## 3.4 Minimal Justification and Proof Set

모순을 야기하는 최소 assertion subset을 MUS 관점에서

\[
M \subseteq A_i\cup A_j
\]

라 할 때

\[
SAT(\mathcal{T}\cup M)=0
\]

이고 $M$의 모든 proper subset이 satisfiable하면 $M$은 minimal contradiction explanation이다.

하나의 contradiction $c$에 대한 여러 minimal explanation을

\[
\Pi(c)=\{\pi_1,\ldots,\pi_k\}
\]

라 하고, 설명 점수의 차이가 $\epsilon$ 이내인 proof들을 Rashomon-inspired set으로 유지한다.

---

# 4. 제안 방법

제안 방법은 새로운 tableau calculus 하나가 아니라 세 단계의 protocol이다.

\[
\text{Semantic SAT}
\rightarrow
\text{Perspective Index}
\rightarrow
\text{Multi-Justification Preservation}
\]

각 단계가 해결하는 문제는 서로 다르다. 이를 명확히 하기 위해 세 개의 running example을 사용한다.

## 4.1 Example A: 추론 정확성 — 왜 semantic satisfiability가 필요한가

다음 지식베이스를 생각하자.

\[
P(a) \rightarrow Q(a)
\]

\[
\neg Q(a)
\]

질의는

\[
\neg P(a)
\]

이다.

단순 forward rule execution은 $P(a)$가 주어지지 않았기 때문에 새로운 사실을 생성하지 못한다. 따라서 `Unknown`을 반환할 수 있다. 그러나 classical semantics에서는 modus tollens에 의해 $\neg P(a)$가 귀결된다.

Tableau/refutation 방식으로 entailment를 검사하면 질의의 부정을 추가한다.

\[
KB \cup \{P(a)\}
\]

$P(a)\rightarrow Q(a)$와 $P(a)$로부터 $Q(a)$가 성립하고 기존 $\neg Q(a)$와 clash한다.

\[
Q(a),\neg Q(a)\Rightarrow\bot.
\]

따라서

\[
KB\models\neg P(a).
\]

**이 예시가 보여주는 바는 “Tableau가 관점을 잘 처리한다”가 아니다.** 먼저 semantic satisfiability가 단순 forward-only inference보다 더 강한 논리 판정을 제공할 수 있다는 점이다. 본 논문의 첫 번째 실험은 정확히 이 logical core를 FOLIO에서 평가한다.

## 4.2 Example B: 모순 발생 위치 — 전체 UNSAT만으로는 충분하지 않다

공통 ontology rule을 다음과 같이 두자.

\[
FatherOf(x,y)\rightarrow ParentOf(x,y).
\]

### Case B-1: Intra-Perspective Contradiction

관점 $P_1$:

\[
FatherOf(Alice,Bob)
\]

\[
\neg ParentOf(Alice,Bob)
\]

관점 $P_2$:

\[
FriendOf(Carol,Dan)
\]

$P_1$만 보더라도 ontology closure에 의해 `ParentOf(Alice,Bob)`가 도출되므로 $P_1$은 이미 UNSAT이다.

\[
SAT(T\cup A_1)=0.
\]

### Case B-2: Inter-Perspective Contradiction

관점 $P_1$:

\[
FatherOf(Alice,Bob)
\]

관점 $P_2$:

\[
\neg ParentOf(Alice,Bob)
\]

이 경우

\[
SAT(T\cup A_1)=1,
\]

\[
SAT(T\cup A_2)=1,
\]

이지만

\[
SAT(T\cup A_1\cup A_2)=0.
\]

### 기존 merged reasoning과의 차이

두 경우 모두 처음부터

\[
SAT(T\cup A_1\cup A_2)
\]

만 검사하면 결과는 동일하게 `UNSAT`이다. 그러나 Perspective-Indexed protocol은 local SAT 상태를 먼저 보존하기 때문에 Case B-1을 `Intra`, Case B-2를 `Inter`로 구분한다.

이 예시는 본 연구의 핵심적인 **contradiction localization** 기여를 설명하며, controlled four-class scope experiment가 이를 평가한다.

## 4.3 Example C: 복수 proof 보존 — 하나의 모순에 원인이 두 개일 수 있다

다음 규칙과 사실을 생각하자.

\[
A\rightarrow C
\]

\[
B\rightarrow C
\]

\[
A, B, \neg C
\]

이 지식베이스에는 동일한 clash $C\land\neg C$를 만드는 두 개의 독립적인 최소 설명이 존재한다.

첫 번째 proof:

\[
\pi_1=\{A, A\rightarrow C, \neg C\}.
\]

두 번째 proof:

\[
\pi_2=\{B, B\rightarrow C, \neg C\}.
\]

둘 다 하나의 요소만 제거해도 더 이상 contradiction을 보장하지 않는 minimal explanation이다. 첫 번째 proof를 발견하는 즉시 탐색을 멈추면 사용자는 $A$ 경로만 보게 된다. 그러나 실제로 $B$ 경로도 독립적인 원인이다.

본 연구의 Rashomon layer는 “최초 proof”를 “최고 proof”로 간주하지 않는다. 여러 minimal justification에 점수를 부여하고 최고 점수와 $\epsilon$ 이내인 설명을 모두 보존한다.

예를 들어

\[
Score(\pi)=
-\alpha |\pi|
+\beta Diversity(\pi)
+\gamma Provenance(\pi)
\]

와 같이 정의할 수 있다. 현재 구현은 작은 benchmark에서 proof length와 perspective diversity를 이용하는 경량 버전을 사용한다.

이 예시의 핵심은 “multiple justification을 처음 발견했다”는 것이 아니다. Axiom Pinpointing은 이미 이를 다룬다. 본 연구가 평가하는 것은 **single-proof output과 multi-proof preservation 사이의 explanation coverage 차이**이다.

## 4.4 Dual-Proof State

LogicNLI의 paradox는 별도의 중요한 사례를 제공한다. 특정 statement $q$에 대해

\[
KB\models q
\]

이면서 동시에

\[
KB\models\neg q
\]

일 수 있다. 만약 reasoner가 $q$의 proof를 찾는 즉시 `Entailment`로 종료하면 paradox를 잃는다. 따라서 다음 상태를 모두 검사한다.

\[
E^+(q)=1-SAT(KB\cup\{\neg q\}),
\]

\[
E^-(q)=1-SAT(KB\cup\{q\}).
\]

최종 판정은

\[
(E^+,E^-)=
\begin{cases}
(1,0) & Entailment\\
(0,1) & Contradiction\\
(0,0) & Neutral\\
(1,1) & Paradox
\end{cases}
\]

가 된다.

---

# 5. 실험 설계

## 5.1 데이터셋

### FOLIO

FOLIO는 자연어 premise와 first-order logic annotation을 함께 제공하는 human-annotated logical reasoning benchmark이다 [14]. 본 실험은 natural-language parsing이 아니라 logical core를 평가하기 위해 공식 v0.0 validation의 FOL annotation을 사용한다. 현재 구현이 완전히 지원하는 fragment는 ground fact/conjunction, universal Horn implication, explicit negation, single ground-literal query이다. Existential quantification, disjunction, XOR, biconditional 등 전체 FOL 문법은 아직 지원하지 않는다.

따라서 204개 validation example 중 28개만 strict supported fragment로 분류되며 coverage는 13.73%이다. 이 제한은 결과 해석에 반드시 포함한다.

### LogicNLI

LogicNLI는 first-order reasoning을 NLI 형식으로 진단하기 위한 benchmark이며 entailment, contradiction, neutral, paradox/self-contradiction을 구분한다 [13]. 본 실험은 자연어 문장이 아니라 공식 `test_logic` structured representation을 사용한다. 총 100 context, 2,000 statement이며 네 클래스가 각각 500개이다.

### Controlled Contradiction-Scope Benchmark

외부 benchmark에는 본 논문이 정의한 `Intra`, `Inter`, `Divergence`, `Consistent` 네 클래스가 직접 존재하지 않는다. 따라서 capability ablation을 위해 각 클래스 20개씩 총 80개의 controlled logical case를 생성하였다. 이 데이터셋은 자연어 generalization 성능 측정이 아니라 **protocol이 원래 의도한 네 상태를 구분할 수 있는지 확인하는 기능 검증**이다.

### Controlled Multi-Justification Benchmark

20개 case 각각에 두 개의 독립적인 minimal contradiction explanation을 구성하였다. 따라서 gold explanation 수는 총 40개이다. 이 benchmark는 proof enumeration 및 preservation 기능을 검증한다.

### CONAN Case Study

CONAN은 탐정 서사에서 등장인물별 관계 관점을 제공하는 데이터셋이다 [16]. 각 인물에게 알려진 관계가 다르므로 perspective provenance를 실제 서사 데이터에서 관찰할 수 있다. 다만 CONAN 원본은 contradiction-scope label을 제공하지 않으므로 본 논문의 정량 성능 주장을 CONAN에 직접 의존하지 않는다. CONAN은 multi-perspective proposition extraction과 사례 분석에 사용한다.

## 5.2 Baselines

실험 목적별 baseline을 다르게 둔다.

1. **Direct Fact:** query 또는 그 부정이 explicit fact로 존재하는지만 검사한다.
2. **Forward Horn:** implication을 정방향으로 적용하는 forward-chaining baseline이다.
3. **Semantic Clause Tableau:** satisfiability/refutation 기반 logical core이다.
4. **Single-Path Forward Decision:** 첫 번째 지원 방향을 발견하면 판정을 종료한다.
5. **Dual-Proof Decision:** positive/negative proof를 모두 검사한다.
6. **Merged-ABox Tableau:** perspective를 합친 후 한 번만 SAT를 검사한다.
7. **Perspective-Indexed Tableau:** local SAT와 merged SAT를 분리 검사한다.
8. **Single-Proof Explanation:** 첫 번째 minimal explanation 하나만 반환한다.
9. **Multi-Justification/Rashomon:** near-equivalent minimal explanations를 복수로 보존한다.

## 5.3 평가 지표

Accuracy는 전체 instance 중 정확히 분류한 비율이다.

\[
Accuracy=\frac{\#Correct}{\#Total}.
\]

각 클래스의 F1은 Precision과 Recall의 조화평균이다.

\[
F1_c=\frac{2P_cR_c}{P_c+R_c}.
\]

Macro-F1은 각 클래스 F1을 동일 가중치로 평균한다.

\[
MacroF1=\frac{1}{|C|}\sum_{c\in C}F1_c.
\]

본 연구에서 Macro-F1이 중요한 이유는 merged reasoning이 전체 Accuracy는 높게 유지하면서도 `Intra-Contradiction`과 같은 특정 클래스를 전혀 맞히지 못할 수 있기 때문이다. 예를 들어 네 클래스가 균등한 80개 case에서 한 클래스 20개를 전부 놓치면 Accuracy는 75%이지만 해당 클래스 F1은 0이 된다.

Explanation Coverage는 gold minimal explanation 중 반환된 explanation의 비율이다.

\[
Coverage=\frac{|E_{returned}\cap E_{gold}|}{|E_{gold}|}.
\]

---

# 6. 실험 결과

## 6.1 RQ1: 추론 정확성 — FOLIO

FOLIO strict supported fragment 28개에서의 결과는 다음과 같다.

| Method | Accuracy | Macro-F1 |
|---|---:|---:|
| Direct Fact | 42.86% | 26.71% |
| Forward Horn | 75.00% | 74.18% |
| **Semantic Clause Tableau** | **96.43%** | **96.33%** |
| Rashomon-Tableau logical core | 96.43% | 96.33% |

Semantic Clause Tableau는 Forward Horn 대비 Accuracy **+21.43 percentage points**, Macro-F1 **+22.15 percentage points** 높았다. Example A에서 보인 것처럼 refutation 기반 entailment 검사는 forward-only inference가 직접 생성하지 못하는 logical consequence를 판정할 수 있다.

그러나 이 결과에는 두 가지 제한이 있다. 첫째, 28/204, 즉 13.73%의 validation fragment만 대상으로 한다. 둘째, FOLIO는 single-context이므로 perspective indexing이나 Rashomon explanation layer는 class prediction을 변경하지 않는다. 실제로 Semantic Clause Tableau와 Rashomon-Tableau logical core의 Accuracy가 동일한 것은 예상된 결과이다. 따라서 이 실험은 **전체 Rashomon-Tableau 성능이 아니라 semantic reasoning core의 검증**이다.

## 6.2 RQ2: Dual-Proof Contradiction — LogicNLI

LogicNLI structured `test_logic` 전체 2,000 statement에서 결과는 다음과 같다.

| Method | Accuracy | Macro-F1 | Paradox / Self-Contradiction F1 |
|---|---:|---:|---:|
| Direct Fact Dual Check | 50.55% | 42.88% | 0.40% |
| Single-Path Forward | 74.00% | 65.78% | **0.00%** |
| **Dual-Proof Decision** | **98.40%** | **98.40%** | **97.92%** |

Dual-Proof 방식은 Single-Path 대비 Accuracy **+24.40 pp**, Macro-F1 **+32.63 pp** 향상되었다. 특히 paradox F1은 0.00%에서 97.92%로 증가하였다.

이 결과는 Example C와 유사한 “복수 경로를 잃지 않는 것”의 중요성을 다른 형태로 보여준다. 단, 여기서 dual-proof는 여러 MUS를 모두 열거한다는 뜻이 아니다. `q`와 `¬q`라는 두 **결론 방향**의 증명 가능성을 모두 확인하는 것이다. Proof Rashomon layer는 동일 contradiction에 대한 **여러 justification**을 보존한다는 점에서 한 단계 다르다.

LogicNLI 원 논문에서 자연어 입력을 사용하는 RoBERTa의 Test-A Accuracy는 68.3%, XLNet은 65.4%, BERT는 55.9%, human은 77.5%로 보고되었다 [13]. 본 연구의 98.40%를 이 수치와 직접적인 모델 우위로 비교하지 않는다. 원 논문 모델은 자연어 입력에서 logical pattern을 학습해야 하지만 본 실험은 공식 structured logical representation을 입력으로 사용하기 때문이다. 따라서 본 결과는 **end-to-end language understanding 성능이 아니라 symbolic decision procedure의 성능**이다.

## 6.3 RQ3: 모순 발생 위치 — Perspective Scope

80개 controlled four-class benchmark의 결과는 다음과 같다.

| Method | Accuracy | Macro-F1 |
|---|---:|---:|
| Merged-ABox Tableau | 75.00% | 66.67% |
| **Perspective-Indexed Tableau** | **100.00%** | **100.00%** |

Merged baseline은 `Consistent`, `Divergence`, `Inter-Contradiction`은 처리하지만 `Intra-Contradiction` 20개를 모두 union-level contradiction으로 해석하였다. 따라서 Intra 클래스의 Precision, Recall, F1이 모두 0이 된다. Perspective-Indexed protocol은 Example B처럼 local SAT를 먼저 검사하기 때문에 네 클래스를 모두 구분한다.

향상폭은 Accuracy **+25.00 pp**, Macro-F1 **+33.33 pp**이다. 다만 이 결과는 controlled benchmark의 기능 검증이며 natural-language generalization 결과가 아니다. 따라서 “기존 Tableau보다 일반적으로 25% 정확하다”가 아니라 **동일 SAT oracle을 사용하는 상황에서 contradiction-scope classification capability가 향상되었다**고 해석해야 한다.

## 6.4 RQ4: 복수 Explanation Preservation

각 case에 독립적인 minimal contradiction explanation이 2개씩 존재하는 20개 controlled case를 평가하였다.

| Method | Returned Explanations | Gold Explanations | Coverage |
|---|---:|---:|---:|
| Single-Proof | 20 | 40 | 50.00% |
| **Multi-Justification / Rashomon Set** | **40** | **40** | **100.00%** |

Example C와 같이 독립적인 두 proof가 존재할 때 single-proof 방식은 한 경로만 보존한다. 여러 minimal explanation을 유지하면 explanation coverage가 **+50.00 pp** 증가하였다.

이 결과 역시 Axiom Pinpointing보다 더 많은 justification을 “발견했다”는 의미가 아니다. 동일한 enumeration 결과를 사용자-facing explanation 단계에서 하나로 줄이지 않았다는 의미다. 대규모 ontology에서는 justification 수가 지수적으로 증가할 수 있으므로 모든 explanation을 무조건 출력하는 것도 현실적이지 않다. Rashomon-style selection은 바로 이 지점에서 필요한 **bounded presentation policy**로 해석할 수 있다.

## 6.5 결과 요약

| 평가 대상 | 데이터셋 | Baseline | Baseline | Proposed | 개선 |
|---|---|---|---:|---:|---:|
| Logical inference Accuracy | FOLIO fragment | Forward Horn | 75.00% | **96.43%** | **+21.43 pp** |
| Logical inference Macro-F1 | FOLIO fragment | Forward Horn | 74.18% | **96.33%** | **+22.15 pp** |
| Dual-proof Accuracy | LogicNLI | Single Path | 74.00% | **98.40%** | **+24.40 pp** |
| Dual-proof Macro-F1 | LogicNLI | Single Path | 65.78% | **98.40%** | **+32.63 pp** |
| Paradox F1 | LogicNLI | Single Path | 0.00% | **97.92%** | **+97.92 pp** |
| Scope Accuracy | Controlled Multi-Context | Merged Tableau | 75.00% | **100.00%** | **+25.00 pp** |
| Scope Macro-F1 | Controlled Multi-Context | Merged Tableau | 66.67% | **100.00%** | **+33.33 pp** |
| Explanation Coverage | Controlled Multi-MUS | Single Proof | 50.00% | **100.00%** | **+50.00 pp** |

이 표의 행들은 하나의 동일한 “모델 성능”을 반복 측정한 것이 아니다. 각각 다른 구성요소의 효과를 측정한다. 따라서 서로 다른 개선폭을 더하거나 평균내어 하나의 종합 향상률로 보고하지 않는다.

---

# 7. 논의

## 7.1 본 연구에서 실제로 향상된 것은 무엇인가

세 가지 개선은 서로 다른 원인에서 나온다.

첫째, FOLIO의 향상은 **semantic satisfiability reasoning**에서 나온다. 이는 Perspective나 Rashomon과 무관한 logical core의 효과다.

둘째, multi-context scope benchmark의 향상은 **Perspective Index**에서 나온다. 기존 Tableau calculus가 약해서가 아니라, 모든 assertion을 먼저 병합하면 local inconsistency 여부를 다시 복원하기 어렵기 때문이다.

셋째, explanation benchmark의 향상은 **multiple justification preservation**에서 나온다. 이 단계는 SAT/UNSAT class prediction을 바꾸지 않으며, 설명의 recall/coverage를 높인다.

따라서 본 논문의 메시지는 “Rashomon을 붙이면 모든 Accuracy가 올라간다”가 아니다.

\[
\text{Semantic Tableau}
\Rightarrow \text{Inference quality}
\]

\[
\text{Perspective Index}
\Rightarrow \text{Contradiction localization}
\]

\[
\text{Multi-Justification Preservation}
\Rightarrow \text{Explanation coverage}
\]

이다.

## 7.2 Standpoint Logic과의 차이

Standpoint Logic은 여러 viewpoint를 논리 formalism에 직접 통합한다. 이는 본 연구보다 이론적으로 더 근본적인 해결책이다. 예를 들어 standpoint modality를 이용하면 “관점 $s$에서 $\phi$가 참이다”와 같은 표현을 object language 수준에서 정의할 수 있다. SLTL은 이를 temporal reasoning과 결합하고 전용 tableau까지 제공한다.

본 연구는 반대로 perspective를 논리 외부의 provenance key로 처리한다. 따라서 `Perspective ABox → SAT oracle`이라는 단순한 인터페이스만 있으면 기존 reasoner를 사용할 수 있다. 이 방식은 Standpoint Logic보다 덜 표현력 있지만 다음과 같은 실용적 가능성이 있다.

1. 기존 OWL/SAT reasoner를 변경하지 않고 사용할 수 있다.
2. 이미 source id 또는 agent id를 갖는 데이터 파이프라인에 쉽게 연결할 수 있다.
3. contradiction scope를 operational label로 직접 반환할 수 있다.
4. justification 결과와 provenance를 연결하기 쉽다.

따라서 두 연구는 경쟁이라기보다 **formal integration vs lightweight orchestration**의 관계에 가깝다.

## 7.3 Axiom Pinpointing과 Rashomon Layer의 차이

Axiom Pinpointing은 minimal justification을 계산하는 정확한 inference service이다. 이 기능만 놓고 보면 본 연구의 MUS enumeration보다 선행 연구가 훨씬 깊고 성숙하다. 본 연구에서 Rashomon layer가 의미를 가지려면 단순히 “여러 MUS를 반환했다”에서 끝나서는 안 된다.

향후에는 다음과 같은 proof selection 문제로 명확히 확장할 필요가 있다.

\[
Score(\pi)=
\alpha Faithfulness(\pi)
+\beta ProvenanceDiversity(\pi)
-\gamma Length(\pi)
-\delta Redundancy(\pi).
\]

즉 all-justifications를 전부 사용자에게 노출하는 대신, 논리적으로 유효하면서 서로 구조적으로 또는 provenance 측면에서 충분히 다른 explanation set을 선택해야 한다. 기존 연구에서 justification의 구조적 다양성을 분석해 대규모 justification corpus가 매우 유사한 template으로 반복될 수 있음이 보고된 점은 이 방향의 필요성을 뒷받침한다 [17].

이 관점에서 Rashomon layer의 가능성은 **enumeration 자체가 아니라 diversity-aware explanation summarization**에 있다.

## 7.4 적용 가능성

Perspective는 반드시 사람의 의견을 의미하지 않는다. 다음과 같이 provenance가 분리된 모든 정보 source를 하나의 perspective로 볼 수 있다.

- 서로 다른 뉴스 문서
- 법률 사건의 원고/피고 진술
- 여러 의료 전문가의 판단
- 서로 다른 센서 또는 장비
- 데이터베이스의 시점별 snapshot
- 멀티에이전트의 독립 가설
- 로그/메트릭/트레이스 등 서로 다른 observability source
- 여러 LLM이 생성한 candidate hypothesis

따라서 중요한 것은 narrative가 아니라 **source boundary가 semantic하게 의미가 있는가**이다.

---

# 8. 한계

첫째, 현재 FOLIO evaluator는 전체 FOL이 아니라 validation 204개 중 28개, 즉 13.73%의 strict fragment만 완전 지원한다. 따라서 96.43%를 full-FOLIO 성능 또는 SOTA로 주장할 수 없다.

둘째, LogicNLI 실험은 공식 structured logical representation을 사용한다. 이는 language model이 자연어를 logic으로 변환하는 문제를 제거하므로 BERT/RoBERTa의 end-to-end 결과와 직접적인 동등 비교가 아니다.

셋째, contradiction-scope와 explanation benchmark는 controlled synthetic logical case다. protocol의 capability를 검증하기에는 적합하지만 자연 발생 multi-source contradiction에서의 generalization을 보장하지 않는다.

넷째, 현재 Rashomon explanation score는 경량 heuristic이다. 이를 학술적으로 강한 기여로 만들기 위해서는 explanation diversity, redundancy, faithfulness에 대한 명확한 metric과 human evaluation이 필요하다.

다섯째, Axiom Pinpointing, Standpoint Logic, Multi-Context Systems가 이미 본 연구의 상당 부분과 개념적으로 겹친다. 따라서 novelty는 이들 이론을 대체하는 데 있지 않고, 기존 reasoner와 데이터 provenance를 직접 연결하는 lightweight protocol 및 이를 empirical NLP benchmark와 연결하는 데 있다.

여섯째, pairwise perspective만 중심으로 평가하였다. $m>2$ context에서 어떤 최소 perspective coalition이 inconsistency를 만드는지 찾는 문제는 별도의 조합적 문제다. 향후에는

\[
S\subseteq\mathcal{P},\quad SAT(T\cup\bigcup_{P_i\in S}A_i)=0
\]

을 만족하는 minimal perspective subset을 탐색할 필요가 있다.

---

# 9. 결론

본 연구는 논리 reasoning에서 두 종류의 정보 손실에 주목하였다. 첫 번째는 서로 다른 context를 병합하면서 contradiction의 발생 위치를 잃는 문제이고, 두 번째는 하나의 proof만 선택하면서 동등하게 타당한 alternative explanation을 잃는 문제이다. 이를 해결하기 위해 새로운 logical calculus를 만들기보다 기존 satisfiability reasoner를 perspective별로 반복 호출하고, local SAT와 union SAT의 패턴으로 contradiction scope를 분류하며, 여러 minimal justification을 provenance와 함께 보존하는 Rashomon-Tableau framework를 제안하였다.

세 개의 running example은 제안 방법의 역할을 구분한다. Example A는 semantic refutation이 forward-only inference가 놓치는 logical consequence를 판정하는 과정을 보였다. Example B는 동일한 전체 UNSAT 결과가 실제로는 intra-perspective 또는 inter-perspective conflict일 수 있음을 보였다. Example C는 동일 clash에 여러 독립적인 minimal explanation이 존재할 수 있고 single-proof 출력이 그중 일부를 숨길 수 있음을 보였다.

실험에서도 이러한 역할 분리가 관찰되었다. FOLIO supported fragment에서 semantic Tableau는 forward-Horn 대비 Accuracy 21.43 pp, Macro-F1 22.15 pp 높은 성능을 보였다. LogicNLI structured benchmark에서는 dual-proof decision이 single-path 대비 Accuracy 24.40 pp, Macro-F1 32.63 pp 높았고 paradox F1을 0.00%에서 97.92%로 향상시켰다. Controlled multi-context benchmark에서는 perspective indexing을 통해 contradiction-scope Accuracy가 75.00%에서 100.00%로 증가했으며, controlled multi-justification benchmark에서는 explanation coverage가 50.00%에서 100.00%로 증가하였다.

그러나 이 수치들을 하나의 총체적 “Rashomon-Tableau Accuracy 향상”으로 해석해서는 안 된다. Logical core, perspective localization, explanation preservation은 서로 다른 문제를 해결한다. 본 연구의 학술적 가능성은 이 세 문제를 혼합하지 않고 **reasoning correctness, provenance-aware conflict localization, explanation diversity**라는 분리된 축으로 정식화하고 평가하는 데 있다.

향후 연구에서는 full first-order formula coverage, 실제 multi-source contradiction annotation, Standpoint Logic과의 동일 조건 비교, scalable axiom pinpointing backend, diversity-aware proof-set optimization, 그리고 human-centered explanation evaluation이 필요하다.

---

# References

[1] Motik, B., Shearer, R., & Horrocks, I. (2009). **Hypertableau Reasoning for Description Logics.** Journal of Artificial Intelligence Research, 36, 165–228.

[2] Baader, F., & Peñaloza, R. (2007). **Axiom Pinpointing in General Tableaux.** TABLEAUX 2007, LNCS 4548, 11–27.

[3] Baader, F., Peñaloza, R., & Suntisrivaraporn, B. (2007). **Pinpointing in the Description Logic EL+.** KI 2007, LNCS 4667, 52–67.

[4] Kalyanpur, A., Parsia, B., Horridge, M., & Sirin, E. (2007). **Finding All Justifications of OWL DL Entailments.** ISWC/ASWC 2007.

[5] Brewka, G., & Eiter, T. (2007). **Equilibria in Heterogeneous Nonmonotonic Multi-Context Systems.** AAAI 2007.

[6] Eiter, T., Fink, M., Schüller, P., & Weinzierl, A. (2010). **Finding Explanations of Inconsistency in Multi-Context Systems.** KR 2010.

[7] Gómez Álvarez, L., Rudolph, S., & Strass, H. (2022). **How to Agree to Disagree: Managing Ontological Perspectives using Standpoint Logic.** arXiv:2206.06793.

[8] Gómez Álvarez, L., Rudolph, S., & Strass, H. (2023). **Tractable Diversity: Scalable Multiperspective Ontology Management via Standpoint EL.** arXiv:2302.13187.

[9] Gómez Álvarez, L., Rudolph, S., & Strass, H. (2023). **Pushing the Boundaries of Tractable Multiperspective Reasoning: A Deduction Calculus for Standpoint EL+.** KR 2023, 333–343.

[10] Gigante, N., Gómez Álvarez, L., & Lyon, T. S. (2023). **Standpoint Linear Temporal Logic.** KR 2023.

[11] Gómez Álvarez, L., et al. (2024). **Reasoning in SHIQ with Axiom- and Concept-Level Standpoint Modalities.** KR 2024.

[12] Fisher, A., Rudin, C., & Dominici, F. (2019). **All Models are Wrong, but Many are Useful: Learning a Variable's Importance by Studying an Entire Class of Prediction Models Simultaneously.** Journal of Machine Learning Research, 20(177), 1–81.

[13] Tian, J., Li, Y., Chen, W., Xiao, L., He, H., & Jin, Y. (2021). **Diagnosing the First-Order Logical Reasoning Ability Through LogicNLI.** EMNLP 2021, 3738–3747.

[14] Han, S., et al. (2024). **FOLIO: Natural Language Reasoning with First-Order Logic.** EMNLP 2024, 22017–22031.

[15] Olausson, T., et al. (2023). **LINC: A Neurosymbolic Approach for Logical Reasoning by Combining Language Models with First-Order Logic Provers.** EMNLP 2023.

[16] Zhao, R., Zhu, Q., Xu, H., et al. (2024). **Large Language Models Fall Short: Understanding Complex Relationships in Detective Narratives.** Findings of ACL 2024, 7618–7638.

[17] Bail, S., Parsia, B., & Sattler, U. (2013). **The Logical Diversity of Explanations in OWL Ontologies.** CIKM 2013.

[18] Kalyanpur, A., Parsia, B., Sirin, E., & Hendler, J. (2005). **Debugging Unsatisfiable Classes in OWL Ontologies.** Journal of Web Semantics, 3(4), 268–293.

[19] Ozaki, A., & Peñaloza, R. (2018). **Consequence-Based Axiom Pinpointing.** SUM 2018.

[20] Peñaloza, R. (2020). **Axiom Pinpointing.** arXiv:2003.08298.

---

## Reproducibility Note

The numerical results reported in this manuscript are generated by the repository's executable evaluation scripts and stored under `results/`:

- `results/folio_fragment_metrics.json`
- `results/logicnli_metrics.json`
- `results/ablation_metrics.json`

The reported FOLIO score is a supported-fragment result, not a full-FOLIO score. The LogicNLI experiment uses the official structured logical representation, not end-to-end natural-language input. Controlled scope and explanation experiments are capability ablations rather than natural-language generalization tests.
