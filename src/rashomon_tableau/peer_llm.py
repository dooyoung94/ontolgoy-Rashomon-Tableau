from __future__ import annotations

import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


HF_ROUTER_URL = "https://router.huggingface.co/v1"
_TRANSIENT_HTTP = {408, 409, 425, 429, 500, 502, 503, 504}


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


def _strip_reasoning_wrappers(text: str) -> str:
    text = text.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _extract_json(text: str) -> dict[str, Any]:
    """Extract the first complete JSON object from a model response.

    Structured-output capable providers should already return valid JSON. This
    fallback tolerates reasoning wrappers, markdown fences, and prose or a second
    object after the first valid JSON object without silently accepting a list or
    scalar as the contract response.
    """
    text = _strip_reasoning_wrappers(text)
    if not text:
        raise ValueError("model returned empty content")

    try:
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("model returned non-object JSON")
        return value
    except json.JSONDecodeError as first_error:
        decoder = json.JSONDecoder()
        for match in re.finditer(r"\{", text):
            try:
                value, _end = decoder.raw_decode(text[match.start() :])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        raise first_error


def _schema_response_format(schema_name: str, schema: dict[str, Any]) -> dict[str, Any]:
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", schema_name or "response")[:64] or "response"
    return {
        "type": "json_schema",
        "json_schema": {
            "name": safe_name,
            "schema": schema,
            "strict": True,
        },
    }


class OpenAICompatibleClient:
    """Provider-neutral Chat Completions adapter.

    All calls retain the same textual JSON contract. For Hugging Face Inference
    Providers we additionally use the standardized OpenAI-compatible JSON Schema
    response_format for every HF model and every experimental condition, avoiding
    model-specific parsing advantages while preventing malformed benchmark output.
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout: int = 180,
        max_tokens: int | None = None,
        max_retries: int = 0,
        retry_backoff_seconds: float = 2.0,
        enforce_json_schema: bool = False,
    ):
        self.model = model
        self.api_key = api_key
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.max_retries = max(0, max_retries)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        self.enforce_json_schema = enforce_json_schema

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.load(resp)
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                last_error = RuntimeError(f"LLM endpoint failed HTTP {exc.code}: {body[:1200]}")
                if exc.code not in _TRANSIENT_HTTP or attempt >= self.max_retries:
                    raise last_error from exc
            except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
                last_error = RuntimeError(f"LLM endpoint transport failure: {exc}")
                if attempt >= self.max_retries:
                    raise last_error from exc

            delay = self.retry_backoff_seconds * (2**attempt)
            if delay:
                time.sleep(delay)

        assert last_error is not None
        raise last_error

    def structured(self, *, instructions: str, input_text: str, schema_name: str, schema: dict[str, Any]) -> JsonResponse:
        prompt = f"{instructions}\n\n{_json_contract(schema)}\n\nINPUT\n{input_text}"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if self.enforce_json_schema:
            payload["response_format"] = _schema_response_format(schema_name, schema)

        raw = self._request(payload)
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
            timeout=int(model_cfg.get("timeout_seconds", 150)),
            max_tokens=int(model_cfg.get("max_tokens", 1024)),
            max_retries=int(model_cfg.get("max_retries", 2)),
            retry_backoff_seconds=float(model_cfg.get("retry_backoff_seconds", 2.0)),
            enforce_json_schema=bool(model_cfg.get("structured_output", True)),
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
