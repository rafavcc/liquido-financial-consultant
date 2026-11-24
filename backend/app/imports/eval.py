"""Avaliação manual contra o modelo real: `uv run python -m app.imports.eval [pasta]`.

Para cada imagem da pasta chama o LLM, grava a resposta em `backend/calibration/respostas/<nome>.json`,
interpreta e, se houver `<nome>.esperado.json` (lista de ofertas com tipo, emissor, taxa, vencimento,
valor_minimo), imprime os acertos por campo. Nunca grava no banco.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx

from app.domain.settings import Settings
from app.imports.interpret import Created, interpret_offer
from app.imports.llm import LlmConfig, OpenAICompatClient
from app.imports.schema import RawExtraction
from app.imports.service import detect_mime

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DIR = BACKEND_DIR / "calibration" / "prints"
FIELDS = ("tipo", "emissor", "taxa", "vencimento", "minimo")


def _num(v: Decimal | None) -> str:
    """Forma canônica de um Decimal (0.1120 == 0.112; 1000.00 == 1000)."""
    if v is None:
        return ""
    n = v.normalize()
    return format(n, "f")


def actual_fields(data) -> dict[str, str]:
    return {
        "tipo": data.tipo.value,
        "emissor": (data.emissor or "").strip().casefold(),
        "taxa": _num(data.taxa),
        "vencimento": data.data_vencimento.isoformat() if data.data_vencimento else "",
        "minimo": _num(data.valor_minimo),
    }


def _expected_fields(e: dict) -> dict[str, str]:
    def dec(v) -> str:
        return _num(Decimal(str(v))) if v is not None else ""

    return {
        "tipo": str(e.get("tipo", "")).upper(),
        "emissor": str(e.get("emissor", "")).strip().casefold(),
        "taxa": dec(e.get("taxa")),
        "vencimento": str(e.get("vencimento", "")),
        "minimo": dec(e.get("valor_minimo")),
    }


def interpreted(raw: RawExtraction, settings: Settings, today: date) -> list:
    """ProductData das ofertas que o interpretador aceita (cortadas, ignoradas e falhas ficam de fora)."""
    out = []
    for offer in raw.ofertas:
        r = interpret_offer(offer, raw.plataforma, settings, today)
        if isinstance(r, Created):
            out.append(r.data)
    return out


def expected_fields_from(obj, settings: Settings, today: date) -> list[dict[str, str]]:
    """O gabarito é uma RawExtraction transcrita à mão (interpretada pelo mesmo caminho do modelo)
    ou uma lista simples de {tipo, emissor, taxa, vencimento, valor_minimo}."""
    if isinstance(obj, dict) and "ofertas" in obj:
        raw = RawExtraction.model_validate(obj)
        return [actual_fields(d) for d in interpreted(raw, settings, today)]
    return [_expected_fields(e) for e in obj]


def compare(expected: list[dict[str, str]], got: list[dict[str, str]]) -> dict[str, tuple[int, int]]:
    """Acertos por campo. Cada oferta esperada é pareada com uma lida ainda livre de mesmo tipo e vencimento
    (ou, na falta, só mesmo vencimento); a que não tem par conta como erro em todos os campos."""
    result = {f: [0, 0] for f in FIELDS}
    livres = list(got)
    for want in expected:
        have = next((g for g in livres if g["tipo"] == want["tipo"] and g["vencimento"] == want["vencimento"]), None)
        if have is None:
            have = next((g for g in livres if g["vencimento"] == want["vencimento"]), None)
        if have is not None:
            livres.remove(have)
        for f in FIELDS:
            result[f][1] += 1
            if have is not None and have[f] == want[f]:
                result[f][0] += 1
    return {f: (a, t) for f, (a, t) in result.items()}


def main(argv: list[str]) -> int:
    folder = Path(argv[0]) if argv else DEFAULT_DIR
    if not folder.is_dir():
        print(f"Pasta de calibração não encontrada: {folder}")
        return 1
    cfg = LlmConfig.from_env()
    if cfg is None:
        print("Defina LLM_BASE_URL e CASA_LLM_MODEL para avaliar.")
        return 1
    client = OpenAICompatClient(cfg, httpx.Client())
    out_dir = BACKEND_DIR / "calibration" / "respostas"
    out_dir.mkdir(parents=True, exist_ok=True)
    settings, today = Settings(), date.today()
    totals = {f: [0, 0] for f in FIELDS}
    for img in sorted(p for p in folder.iterdir() if p.is_file()):
        content = img.read_bytes()
        mime = detect_mime(content)
        if mime is None:
            continue
        print(f"== {img.name}")
        try:
            raw = client.extract(content, mime)
        except Exception as exc:  # avaliação manual: mostra e segue
            print(f"   erro: {exc}")
            continue
        (out_dir / f"{img.stem}.json").write_text(raw.model_dump_json(indent=2), encoding="utf-8")
        created = interpreted(raw, settings, today)
        print(f"   {len(raw.ofertas)} ofertas lidas, {len(created)} interpretadas")
        exp_file = img.with_name(f"{img.stem}.esperado.json")
        if not exp_file.is_file():
            continue
        want = expected_fields_from(json.loads(exp_file.read_text(encoding="utf-8")), settings, today)
        res = compare(want, [actual_fields(d) for d in created])
        for f, (a, t) in res.items():
            totals[f][0] += a
            totals[f][1] += t
            print(f"   {f}: {a}/{t}")
    acertos, total = sum(a for a, _ in totals.values()), sum(t for _, t in totals.values())
    if total:
        print(f"TOTAL: {acertos}/{total} campos corretos ({acertos / total:.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
