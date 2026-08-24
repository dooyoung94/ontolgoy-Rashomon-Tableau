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
_COHERE_UNSUPPORTED_SCHEMA_KEYS = {
    "minimum", "maximum", "minItems", "maxItems", "minLength", "maxLength",
    "uniqueItems", "additionalProperties", "anyOf", "allOf", "oneOf", "not",
}


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


def _validate_schema_value(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(value, dict):
            raise ValueError(f"{path}: expected object")
        required = schema.get("required") or []
        missing = [key for key in required if key not in value]
        if missing:
            raise ValueError(f"{path}: missing required fields {missing}")
        properties = schema.get("properties") or {}
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise ValueError(f"{path}: unexpected fields {extra}")
        for key, child_schema in properties.items():
            if key in value:
                _validate_schema_value(value[key], child_schema, f"{path}.{key}")
    elif expected == "array":
        if not isinstance(value, list):
            raise ValueError(f"{path}: expected array")
        if "minItems" in schema and len(value) < int(schema["minItems"]):
            raise ValueError(f"{path}: fewer than minItems")
        if "maxItems" in schema and len(value) > int(schema["maxItems"]):
            raise ValueError(f"{path}: more than maxItems")
        if schema.get("uniqueItems") and len({json.dumps(x, sort_keys=True) for x in value}) != len(value):
            raise ValueError(f"{path}: duplicate items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate_schema_value(item, item_schema, f"{path}[{index}]")
    elif expected == "string":
        if not isinstance(value, str):
            raise ValueError(f"{path}: expected string")
        if "minLength" in schema and len(value) < int(schema["minLength"]):
            raise ValueError(f"{path}: shorter than minLength")
        if "maxLength" in schema and len(value) > int(schema["maxLength"]):
            raise ValueError(f"{path}: longer than maxLength")
    elif expected == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{path}: expected boolean")
    elif expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{path}: expected integer")
    elif expected == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{path}: expected number")

    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: value not in enum")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ValueError(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise ValueError(f"{path}: above maximum {schema['maximum']}")


def _matches_schema_contract(value: Any, schema: dict[str, Any]) -> bool:
    try:
        _validate_schema_value(value, schema)
        return True
    except ValueError:
        return False


def _cohere_compatible_schema(schema: Any) -> Any:
    if isinstance(schema, list):
        return [_cohere_compatible_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    return {
        key: _cohere_compatible_schema(value)
        for key, value in schema.items()
        if key not in _COHERE_UNSUPPORTED_SCHEMA_KEYS
    }


def _provider_schema(schema: dict[str, Any], profile: str | None) -> dict[str, Any]:
    return _cohere_compatible_schema(schema) if profile == "cohere" else schema


def _extract_json(text: str, schema: dict[str, Any]) -> dict[str, Any]:
    text = _strip_reasoning_wrappers(text)
    if not text:
        raise ValueError("model returned empty content")
    try:
        value = json.loads(text)
        _validate_schema_value(value, schema)
        return value
    except (json.JSONDecodeError, ValueError):
        pass

    decoder = json.JSONDecoder()
    last_validation_error: ValueError | None = None
    for match in re.finditer(r"\{", text):
        try:
            value, _end = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        try:
            _validate_schema_value(value, schema)
            return value
        except ValueError as exc:
            last_validation_error = exc
    if last_validation_error is not None:
        raise last_validation_error
    raise ValueError(f"no JSON object matched required fields {schema.get('required') or []}")


def _schema_response_format(schema_name: str, schema: dict[str, Any]) -> dict[str, Any]:
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", schema_name or "response")[:64] or "response"
    return {
        "type": "json_schema",
        "json_schema": {"name": safe_name, "schema": schema, "strict": True},
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


def _safe_payload_copy(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


class OpenAICompatibleClient:
    """Provider-neutral Chat Completions adapter with auditable transport retries."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout: int = 180,
        max_tokens: int | None = None,
        schema_max_tokens: dict[str, int] | None = None,
        max_retries: int = 0,
        contract_retries: int = 0,
        retry_backoff_seconds: float = 2.0,
        enforce_json_schema: bool = False,
        schema_profile: str | None = None,
        reasoning_effort: str | None = None,
    ):
        self.model = model
        self.api_key = api_key
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.schema_max_tokens = {
            str(key): int(value)
            for key, value in (schema_max_tokens or {}).items()
            if int(value) > 0
        }
        self.max_retries = max(0, max_retries)
        self.contract_retries = max(0, contract_retries)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        self.enforce_json_schema = enforce_json_schema
        self.schema_profile = schema_profile
        self.reasoning_effort = reasoning_effort
        # Contains provider payloads and status metadata only. Authorization headers
        # and API keys are deliberately never recorded.
        self.request_log: list[dict[str, Any]] = []

    def _request(self, payload: dict[str, Any], *, schema_name: str | None = None) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            entry: dict[str, Any] = {
                "schema_name": schema_name,
                "url": self.url,
                "transport_attempt": attempt + 1,
                "payload": _safe_payload_copy(payload),
            }
            self.request_log.append(entry)
            req = urllib.request.Request(
                self.url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = json.load(resp)
                    entry["http_status"] = int(getattr(resp, "status", 200) or 200)
                    entry["response_model"] = raw.get("model", self.model)
                    return raw
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                entry["http_status"] = int(exc.code)
                entry["error_body_preview"] = body[:1200]
                last_error = RuntimeError(f"LLM endpoint failed HTTP {exc.code}: {body[:1200]}")
                if exc.code not in _TRANSIENT_HTTP or attempt >= self.max_retries:
                    raise last_error from exc
            except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
                entry["transport_error"] = str(exc)
                last_error = RuntimeError(f"LLM endpoint transport failure: {exc}")
                if attempt >= self.max_retries:
                    raise last_error from exc

            delay = self.retry_backoff_seconds * (2 ** attempt)
            entry["retry_delay_seconds"] = delay
            if delay:
                time.sleep(delay)

        assert last_error is not None
        raise last_error

    def structured(self, *, instructions: str, input_text: str, schema_name: str, schema: dict[str, Any]) -> JsonResponse:
        base_prompt = f"{instructions}\n\n{_json_contract(schema)}\n\nINPUT\n{input_text}"
        total_input = total_output = total_tokens = 0
        last_error: Exception | None = None
        last_preview = ""
        last_finish = ""
        last_model = self.model
        token_budget = self.schema_max_tokens.get(schema_name, self.max_tokens)
        provider_schema = _provider_schema(schema, self.schema_profile)

        for contract_attempt in range(self.contract_retries + 1):
            prompt = base_prompt
            if contract_attempt:
                prompt += (
                    "\n\nIMPORTANT RETRY: The previous provider response did not satisfy the JSON contract. "
                    "Return only the requested object with every required field and valid value ranges."
                )
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
            }
            if token_budget is not None:
                payload["max_tokens"] = token_budget
            if self.reasoning_effort:
                payload["reasoning_effort"] = self.reasoning_effort
            if self.enforce_json_schema:
                payload["response_format"] = _schema_response_format(schema_name, provider_schema)

            raw = self._request(payload, schema_name=schema_name)
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
                return JsonResponse(parsed, last_model, Usage(total_input, total_output, total_tokens or total_input + total_output))

            final_text = _content_text(message.get("content"))
            reasoning_text = _content_text(message.get("reasoning_content") or message.get("reasoning"))
            candidate_texts = [x for x in (final_text, reasoning_text) if x.strip()]
            last_preview = " | ".join(x[:500] for x in candidate_texts)
            for text in candidate_texts:
                try:
                    data = _extract_json(text, schema)
                    return JsonResponse(data, last_model, Usage(total_input, total_output, total_tokens or total_input + total_output))
                except (ValueError, json.JSONDecodeError) as exc:
                    last_error = exc
            if not candidate_texts:
                last_error = ValueError("model returned empty content")
            if contract_attempt < self.contract_retries:
                delay = self.retry_backoff_seconds * (2 ** contract_attempt)
                if delay:
                    time.sleep(delay)

        raise RuntimeError(
            f"structured response contract failed after {self.contract_retries + 1} attempts; "
            f"finish_reason={last_finish!r}; token_budget={token_budget!r}; "
            f"schema_profile={self.schema_profile!r}; error={last_error}; preview={last_preview[:700]!r}"
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
        payload = {"model": self.model, "max_tokens": 2048, "messages": [{"role": "user", "content": prompt}]}
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
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
        return OpenAICompatibleClient(model=model, api_key=api_key, base_url=base_url or "https://api.openai.com/v1")
    if execution == "huggingface_router":
        return OpenAICompatibleClient(
            model=model,
            api_key=api_key,
            base_url=base_url or HF_ROUTER_URL,
            timeout=int(model_cfg.get("timeout_seconds", 180)),
            max_tokens=int(model_cfg.get("max_tokens", 2048)),
            schema_max_tokens=model_cfg.get("schema_max_tokens") or {},
            max_retries=int(model_cfg.get("max_retries", 2)),
            contract_retries=int(model_cfg.get("contract_retries", 2)),
            retry_backoff_seconds=float(model_cfg.get("retry_backoff_seconds", 2.0)),
            enforce_json_schema=bool(model_cfg.get("structured_output", True)),
            schema_profile=model_cfg.get("schema_profile"),
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
