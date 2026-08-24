# Hugging Face Open-LLM MAGIC Track

This track fills the natural-language MAGIC method matrix with currently callable **open-weight** LLMs through Hugging Face Inference Providers.

## Models

Provider is pinned together with the model so reruns do not silently switch backends.

| Key | Model | HF provider |
|---|---|---|
| `hf_gpt_oss_120b` | `openai/gpt-oss-120b` | Novita |
| `hf_qwen3_235b` | `Qwen/Qwen3-235B-A22B-Instruct-2507` | Novita |
| `hf_llama_3_3_70b` | `meta-llama/Llama-3.3-70B-Instruct` | Together |

DeepSeek-R1-0528 was removed from the active HF matrix after bounded smoke tests repeatedly returned provider-side 504/429 errors. The replacement Llama 3.3 70B route is pinned to Together because Hugging Face currently reports structured-output support for that provider/model combination.

The runtime uses Hugging Face's OpenAI-compatible router:

```text
https://router.huggingface.co/v1
```

## Credential

Create a Hugging Face token that can call Inference Providers and add it to the GitHub repository as an Actions secret named:

```text
HF_TOKEN
```

The benchmark never writes the token to an artifact.

## Bounded smoke test

Before any benchmark pilot, run the bounded contract smoke test. It performs exactly three provider requests per base model with client retries disabled:

1. Direct conflict JSON contract
2. Claim-extraction JSON contract
3. World-score JSON contract

For the three-model HF set the hard cap is therefore **9 provider requests total**. The smoke test is engineering validation only and is never reported as a MAGIC benchmark result.

Task-specific output budgets are used because claim extraction is materially longer than direct judgment or world scoring:

- Direct: 1024 output tokens
- Claim extraction: 4096 output tokens
- World score: 768 output tokens

## Benchmark run order

After the bounded smoke test succeeds, use staged experiments rather than jumping directly to all 588 rows:

1. 20-row pilot for method/cost validation
2. 100-row intermediate run for statistical and runtime stability
3. Full 588-row run for final reporting

The final paper protocol uses three macro attempts per example. Pilot attempts may be reduced during engineering validation, but pilot numbers are not headline results.

## Per-model conditions

Every base model is evaluated on the same contexts under four conditions:

1. `Direct`
2. `Compute-Matched Direct`
3. `Rashomon Worlds + same-LLM scorer`
4. `Rashomon Worlds + DeBERTa-v3 scorer`

The main method effect is paired within the same base model. Gold `original_triplet`, `perturb_triplet`, IDs and localization labels are evaluation-only.

Compute-Matched Direct is bounded. A sample whose compute budget cannot be matched within the configured hard cap is marked `budget_reached=false` and excluded from the compute-matched paired comparison rather than silently using an unmatched sample.

## Outputs

The workflow uploads:

- `magic_peer_matrix_summary.json`
- `magic_peer_matrix_paired_stats.json`
- `magic_peer_loc_blinded.json`
- per-model JSONL predictions

`analyze_magic_peer_matrix.py` reports paired method effects, exact McNemar p-values and bootstrap confidence intervals. LOC is exported for blinded human scoring rather than replaced with an automatic LLM judge.
