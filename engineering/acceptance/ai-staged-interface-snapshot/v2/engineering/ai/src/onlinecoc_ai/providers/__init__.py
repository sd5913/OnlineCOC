from .compatible import CompatibleProvider
from .deepseek import DeepSeekProvider


def create_provider(profile, **options):
    return (DeepSeekProvider if profile["adapter"] == "deepseek-chat" else CompatibleProvider)(profile, **options)
