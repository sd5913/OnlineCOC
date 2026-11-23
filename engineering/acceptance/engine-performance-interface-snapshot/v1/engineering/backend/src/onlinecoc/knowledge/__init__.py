"""Host-owned, account-scoped disclosure. Independent of the AI runtime."""
from .service import KnowledgeService
from .provider import HostStateProvider

__all__ = ['KnowledgeService', 'HostStateProvider']
