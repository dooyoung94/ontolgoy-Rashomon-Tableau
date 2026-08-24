# Benchmark Protocol — Rashomon Worlds

## Central test

> **Does Rashomon Worlds improve the same base model's multi-hop conflict identification and localization under identical MAGIC conditions?**

The paper's main MAGIC claim is a **method effect within model**, not a raw comparison between unrelated model families.

---

## 1. Primary MAGIC paired experiment

Use the same five peer model families evaluated by MAGIC:

- Mixtral 8x7B Instruct
- Llama 3.1 70B Instruct
- Claude 3.5 Haiku
- GPT-4o-mini
- o1

For each model `M`, evaluate the same examples under three conditions:

| Condition | Input | LLM reasoning | Rashomon Worlds |
|---|---|---|---|
| **M-Direct** | original MAGIC natural-language contexts | direct conflict judgment | No |
| **M-ComputeMatched** | identical contexts | repeated/direct reasoning with call/token budget matched as closely as possible | No |
| **M-Rashomon** | identical contexts | claim extraction + world scoring by the same model | **Yes** |

The primary effects are paired within model:

```text
ΔID_M  = ID(M-Rashomon)  - ID(M-ComputeMatched)
ΔLOC_M = LOC(M-Rashomon) - LOC(M-ComputeMatched)
```

Secondary effects compare against the original direct condition:

```text
ΔID_direct_M  = ID(M-Rashomon)  - ID(M-Direct)
ΔLOC_direct_M = LOC(M-Rashomon) - LOC(M-Direct)
```

The final method-level evidence should report:

- mean ΔID across the five models;
- mean ΔLOC across the five models;
- number of models with positive ΔID;
- number of models with positive ΔLOC;
- per-conflict-count (1/2/3/4) effects;
- paired bootstrap confidence intervals over examples.

A strong claim requires improvement to be **consistent across several base models**, not just one model.

---

## 2. MAGIC protocol parity

MAGIC's published evaluation performs three independent inference attempts per model. The natural-language reproduction therefore uses **3 attempts/example/condition** where the endpoint permits stochastic sampling.

For ID, retain the paper's success logic: if conflict detection fails in all attempts the example scores 0; otherwise it scores 1.

For LOC, evaluate localization only for correctly identified conflict cases and require all conflict locations according to the official protocol/mapping.

All conditions must use:

- exactly the same `context1` and `context2` text;
- the same sentence numbering and gold-to-sentence mapping;
- the same attempt count;
- frozen prompt templates before test execution;
- identical test examples;
- no `original_triplet`, `perturb_triplet`, `rel_id`, row ID, or gold LOC in prediction prompts.

Gold structured fields may be read **only after prediction** for scoring/audit.

---

## 3. Compute fairness

Rashomon Worlds naturally makes more model calls than a one-shot direct baseline. Therefore two baselines are mandatory:

1. **M-Direct** — reproduces ordinary MAGIC direct prompting.
2. **M-ComputeMatched** — spends a comparable number of calls/tokens on direct/self-consistency reasoning but does not use possible-world construction.

The main causal comparison is `M-Rashomon` vs `M-ComputeMatched`. This prevents a gain caused purely by additional inference compute from being attributed to the method.

Record per method/model:

- API calls/example;
- input tokens/example;
- output tokens/example;
- wall-clock latency where available;
- endpoint/model revision;
- sampling parameters.

---

## 4. Exact model reproducibility

Historical peer numbers are retained as reference, but exact 2025 checkpoints are not uniformly available through first-party APIs in 2026.

`config/magic_peer_model_matrix.yaml` records the expected checkpoint and runtime environment for each family.

Rules:

- If the **exact historical checkpoint** can be served, label the run `historical-checkpoint reproduction`.
- If only a replacement/current checkpoint is available, label it `same-family current-model experiment` and do **not** merge its score with the published MAGIC number.
- For open-weight Mixtral/Llama, a reproducible vLLM/local endpoint serving exact weights is acceptable.
- For retired proprietary checkpoints (notably Claude 3.5 Haiku), an exact rerun may be impossible; replacement-model results must be a separate row.

The method-effect claim itself remains valid as long as **Direct, ComputeMatched, and Rashomon use the exact same checkpoint within each paired model experiment**.

---

## 5. Existing structured MAGIC diagnostics

The previous structured experiment remains a mechanism diagnostic, not the headline peer comparison.

Validated run `32725453943`, artifact `9519356207`:

| Variant | Row conflict recall | Query conflict recall | Gold-world query recall | Structured row exact LOC |
|---|---:|---:|---:|---:|
| B1 Static Tableau | 5.44% | 4.45% | — | — |
| B2 Early-commit single world | 29.93% | 22.63% | — | — |
| B3 Possible-world retention | — | — | **39.39%** | **29.42%** |
| B4 Weakly weighted worlds | 22.79% | 16.86% | — | 7.14% |

Interpretation: possible worlds improve retention, while naive ranking remains insufficient. These numbers are **not official MAGIC ID/LOC**.

---

## 6. Published MAGIC peer reference

Weighted multi-hop values derived from the published N=1..4 subgroup results:

| Peer | Weighted ID | Weighted LOC |
|---|---:|---:|
| Mixtral 8x7B | 28.21% | 9.23% |
| Claude 3.5 Haiku | 48.81% | 34.01% |
| o1 | 48.98% | 28.57% |
| Llama 3.1 70B | 67.32% | 27.15% |
| GPT-4o-mini | 78.40% | 47.28% |

These are the **baseline model rows** motivating the new paired study. The research question is not simply whether Rashomon beats 78.40% globally; it is whether adding the method raises each model's own ID/LOC under controlled conditions.

Expected final table:

| Model | Direct ID | +Rashomon ID | ΔID | Direct LOC | +Rashomon LOC | ΔLOC |
|---|---:|---:|---:|---:|---:|---:|
| Mixtral 8x7B | measured | measured | measured | measured | measured | measured |
| Llama 3.1 70B | measured | measured | measured | measured | measured | measured |
| Claude 3.5 Haiku | measured | measured | measured | measured | measured | measured |
| GPT-4o-mini | measured | measured | measured | measured | measured | measured |
| o1 | measured | measured | measured | measured | measured | measured |
| **Mean** | — | — | **mean ΔID** | — | — | **mean ΔLOC** |

A second table reports ComputeMatched vs Rashomon and is the primary method-effect table.

---

## 7. DAFNA-EA Books — already measured truth adjudication

Current same-protocol track:

- 100 gold books;
- `AuthorsNamesList`;
- 1,999 collapsed source-object claims;
- 227 sources;
- shared surname + first-initial normalization.

Validated run `32726434311`, artifact `9519739380`:

| Method | Exact Truth Accuracy | Author F1 |
|---|---:|---:|
| **Rashomon Worlds — Marginal Reliability** | **62.00%** | **84.13%** |
| Rashomon Worlds — Hard Commit | 61.00% | 84.04% |
| Prior Atomic Resolution | 61.00% | 82.88% |
| Rashomon Worlds — Uniform | 58.00% | 80.38% |
| TruthFinder, official | 57.00% | 66.85% |
| AccuSim, official | 57.00% | 66.18% |
| 2-Estimates, official | 54.00% | 65.28% |
| 3-Estimates, official | 53.00% | 65.45% |
| Accu, official | 53.00% | 65.45% |

Identical-protocol gains:

- marginal vs hard commitment: **+1.00 pp exact**;
- marginal vs prior atomic: **+1.00 pp exact, +1.25 pp F1**;
- marginal vs TruthFinder/AccuSim: **+5.00 pp exact**.

DAFNA establishes the truth-adjudication side; the five-model paired MAGIC experiment is required to establish the multi-hop conflict/localization side.

---

## 8. Leakage and tuning rules

Forbidden:

- test-row-specific relation rules;
- sample IDs, `rel_id`, `original_triplet`, `perturb_triplet`, gold ID or LOC in model inputs;
- prompt or coefficient tuning on the final reported test outputs;
- giving only the Rashomon condition extra external facts unavailable to the baseline.

Development/tuning must use a frozen dev subset or external relation source and then be locked before final evaluation.

---

## 9. Statistical reporting

For every paired model experiment report:

- ID and LOC;
- absolute percentage-point improvement;
- paired bootstrap 95% CI for ΔID and ΔLOC;
- McNemar test for paired binary ID where appropriate;
- per-N conflict breakdown;
- inference cost.

Across models report the mean/median ΔID and ΔLOC and count of positive models. Do not treat five models as independent examples for a high-powered significance claim; example-level paired statistics remain primary.

---

## 10. Reproducibility record

Every headline run must record:

- dataset commit/version;
- exact model checkpoint/endpoint;
- prompt hash;
- attempts/example;
- decoding parameters;
- call/token budget;
- maximum graph hops/worlds;
- gold usage policy;
- code commit;
- CI/live-run identifier;
- raw cached predictions.

The natural-language method comparison is not considered complete until all available peer-model pairs have both baseline and Rashomon predictions under this protocol.
