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


def _matches_schema_contract(value: Any, schema: dict[str, Any]) -> bool:
    """Lightweight contract check used only to select the intended JSON object.

    The provider is still asked for strict JSON Schema output. This check prevents
    fallback parsing from accidentally selecting an echoed schema or another JSON
    object that does not contain the response's required top-level fields.
    """
    if not isinstance(value, dict):
        return False
    required = schema.get("required") or []
    if any(key not in value for key in required):
        return False
    properties = schema.get("properties") or {}
    type_checks = {
        "array": list,
        "object": dict,
        "string": str,
        "boolean": bool,
        "number": (int, float),
        "integer": int,
    }
    for key in required:
        spec = properties.get(key) or {}
        expected = spec.get("type")
        py_type = type_checks.get(expected)
        if py_type is not None and not isinstance(value.get(key), py_type):
            return False
    return True


def _extract_json(text: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Extract the first complete object satisfying the requested response schema."""
    text = _strip_reasoning_wrappers(text)
    if not text:
        raise ValueError("model returned empty content")

    try:
        value = json.loads(text)
        if _matches_schema_contract(value, schema):
            return value
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _end = decoder.raw_decode(text[match.start() :])
        except json.JSONDecodeError:
            continue
        if _matches_schema_contract(value, schema):
            return value

    required = schema.get("required") or []
    raise ValueError(f"no JSON object matched required fields {required}")


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


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        chunks: list[str] = []
        for item in value:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    chunks.append(text)
        return "".join(chunks)
    return ""


class OpenAICompatibleClient:
    """Provider-neutral Chat Completions adapter with HF reliability controls."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout: int = 180,
        max_tokens: int | None = None,
        max_retries: int = 0,
        contract_retries: int = 0,
        retry_backoff_seconds: float = 2.0,
        enforce_json_schema: bool = False,
        reasoning_effort: str | None = None,
    ):
        self.model = model
        self.api_key = api_key
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.max_retries = max(0, max_retries)
        self.contract_retries = max(0, contract_retries)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        self.enforce_json_schema = enforce_json_schema
        self.reasoning_effort = reasoning_effort

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
        base_prompt = f"{instructions}\n\n{_json_contract(schema)}\n\nINPUT\n{input_text}"
        total_input = 0
        total_output = 0
        total_tokens = 0
        last_error: Exception | None = None
        last_preview = ""
        last_finish = ""
        last_model = self.model

        for contract_attempt in range(self.contract_retries + 1):
            prompt = base_prompt
            if contract_attempt:
                prompt += (
                    "\n\nIMPORTANT RETRY: The previous provider response did not satisfy the JSON contract. "
                    "Return only the requested object with every required top-level field."
                )
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
            }
            if self.max_tokens is not None:
                payload["max_tokens"] = self.max_tokens
            if self.reasoning_effort:
                payload["reasoning_effort"] = self.reasoning_effort
            if self.enforce_json_schema:
                payload["response_format"] = _schema_response_format(schema_name, schema)

            raw = self._request(payload)
            last_model = raw.get("model", self.model)
            u = raw.get("usage") or {}
            total_input += int(u.get("prompt_tokens", 0) or 0)
            total_output += int(u.get("completion_tokens", 0) or 0)
            total_tokens += int(u.get("total_tokens", 0) or 0)

            choice = (raw.get("choices") or [{}])[0]
            last_finish = str(choice.get("finish_reason") or "")
            message = choice.get("message") or {}

            parsed = message.get("parsed")
            if _matches_schema_contract(parsed, schema):
                return JsonResponse(
                    data=parsed,
                    model=last_model,
                    usage=Usage(total_input, total_output, total_tokens or total_input + total_output),
                )

            final_text = _content_text(message.get("content"))
            reasoning_text = _content_text(message.get("reasoning_content") or message.get("reasoning"))
            candidate_texts = [x for x in (final_text, reasoning_text) if x.strip()]
            last_preview = " | ".join(x[:500] for x in candidate_texts)

            for text in candidate_texts:
                try:
                    data = _extract_json(text, schema)
                    return JsonResponse(
                        data=data,
                        model=last_model,
                        usage=Usage(total_input, total_output, total_tokens or total_input + total_output),
                    )
                except (ValueError, json.JSONDecodeError) as exc:
                    last_error = exc

            if not candidate_texts:
                last_error = ValueError("model returned empty content")

            if contract_attempt < self.contract_retries:
                delay = self.retry_backoff_seconds * (2**contract_attempt)
                if delay:
                    time.sleep(delay)

        raise RuntimeError(
            f"structured response contract failed after {self.contract_retries + 1} attempts; "
            f"finish_reason={last_finish!r}; error={last_error}; preview={last_preview[:700]!r}"
        )


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
        return JsonResponse(data=_extract_json(text, schema), model=raw.get("model", self.model), usage=usage)


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
            timeout=int(model_cfg.get("timeout_seconds", 180)),
            max_tokens=int(model_cfg.get("max_tokens", 2048)),
            max_retries=int(model_cfg.get("max_retries", 2)),
            contract_retries=int(model_cfg.get("contract_retries", 2)),
            retry_backoff_seconds=float(model_cfg.get("retry_backoff_seconds", 2.0)),
            enforce_json_schema=bool(model_cfg.get("structured_output", True)),
            reasoning_effort=model_cfg.get("reasoning_effort"),
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
