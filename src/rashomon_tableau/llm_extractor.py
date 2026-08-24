from __future__ import annotations

import json
import os
from typing import Iterable

from .models import Literal


class OpenAIPropositionExtractor:
    def __init__(self, model: str = "gpt-5-mini", max_chars: int = 30000):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install optional LLM dependency: pip install -r requirements-llm.txt") from exc
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required for --mode llm")
        self.client = OpenAI()
        self.model = model
        self.max_chars = max_chars

    def extract(self, text: str, allowed_relations: Iterable[str], story: str, perspective: str) -> list[Literal]:
        relations = sorted(set(allowed_relations))
        prompt = f'''You extract interpersonal relationship propositions from a detective narrative.
Return ONLY valid JSON in this schema:
{{"triples":[{{"subject":"...","predicate":"...","object":"..."}}]}}

Rules:
- Use only predicates from ALLOWED_RELATIONS.
- Keep character/entity names exactly as written when possible.
- Do not infer a relationship unless supported by the perspective text.
- One proposition = (subject, predicate, object).
- Do not add negation; this task evaluates relation extraction against Conan gold labels.

ALLOWED_RELATIONS:
{json.dumps(relations, ensure_ascii=False)}

PERSPECTIVE TEXT:
{text[: self.max_chars]}'''.strip()
        response = self.client.responses.create(model=self.model, input=prompt)
        raw = response.output_text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:].lstrip()
        payload = json.loads(raw)
        out: list[Literal] = []
        allowed = set(relations)
        for item in payload.get("triples", []):
            pred = str(item.get("predicate", "")).strip()
            if pred not in allowed:
                continue
            subject = str(item.get("subject", "")).strip(); obj = str(item.get("object", "")).strip()
            if subject and obj:
                out.append(Literal(pred, subject, obj, False, perspective, story, "llm"))
        return out
