"""Immutable provider snapshots, isolated by asynchronous execution context."""

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Literal

ProviderKind = Literal["llm", "image", "video"]


@dataclass(frozen=True)
class ProviderBinding:
    provider_id: str
    model: str
    api_key: str = field(repr=False)
    embedding_model: str = "text-embedding-v4"
    api_base: str | None = None


@dataclass(frozen=True)
class ProviderSnapshot:
    tenant_id: str
    bindings: tuple[tuple[str, ProviderBinding], ...]

    def get(self, kind: str) -> ProviderBinding | None:
        return next((binding for key, binding in self.bindings if key == kind), None)


active_providers: ContextVar[ProviderSnapshot | None] = ContextVar(
    "active_providers", default=None
)
