from .compatible import CompatibleProvider


class DeepSeekProvider(CompatibleProvider):
    def body(self, messages, tools):
        return {**super().body(messages, tools), "thinking": {"type": "disabled"}}
