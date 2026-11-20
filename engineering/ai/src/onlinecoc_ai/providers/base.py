"""Small provider interface and sanitized errors; no raw HTTP diagnostics."""
from dataclasses import dataclass

from ..errors import AiError


class ProviderError(AiError):
    def __init__(self, code, *, retryable=False, status=None):
        super().__init__(code)
        self.retryable, self.http_status = retryable, status


@dataclass(frozen=True)
class Completion:
    message: dict
    usage: dict
    finish_reason: str
    response_digest: str
    model: str | None = None
    system_fingerprint: str | None = None


CAPABILITIES = {"protocol": "chat-completions", "jsonObject": True, "tools": True,
                "stream": False, "thinking": False}
