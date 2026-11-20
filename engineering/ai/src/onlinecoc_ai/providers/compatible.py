import asyncio
import copy
import re
from urllib.parse import urlsplit

import httpx

from ..contracts import canonical, digest, loads, validate
from ..errors import AiError, require
from ..profiles import credential
from .base import CAPABILITIES, Completion, ProviderError
from .transport import VerifiedTransport

MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_REQUEST_BYTES = 256 * 1024


class CompatibleProvider:
    capabilities = CAPABILITIES

    def __init__(self, profile, *, transport=None, credential_loader=credential):
        self.profile = copy.deepcopy(validate("Profile", profile))
        self.credential_loader = credential_loader
        url = urlsplit(profile["baseUrl"])
        try:
            require(url.port is None or 1 <= url.port <= 65535, "ENDPOINT_INVALID")
        except ValueError as exc:
            raise AiError("ENDPOINT_INVALID") from exc
        require(not any(ord(c) <= 32 for c in profile["baseUrl"]) and not url.path.endswith("/chat/completions"), "ENDPOINT_INVALID")
        self.endpoint = profile["baseUrl"].rstrip("/") + "/chat/completions"
        request = profile["request"]
        self.client = httpx.AsyncClient(transport=transport or VerifiedTransport(profile["allowPrivateEndpoint"]),
            trust_env=False, follow_redirects=False,
            timeout=httpx.Timeout(request["totalTimeoutMs"] / 1000, connect=request["connectTimeoutMs"] / 1000),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2))

    def body(self, messages, tools):
        # JSON mode requires an explicit instruction, not merely JSON-shaped
        # examples. Guard custom callers too, without mutating their history.
        messages = list(messages)
        if not any(m.get("role") in ("system", "user") and
                   isinstance(m.get("content"), str) and "json" in m["content"].lower()
                   for m in messages):
            messages.insert(0, {"role": "system", "content":
                "Return a valid JSON object matching the requested response contract."})
        result = {"model": self.profile["model"], "messages": messages, "stream": False,
                  "max_tokens": self.profile["request"]["maxOutputTokens"], "response_format": {"type": "json_object"}}
        if tools:
            result["tools"] = tools
        return result

    async def complete(self, messages, tools=(), *, allow_disabled=False):
        require(self.profile["enabled"] or allow_disabled, "PROFILE_DISABLED")
        body = self.body(messages, list(tools))
        raw = canonical(body)
        require(len(raw) <= MAX_REQUEST_BYTES, "CONTEXT_LIMIT_EXCEEDED")
        key = self.credential_loader(self.profile)
        require(isinstance(key, str) and 0 < len(key) <= 8192 and all(32 < ord(c) < 127 for c in key), "CREDENTIAL_MISSING")
        try:
            async with asyncio.timeout(self.profile["request"]["totalTimeoutMs"] / 1000):
                async with self.client.stream("POST", self.endpoint, content=raw,
                    headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}) as response:
                    status = response.status_code
                    if status in (401, 403):
                        raise ProviderError("PROVIDER_AUTH_FAILED", status=status)
                    if status in (400, 422):
                        raise ProviderError("PROVIDER_REQUEST_INVALID", status=status)
                    if status == 402:
                        raise ProviderError("PROVIDER_BALANCE_INSUFFICIENT", status=status)
                    if status == 404:
                        raise ProviderError("PROVIDER_NOT_FOUND", status=status)
                    if status == 408:
                        raise ProviderError("PROVIDER_TIMEOUT", retryable=True, status=status)
                    if status == 413:
                        raise ProviderError("PROVIDER_REQUEST_TOO_LARGE", status=status)
                    if status == 429:
                        raise ProviderError("PROVIDER_RATE_LIMITED", retryable=True, status=status)
                    if 500 <= status <= 599:
                        raise ProviderError("PROVIDER_UNAVAILABLE", retryable=True, status=status)
                    if 300 <= status <= 399:
                        raise ProviderError("PROVIDER_REDIRECT_REJECTED", status=status)
                    if status != 200:
                        raise ProviderError("PROVIDER_HTTP_ERROR", status=status)
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes():
                        chunks.extend(chunk)
                        if len(chunks) > MAX_RESPONSE_BYTES:
                            raise ProviderError("PROVIDER_RESPONSE_LIMIT")
                    return self.parse(bytes(chunks))
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise ProviderError("PROVIDER_TIMEOUT", retryable=True) from None
        except (httpx.TransportError, OSError) as exc:
            raise ProviderError("PROVIDER_UNAVAILABLE", retryable=True) from None

    def parse(self, raw):
        try:
            value = loads(raw)
            require(type(value) is dict and type(value.get("choices")) is list and len(value["choices"]) == 1, "PROVIDER_RESPONSE_INVALID")
            choice = value["choices"][0]
            reason, message, usage = choice["finish_reason"], choice["message"], value["usage"]
            if reason == "length":
                raise ProviderError("PROVIDER_OUTPUT_TRUNCATED")
            require(reason in ("stop", "tool_calls") and message["role"] == "assistant", "PROVIDER_RESPONSE_INVALID")
            require(not message.get("refusal"), "PROVIDER_CONTENT_REJECTED")
            # First version is explicitly non-thinking. Do not persist or expose
            # reasoning content from a misconfigured compatible endpoint.
            require(not message.get("reasoning_content"), "UNSUPPORTED_CAPABILITY")
            normalized_usage = {k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
            require(all(type(v) is int and 0 <= v <= 2**53 - 1 for v in normalized_usage.values()) and
                    usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"], "PROVIDER_USAGE_INVALID")
            content = message.get("content")
            require(content is None or type(content) is str, "PROVIDER_RESPONSE_INVALID")
            normalized = {"role": "assistant", "content": content}
            calls = message.get("tool_calls", [])
            if calls:
                require(reason == "tool_calls" and type(calls) is list and len(calls) <= 16, "PROVIDER_RESPONSE_INVALID")
                normalized["tool_calls"] = []
                identifiers = set()
                for call in calls:
                    function = call["function"]
                    require(call["type"] == "function" and isinstance(call["id"], str) and 0 < len(call["id"]) <= 200 and call["id"] not in identifiers, "PROVIDER_RESPONSE_INVALID")
                    require(isinstance(function["name"], str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", function["name"]) and isinstance(function["arguments"], str), "PROVIDER_RESPONSE_INVALID")
                    identifiers.add(call["id"])
                    require(type(loads(function["arguments"])) is dict, "PROVIDER_RESPONSE_INVALID")
                    normalized["tool_calls"].append({"id": call["id"], "type": "function", "function": {"name": function["name"], "arguments": function["arguments"]}})
            else:
                require(reason == "stop" and content and content.strip(), "PROVIDER_EMPTY_OUTPUT")
                # A valid wire reply has billable usage even if its answer JSON
                # is malformed. Let the coordinator record and repair that text.
            identity={k:value.get(k) for k in ('model','system_fingerprint')}
            require(all(v is None or type(v) is str and 0<len(v)<=200 and all(ord(c)>=32 for c in v) for v in identity.values()),'PROVIDER_RESPONSE_INVALID')
            return Completion(normalized, normalized_usage, reason, digest(value), identity['model'], identity['system_fingerprint'])
        except ProviderError:
            raise
        except (AiError, KeyError, TypeError, ValueError) as exc:
            raise ProviderError(getattr(exc, "code", "PROVIDER_RESPONSE_INVALID") if getattr(exc, "code", "").startswith(("PROVIDER_", "UNSUPPORTED_")) else "PROVIDER_RESPONSE_INVALID") from None

    async def probe(self):
        result = await self.complete([{"role": "system", "content": 'Return only json: {"ok":true}.'}, {"role": "user", "content": "Connection and JSON capability check."}], allow_disabled=True)
        require(loads(result.message["content"]) == {"ok": True}, "UNSUPPORTED_CAPABILITY")
        tool = {"type": "function", "function": {"name": "connection_probe", "description": "Return the connection probe status",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}}
        called = await self.complete([{"role": "system", "content": 'Call connection_probe exactly once with {}. Do not answer directly. Use json.'},
            {"role": "user", "content": "Check tool calling support."}], [tool], allow_disabled=True)
        calls = called.message.get("tool_calls", [])
        require(len(calls) == 1 and calls[0]["function"]["name"] == "connection_probe" and loads(calls[0]["function"]["arguments"]) == {}, "UNSUPPORTED_CAPABILITY")
        return {"profileId": self.profile["profileId"], "profileRevision": self.profile["revision"], "model": self.profile["model"],
                "jsonProbe": "passed", "toolProbe": "passed", "usage": {k: result.usage[k] + called.usage[k] for k in result.usage},
                "returnedModels":[result.model,called.model], "systemFingerprints":[result.system_fingerprint,called.system_fingerprint],
                "responseDigests": [result.response_digest, called.response_digest]}

    async def close(self):
        await self.client.aclose()
