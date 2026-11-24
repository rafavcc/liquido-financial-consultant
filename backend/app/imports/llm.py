"""Contrato do cliente de visão (spec §7.3). A implementação HTTP vem na Task 7."""

from __future__ import annotations

from typing import Protocol

from app.imports.schema import RawExtraction


class LlmUnavailable(Exception):
    """Falha re-tentável: rede, timeout, 5xx, "No model loaded"."""


class LlmBadResponse(Exception):
    """Resposta ilegível; não adianta tentar de novo."""


class LlmClient(Protocol):
    def extract(self, image: bytes, mime: str) -> RawExtraction: ...

    def ping(self) -> bool: ...
