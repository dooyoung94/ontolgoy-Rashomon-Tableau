from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


HF_ROUTER_URL = "https://router.huggingface.co/v1"


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class JsonResponse:
    data: dict[str, Any]
    model: str
    usage: Usage


def _json_contract(schema: dict[str, Any]) -> str:
    return (
        "Return exactly one JSON object and no prose or markdown. "
        "The JSON must conform to this schema:\n" + json.dumps(schema, ensure_ascii=False)
    )


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("model returned non-object JSON")
        return value
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            value = json.loads(text[start : end + 1])
            if isinstance(value, dict):
                return value
        raise


class OpenAICompatibleClient:
    """Provider-neutral Chat Completions adapter.

    No vendor-specific structured-output feature is used: every evaluated model
    receives the same textual JSON contract.  This works with OpenAI, vLLM and the
    Hugging Face Inference Providers OpenAI-compatible router.
    """

    def __init__(self, *, model: str, api_key: str, base_url: str, timeout: int = 180):
        self.model = model
        self.api_key = api_key
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.timeout = timeout

    def structured(self, *, instructions: str, input_text: str, schema_name: str, schema: dict[str, Any]) -> JsonResponse:
        prompt = f"{instructions}\n\n{_json_contract(schema)}\n\nINPUT\n{input_text}"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = json.load(resp)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM endpoint failed HTTP {exc.code}: {body[:1200]}") from exc
        choice = (raw.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or ""
        data = _extract_json(content)
        u = raw.get("usage") or {}
        usage = Usage(
            input_tokens=int(u.get("prompt_tokens", 0) or 0),
            output_tokens=int(u.get("completion_tokens", 0) or 0),
            total_tokens=int(u.get("total_tokens", 0) or 0),
        )
        return JsonResponse(data=data, model=raw.get("model", self.model), usage=usage)


class AnthropicMessagesClient:
    """Anthropic Messages adapter using the same textual JSON contract."""

    def __init__(self, *, model: str, api_key: str, base_url: str = "https://api.anthropic.com/v1", timeout: int = 180):
        self.model = model
        self.api_key = api_key
        self.url = base_url.rstrip("/") + "/messages"
        self.timeout = timeout

    def structured(self, *, instructions: str, input_text: str, schema_name: str, schema: dict[str, Any]) -> JsonResponse:
        prompt = f"{instructions}\n\n{_json_contract(schema)}\n\nINPUT\n{input_text}"
        payload = {
            "model": self.model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = json.load(resp)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Anthropic endpoint failed HTTP {exc.code}: {body[:1200]}") from exc
        text = "".join(x.get("text", "") for x in raw.get("content", []) if x.get("type") == "text")
        u = raw.get("usage") or {}
        usage = Usage(
            input_tokens=int(u.get("input_tokens", 0) or 0),
            output_tokens=int(u.get("output_tokens", 0) or 0),
            total_tokens=int(u.get("input_tokens", 0) or 0) + int(u.get("output_tokens", 0) or 0),
        )
        return JsonResponse(data=_extract_json(text), model=raw.get("model", self.model), usage=usage)


def client_from_environment(model_cfg: dict[str, Any]):
    model_env = model_cfg.get("model_env", "")
    model = os.getenv(model_env, model_cfg["exact_model"]) if model_env else model_cfg["exact_model"]
    api_key_env = model_cfg.get("api_key_env", "")
    api_key = os.getenv(api_key_env, "")
    if not api_key:
        raise RuntimeError(f"Missing API key env {api_key_env} for {model_cfg['display_name']}")

    execution = model_cfg.get("execution")
    base_env = model_cfg.get("base_url_env", "")
    base_url = os.getenv(base_env, "") if base_env else ""

    if execution == "openai":
        return OpenAICompatibleClient(
            model=model,
            api_key=api_key,
            base_url=base_url or "https://api.openai.com/v1",
        )
    if execution == "huggingface_router":
        return OpenAICompatibleClient(
            model=model,
            api_key=api_key,
            base_url=base_url or HF_ROUTER_URL,
        )
    if execution == "openai_compatible":
        if not base_url:
            raise RuntimeError(f"Missing endpoint env {base_env} for {model_cfg['display_name']}")
        return OpenAICompatibleClient(model=model, api_key=api_key, base_url=base_url)
    if execution == "anthropic_or_archived_endpoint":
        mode = os.getenv("CLAUDE_ENDPOINT_MODE", "anthropic")
        if mode == "openai_compatible":
            if not base_url:
                raise RuntimeError("CLAUDE_BASE_URL required for archived OpenAI-compatible Claude endpoint")
            return OpenAICompatibleClient(model=model, api_key=api_key, base_url=base_url)
        return AnthropicMessagesClient(model=model, api_key=api_key, base_url=base_url or "https://api.anthropic.com/v1")
    raise ValueError(f"Unsupported execution mode: {execution}")
