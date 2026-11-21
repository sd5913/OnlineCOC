"""Stable errors shared by CLI, host adapters and model-facing tools."""


class AiError(ValueError):
    def __init__(self, code, message="", path=""):
        self.code, self.detail, self.path = code, str(message), str(path)
        super().__init__(code + (": " + self.detail if self.detail else ""))

    def public(self):
        return {"code": self.code}


def require(condition, code="INPUT_INVALID", message="", path=""):
    if not condition:
        raise AiError(code, message, path)
