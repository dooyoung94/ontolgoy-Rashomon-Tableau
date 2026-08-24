# Hugging Face Open-LLM MAGIC Track

This track fills the natural-language MAGIC method matrix with currently callable **open-weight** LLMs through Hugging Face Inference Providers.

## Models

Provider is pinned together with the model so reruns do not silently switch backends.

| Key | Model | HF provider |
|---|---|---|
| `hf_gpt_oss_120b` | `openai/gpt-oss-120b` | Fireworks AI |
| `hf_qwen3_235b` | `Qwen/Qwen3-235B-A22B-Instruct-2507` | DeepInfra |
| `hf_deepseek_r1_0528` | `deepseek-ai/DeepSeek-R1-0528` | DeepInfra |

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

## Run order

Use **Actions → MAGIC Live Model Matrix → Run workflow**.

Recommended progression:

1. `model_set=hf_open_llms`, `limit=20`, `attempts=3`
2. `model_set=hf_open_llms`, `limit=100`, `attempts=3`
3. `model_set=hf_open_llms`, `limit=0`, `attempts=3` for all 588 MAGIC multi-hop rows

Do not make a headline claim from the pilot runs. Only the full 588-row run is used for final reporting.

## Per-model conditions

Every base model is evaluated on the same contexts under four conditions:

1. `Direct`
2. `Compute-Matched Direct`
3. `Rashomon Worlds + same-LLM scorer`
4. `Rashomon Worlds + DeBERTa-v3 scorer`

The main method effect is paired within the same base model. Gold `original_triplet`, `perturb_triplet`, IDs and localization labels are evaluation-only.

## Outputs

The workflow uploads:

- `magic_peer_matrix_summary.json`
- `magic_peer_matrix_paired_stats.json`
- `magic_peer_loc_blinded.json`
- per-model JSONL predictions

`analyze_magic_peer_matrix.py` reports paired method effects, exact McNemar p-values and bootstrap confidence intervals. LOC is exported for blinded human scoring rather than replaced with an automatic LLM judge.
