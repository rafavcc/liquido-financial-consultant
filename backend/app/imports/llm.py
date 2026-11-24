"""Cliente de visão: contrato (spec §7.3) e implementações HTTP e falsa."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.imports.schema import EXTRACTION_JSON_SCHEMA, RawExtraction

log = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).parent / "prompt_sistema.md"
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


class LlmUnavailable(Exception):
    """Falha re-tentável: rede, timeout, 5xx, "No model loaded"."""


class LlmBadResponse(Exception):
    """Resposta ilegível; não adianta tentar de novo."""


class LlmClient(Protocol):
    def extract(self, image: bytes, mime: str) -> RawExtraction: ...

    def ping(self) -> bool: ...


@dataclass
class LlmConfig:
    base_url: str
    model: str
    api_key: str | None
    timeout_s: float

    @classmethod
    def from_env(cls) -> LlmConfig | None:
        base_url = os.environ.get("LLM_BASE_URL", "").strip()
        model = os.environ.get("CASA_LLM_MODEL", "").strip()
        if not base_url or not model:
            return None
        return cls(
            base_url.rstrip("/"),
            model,
            os.environ.get("LLM_API_KEY") or None,
            float(os.environ.get("LLM_TIMEOUT_S") or 300),
        )


def _clean(text: str) -> str:
    text = _THINK.sub("", text).strip()
    m = _FENCE.match(text)
    return m.group(1) if m else text


class OpenAICompatClient:
    def __init__(self, config: LlmConfig, http: httpx.Client) -> None:
        self._cfg, self._http = config, http
        self._use_schema = True
        self._system = PROMPT_FILE.read_text(encoding="utf-8")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._cfg.api_key}"} if self._cfg.api_key else {}

    def _post(self, body: dict) -> httpx.Response:
        try:
            return self._http.post(
                f"{self._cfg.base_url}/chat/completions",
                json=body, headers=self._headers(), timeout=self._cfg.timeout_s,
            )
        except httpx.HTTPError as exc:
            raise LlmUnavailable(str(exc) or exc.__class__.__name__) from exc

    def _body(self, messages: list[dict]) -> dict:
        body: dict = {
            "model": self._cfg.model,
            "temperature": 0,
            "messages": messages,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if self._use_schema:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "extracao", "schema": EXTRACTION_JSON_SCHEMA, "strict": True},
            }
        return body

    def _complete(self, messages: list[dict]) -> str:
        resp = self._post(self._body(messages))
        if resp.status_code == 400 and self._use_schema and "response_format" in resp.text:
            self._use_schema = False
            resp = self._post(self._body(messages))
        if resp.status_code == 400 and "No model loaded" in resp.text:
            raise LlmUnavailable("nenhum modelo carregado no servidor")
        if resp.status_code >= 500:
            raise LlmUnavailable(f"HTTP {resp.status_code}")
        if resp.status_code >= 400:
            raise LlmBadResponse(f"HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            return resp.json()["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LlmBadResponse("resposta fora do formato esperado") from exc

    @staticmethod
    def _parse(text: str) -> RawExtraction:
        return RawExtraction.model_validate(json.loads(_clean(text)))

    def extract(self, image: bytes, mime: str) -> RawExtraction:
        url = f"data:{mime};base64,{base64.b64encode(image).decode()}"
        messages: list[dict] = [
            {"role": "system", "content": self._system},
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": url}}]},
        ]
        text = self._complete(messages)
        try:
            return self._parse(text)
        except (ValueError, ValidationError) as exc:
            erro = str(exc)
        messages += [
            {"role": "assistant", "content": text},
            {"role": "user", "content": f"Sua resposta anterior não era JSON válido: {erro}"},
        ]
        try:
            return self._parse(self._complete(messages))
        except (ValueError, ValidationError) as exc:
            raise LlmBadResponse(str(exc)) from exc

    def ping(self) -> bool:
        try:
            return self._http.get(
                f"{self._cfg.base_url}/models", headers=self._headers(), timeout=3
            ).is_success
        except httpx.HTTPError:
            return False


class FakeLlmClient:
    """Para e2e/testes: devolve `<sha256>.json` ou `default.json` do diretório."""

    def __init__(self, fixtures_dir: Path) -> None:
        self._dir = fixtures_dir

    def extract(self, image: bytes, mime: str) -> RawExtraction:
        file = self._dir / f"{hashlib.sha256(image).hexdigest()}.json"
        if not file.is_file():
            file = self._dir / "default.json"
        return RawExtraction.model_validate(json.loads(file.read_text(encoding="utf-8")))

    def ping(self) -> bool:
        return True
