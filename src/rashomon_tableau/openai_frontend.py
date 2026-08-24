from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini-2026-03-17")
API_URL = os.getenv("OPENAI_RESPONSES_URL", "https://api.openai.com/v1/responses")

LOCATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "source": {"type": "string", "enum": ["context1", "context2"]},
        "sentence_id": {"type": "integer", "minimum": 0},
    },
    "required": ["source", "sentence_id"],
    "additionalProperties": False,
}

CLAIM_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string"},
                    "relation": {"type": "string"},
                    "object": {"type": "string"},
                    "source": {"type": "string", "enum": ["context1", "context2"]},
                    "sentence_id": {"type": "integer", "minimum": 0},
                    "negated": {"type": "boolean"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["subject", "relation", "object", "source", "sentence_id", "negated", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["claims"],
    "additionalProperties": False,
}

DIRECT_MAGIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "conflict_detected": {"type": "boolean"},
        "locations": {"type": "array", "items": LOCATION_SCHEMA},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["conflict_detected", "locations", "confidence"],
    "additionalProperties": False,
}

COMPUTE_ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "candidate_conflicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "locations": {"type": "array", "items": LOCATION_SCHEMA},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["summary", "locations", "confidence"],
                "additionalProperties": False,
            },
        },
        "analysis_summary": {"type": "string"},
    },
    "required": ["candidate_conflicts", "analysis_summary"],
    "additionalProperties": False,
}

WORLD_SCORE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "support": {"type": "number", "minimum": 0, "maximum": 1},
        "contradiction": {"type": "number", "minimum": 0, "maximum": 1},
        "unresolved": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["support", "contradiction", "unresolved"],
    "additionalProperties": False,
}

BATCH_WORLD_SCORE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "support": {"type": "number", "minimum": 0, "maximum": 1},
                    "contradiction": {"type": "number", "minimum": 0, "maximum": 1},
                    "unresolved": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["id", "support", "contradiction", "unresolved"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["scores"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class OpenAIUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class StructuredResponse:
    data: dict[str, Any]
    model: str
    usage: OpenAIUsage


class OpenAIResponsesClient:
    """Minimal Responses API client with JSON-schema Structured Outputs."""

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL, timeout: int = 120):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for the natural-language MAGIC track")
        self.model = model
        self.timeout = timeout

    def structured(self, *, instructions: str, input_text: str, schema_name: str, schema: dict[str, Any]) -> StructuredResponse:
        payload = {
            "model": self.model,
            "instructions": instructions,
            "input": input_text,
            "store": False,
            "text": {"format": {"type": "json_schema", "name": schema_name, "schema": schema, "strict": True}},
        }
        request = urllib.request.Request(
            API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "rashomon-worlds-magic-eval/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = json.load(response)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI Responses API failed with HTTP {exc.code}: {body[:1000]}") from exc

        text = raw.get("output_text") or _extract_output_text(raw)
        if not text:
            raise RuntimeError(f"Structured response had no output text: {json.dumps(raw)[:1500]}")
        data = json.loads(text)
        usage_raw = raw.get("usage") or {}
        usage = OpenAIUsage(
            input_tokens=int(usage_raw.get("input_tokens", 0) or 0),
            output_tokens=int(usage_raw.get("output_tokens", 0) or 0),
            total_tokens=int(usage_raw.get("total_tokens", 0) or 0),
        )
        return StructuredResponse(data=data, model=raw.get("model", self.model), usage=usage)


def _extract_output_text(raw: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in raw.get("output") or []:
        for content in item.get("content") or []:
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(content["text"])
    return "".join(chunks)


def numbered_context(context: str) -> str:
    import re

    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", context.strip()) if x.strip()]
    return "\n".join(f"[{i}] {sentence}" for i, sentence in enumerate(sentences))


def _contexts_prompt(context1: str, context2: str) -> str:
    return f"CONTEXT1\n{numbered_context(context1)}\n\nCONTEXT2\n{numbered_context(context2)}"


def extract_claims(client: OpenAIResponsesClient, context1: str, context2: str) -> StructuredResponse:
    return client.structured(
        instructions=(
            "Extract only atomic factual relational claims explicitly stated in the two contexts. "
            "Preserve source and sentence_id exactly. Normalize relation names to short lower-case phrases. "
            "Do not infer missing facts, resolve conflicts, or decide which source is true."
        ),
        input_text=_contexts_prompt(context1, context2),
        schema_name="magic_claim_extraction",
        schema=CLAIM_EXTRACTION_SCHEMA,
    )


def direct_magic_judgment(client: OpenAIResponsesClient, context1: str, context2: str) -> StructuredResponse:
    return client.structured(
        instructions=(
            "Determine whether the two contexts contain at least one factual conflict. "
            "If there is a conflict, return all sentence locations needed to localize it. "
            "A conflict may be multi-hop or implicit. Use only the supplied contexts."
        ),
        input_text=_contexts_prompt(context1, context2),
        schema_name="magic_direct_judgment",
        schema=DIRECT_MAGIC_SCHEMA,
    )


def compute_matched_analysis(client: OpenAIResponsesClient, context1: str, context2: str) -> StructuredResponse:
    return client.structured(
        instructions=(
            "Analyze the two contexts for possible factual conflicts, including multi-hop or implicit conflicts. "
            "List plausible candidate conflicts and their sentence locations, but do not force a final binary decision. "
            "Use only the supplied contexts. This is an analysis pass for a second final-decision pass."
        ),
        input_text=_contexts_prompt(context1, context2),
        schema_name="magic_compute_analysis",
        schema=COMPUTE_ANALYSIS_SCHEMA,
    )


def compute_matched_finalize(
    client: OpenAIResponsesClient,
    context1: str,
    context2: str,
    analysis: dict[str, Any],
) -> StructuredResponse:
    input_text = (
        f"{_contexts_prompt(context1, context2)}\n\nFIRST-PASS ANALYSIS\n"
        f"{json.dumps(analysis, ensure_ascii=False)}"
    )
    return client.structured(
        instructions=(
            "Make the final factual-conflict decision from the original contexts and the supplied first-pass analysis. "
            "Return all sentence locations needed to localize any detected conflict. Do not add facts not present in the contexts."
        ),
        input_text=input_text,
        schema_name="magic_compute_final",
        schema=DIRECT_MAGIC_SCHEMA,
    )


def score_world_bidirectionally(
    client: OpenAIResponsesClient,
    *,
    query: str,
    world_evidence: list[str],
) -> StructuredResponse:
    evidence = "\n".join(f"- {x}" for x in world_evidence)
    return client.structured(
        instructions=(
            "Score the supplied evidence against the query in three mutually exclusive directions: support, contradiction, unresolved. "
            "Contradiction means the evidence implies that the query proposition is false, including an incompatible object/value or "
            "the opposite polarity reached through a valid multi-hop chain. Evaluate only this query-evidence pair. "
            "Return calibrated relative scores in [0,1]; the caller renormalizes them."
        ),
        input_text=f"QUERY\n{query}\n\nEVIDENCE\n{evidence}",
        schema_name="rashomon_world_score",
        schema=WORLD_SCORE_SCHEMA,
    )


def score_worlds_batch(client: OpenAIResponsesClient, items: list[dict[str, Any]]) -> StructuredResponse:
    """Score candidate query-path pairs independently in one physical LLM request."""
    return client.structured(
        instructions=(
            "Evaluate EACH input item independently; never average, rank, calibrate, or compare one item against another item in the batch. "
            "For each id, decide how that item's world_evidence bears on that item's query using three scores: support, contradiction, unresolved. "
            "CONTRADICTION is high when the evidence entails that the query is false, including a conflicting object/value, an explicit negation, "
            "or an opposite proposition established through the supplied multi-hop chain. SUPPORT is high only when the evidence entails the query. "
            "UNRESOLVED is high only when the evidence establishes neither the query nor its contradiction. A single strongly contradictory item "
            "must remain strongly contradictory even if every other batch item is unresolved or supportive. Do not dilute contradiction because "
            "other candidate paths exist. Return exactly one score object for every input id, preserve ids exactly, and use scores in [0,1]."
        ),
        input_text=json.dumps({"items": items}, ensure_ascii=False),
        schema_name="rashomon_world_batch_score",
        schema=BATCH_WORLD_SCORE_SCHEMA,
    )
