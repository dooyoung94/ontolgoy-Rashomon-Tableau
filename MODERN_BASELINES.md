# Modern Conflict-Resolution Baselines (2025–2026)

This document separates **directly comparable truth-discovery baselines** from **modern conflict-detection / RAG conflict-resolution research**. Their metrics should not be mixed into one leaderboard because the input/output tasks differ.

## 1. Benchmark taxonomy

| Track | Representative work | Year / venue | Input | Primary task | Directly comparable to Rashomon-Tableau? |
|---|---|---|---|---|---|
| Classical truth discovery | TruthFinder, 2-/3-Estimates, Accu/AccuSim, LTM via DAFNA-EA | legacy | structured source claims | recover gold value | **Yes, on DAFNA Books** |
| Inter-context conflict | MAGIC | Findings EMNLP 2025 | two graph-derived contexts + KG triplets | conflict detection / localization | **Partly (RQ2)** |
| Fact-level RAG conflict | FaithfulRAG | ACL 2025 | parametric/self knowledge + retrieved context | context-faithful QA | No, cross-task positioning |
| Search-source conflict | DRAGged into CONFLICTS | 2025 | real search results + conflict type | conflict-aware answer generation | Future end-to-end RQ3 |
| Transparent RAG conflict | TCR | AAAI 2026 | parametric + retrieved knowledge | detection + controlled resolution | No, cross-task positioning |
| Temporal conflict | WIKIRECENTCHANGES / When Facts Change | Findings ACL 2026 | temporally changed/stable facts | temporal conflict resolution | No, temporal special case |
| Reasoning-path adjudication | KCR | ACL 2026 | explicit conflicting long contexts | logical conflict adjudication | **Strongest conceptual overlap** |

## 2. Strongest recent overlap: KCR (ACL 2026)

**Disentangling Reasoning Logic to Resolve Explicit Knowledge Conflicts** introduces Knowledge Conflict Reasoning (KCR). KCR disentangles conflicting contexts into textual and graph-based reasoning traces and then uses Reinforcement Learning with Verifiable Rewards (RLVR) to encourage logically consistent paths while suppressing spurious ones.

This makes the following claim unsafe for Rashomon-Tableau:

> “We are the first to structure conflicting contexts into reasoning paths and use logical consistency to resolve them.”

That is no longer defensible.

The narrower distinction is:

| Dimension | KCR | Rashomon-Tableau |
|---|---|---|
| Core paradigm | trained LLM / RLVR | symbolic + statistical adjudication |
| Reasoning representation | text + local KG traces | explicit `Source → Claim → Rule → Derived Claim → Conflict` provenance |
| Source identity | context-oriented | explicit source entity |
| Source reliability estimation | not the core mechanism | explicit iterative reliability |
| Partial vs incompatible claim | not the central data model | explicit `exact / partial / conflict` semantics |
| Logic | learned reasoning consistency | SAT/refutation + ontology/rule derivation |
| Final target | answer under explicit context conflict | source-level truth adjudication + confidence |
| Training | required for KCR model | no task-specific model training in current prototype |

Therefore the current defensible contribution is not generic “reasoning-path conflict resolution,” but **provenance-aware symbolic truth adjudication that keeps source identity and reliability attached to logical derivations**.

Reference: ACL 2026, https://aclanthology.org/2026.acl-long.1451/

## 3. MAGIC (Findings EMNLP 2025)

MAGIC is particularly relevant to RQ2 because it evaluates **inter-context conflict detection and localization** and explicitly contains single-hop and multi-hop graph-derived conflicts.

Official repository: https://github.com/HYU-NLP/MAGIC

The repository now includes a reproducible diagnostic:

```bash
python scripts/evaluate_magic_structured.py
```

The evaluator deliberately uses MAGIC's released structured `original_triplet` and `perturb_triplet` fields. Therefore it is a **structured conflict/provenance sanity test**, not a direct reproduction of MAGIC's natural-language LLM ID/LOC benchmark.

### Current result

| MAGIC subset | N | Pairwise structured conflict detection |
|---|---:|---:|
| 1 single-hop | 208 | 98.56% |
| 2 single-hop | 154 | 98.70% |
| 3 single-hop | 80 | 100.00% |
| 4 single-hop | 50 | 100.00% |
| 1 multi-hop | 300 | 27.00% |
| 2 multi-hop | 158 | 41.14% |
| 3 multi-hop | 80 | 37.50% |
| 4 multi-hop | 50 | 38.00% |
| **Overall** | **1,080** | **63.15%** |

### Interpretation

The result is more useful as a **failure analysis** than as a performance claim:

- direct / explicit conflict patterns are handled well;
- multi-hop conflict generation in MAGIC intentionally creates 2–3 logically connected triplets that indirectly contradict the original fact;
- a local pairwise rule cannot infer those graph-composed contradictions;
- therefore the current system needs **relation-composition semantics or an explicit graph-path reasoner** before claiming strong multi-hop conflict localization.

The `pair_localization_coverage=1.0` field in the current diagnostic is **not localization accuracy**. The evaluator always chooses a best pair from the benchmark-provided gold structured fields; it must not be reported as 100% localization.

Reference: Findings EMNLP 2025, https://aclanthology.org/2025.findings-emnlp.466/

## 4. FaithfulRAG (ACL 2025)

FaithfulRAG explicitly models fact-level conflicts between an LLM's self-consistent knowledge and retrieved contexts, then performs a self-thinking process to improve context-faithful generation.

Official code: https://github.com/XMUDeepLIT/Faithful-RAG

It is an important modern comparison, but it is **not an apples-to-apples DAFNA baseline**:

- its target is RAG answer faithfulness;
- it requires an LLM backend (OpenAI, Hugging Face, or LlamaFactory);
- its reported EM/Acc/F1 measure generated answers rather than source-level truth sets.

For this repository it should be discussed as a modern model baseline and, if executed later, evaluated on its own dataset/metric table rather than mixed with DAFNA exact-set accuracy.

Reference: ACL 2025, https://aclanthology.org/2025.acl-long.1062/

## 5. DRAGged into CONFLICTS (2025)

The Google Research CONFLICTS dataset contains realistic search results, annotated conflict types, and a `correct_answer` for each question. This makes it attractive for a future end-to-end RQ3 evaluation.

Official dataset: https://github.com/google-research-datasets/rag_conflicts

However, Rashomon-Tableau currently assumes normalized propositions / structured claims. A fair evaluation on CONFLICTS therefore requires a **claim extraction and entity/relation normalization layer** before symbolic conflict reasoning. Using the dataset's `correct_answer` or conflict label directly as a feature would leak gold information and is not allowed.

This dataset is the preferred next external benchmark once the extraction layer is frozen.

Reference: https://arxiv.org/abs/2506.08500

## 6. TCR (AAAI 2026)

**Seeing through the Conflict: Transparent Knowledge Conflict Handling in Retrieval-Augmented Generation** introduces TCR, which separates semantic match, factual consistency, and self-answerability signals and injects them into generation through a lightweight soft-prompt.

This work overlaps with our transparency motivation, but its conflict is primarily **parametric-vs-retrieved knowledge** and its mechanism is neural/soft-prompt based. Rashomon-Tableau instead targets explicit multi-source provenance and source-level truth adjudication.

Reference: AAAI 2026, https://ojs.aaai.org/index.php/AAAI/article/view/40740

## 7. Temporal conflict: When Facts Change (Findings ACL 2026)

**When Facts Change: Temporal Knowledge Conflict Resolution in LLMs** introduces WIKIRECENTCHANGES and studies conflicts caused by temporal misalignment between parametric memory and current context. It shows that recognizing temporal change does not necessarily translate into correct final predictions.

This is a useful warning for Rashomon-Tableau: **detecting or explaining a conflict and selecting the correct truth are separate evaluation targets**. The paper should continue to report RQ2 localization and RQ3 truth accuracy separately.

Reference: Findings ACL 2026, https://aclanthology.org/2026.findings-acl.103/

## 8. Updated novelty boundary

After considering 2025–2026 work, the paper should **not** claim any of the following as novel in isolation:

- conflict detection;
- graph-based conflict representation;
- reasoning trace decomposition;
- fact-level conflict modeling;
- logic-guided conflict resolution;
- transparent conflict signals;
- truth discovery from multiple sources.

The strongest defensible combined contribution is:

> **A source-provenance-preserving symbolic truth-adjudication pipeline in which source identity and reliability remain attached to explicit/derived propositions, conflicts are localized as derivation paths, partial support is distinguished from incompatibility, and the localized evidence is reused to rank candidate truths.**

In shorthand:

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

## 9. Evaluation policy going forward

Do not mix unrelated metrics in one leaderboard.

### Direct truth-discovery table
Use DAFNA Books only:

- Majority
- official TruthFinder
- official 2-Estimates
- official 3-Estimates
- official Accu
- official AccuSim
- official LTM (repeat because stochastic)
- Rashomon-Tableau

Metrics: Exact Truth Accuracy, Author-level Precision/Recall/F1.

### Modern conflict-localization table
Use MAGIC:

- structured direct-conflict diagnostic (current)
- future graph-path reasoner
- published LLM ID/LOC results only as **paper-reported reference**, unless we actually execute the same models/prompts.

Metrics must follow the benchmark's own detection/localization definition.

### End-to-end modern truth-resolution table
Preferred next dataset: CONFLICTS / DRAGged.

Required before evaluation:

1. freeze claim extraction,
2. freeze normalization,
3. do not expose gold `conflict_type` / `correct_answer` to the model,
4. infer conflict provenance,
5. rank candidate answers,
6. score against `correct_answer`.
