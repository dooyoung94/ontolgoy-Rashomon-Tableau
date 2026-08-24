from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini-2026-03-17")
API_URL = os.getenv("OPENAI_RESPONSES_URL", "https://api.openai.com/v1/responses")


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
        "locations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "enum": ["context1", "context2"]},
                    "sentence_id": {"type": "integer", "minimum": 0},
                },
                "required": ["source", "sentence_id"],
                "additionalProperties": False,
            },
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["conflict_detected", "locations", "confidence"],
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
    """Minimal Responses API client with JSON-schema Structured Outputs.

    The benchmark deliberately keeps this wrapper small so the evaluation can pin
    the model snapshot and log exact token usage without depending on SDK behavior.
    """

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
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
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
    """Deterministically split MAGIC prose into sentence-addressable text.

    This is intentionally simple; LOC evaluation stores the exact numbered text fed
    to both the direct baseline and the Rashomon extraction pipeline.
    """
    import re

    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", context.strip()) if x.strip()]
    return "\n".join(f"[{i}] {sentence}" for i, sentence in enumerate(sentences))


def extract_claims(client: OpenAIResponsesClient, context1: str, context2: str) -> StructuredResponse:
    prompt = f"CONTEXT1\n{numbered_context(context1)}\n\nCONTEXT2\n{numbered_context(context2)}"
    return client.structured(
        instructions=(
            "Extract only atomic factual relational claims explicitly stated in the two contexts. "
            "Preserve source and sentence_id exactly. Normalize relation names to short lower-case phrases. "
            "Do not infer missing facts, resolve conflicts, or decide which source is true."
        ),
        input_text=prompt,
        schema_name="magic_claim_extraction",
        schema=CLAIM_EXTRACTION_SCHEMA,
    )


def direct_magic_judgment(client: OpenAIResponsesClient, context1: str, context2: str) -> StructuredResponse:
    prompt = f"CONTEXT1\n{numbered_context(context1)}\n\nCONTEXT2\n{numbered_context(context2)}"
    return client.structured(
        instructions=(
            "Determine whether the two contexts contain at least one factual conflict. "
            "If there is a conflict, return all sentence locations needed to localize it. "
            "A conflict may be multi-hop or implicit. Use only the supplied contexts."
        ),
        input_text=prompt,
        schema_name="magic_direct_judgment",
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
            "Score the supplied possible world against the query in three mutually exclusive directions: "
            "support, contradiction, unresolved. Consider the entire multi-hop evidence. "
            "Return calibrated relative scores in [0,1]; they need not be exact probabilities because the caller renormalizes them."
        ),
        input_text=f"QUERY\n{query}\n\nWORLD EVIDENCE\n{evidence}",
        schema_name="rashomon_world_score",
        schema=WORLD_SCORE_SCHEMA,
    )
