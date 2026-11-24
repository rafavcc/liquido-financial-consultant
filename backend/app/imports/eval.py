"""Avaliação manual contra o modelo real: `uv run python -m app.imports.eval [pasta]`.

Para cada imagem da pasta chama o LLM, grava a resposta em `backend/calibration/respostas/<nome>.json`,
interpreta e, se houver `<nome>.esperado.json` (lista de ofertas com tipo, emissor, taxa, vencimento,
valor_minimo), imprime os acertos por campo. Nunca grava no banco.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import httpx

from app.domain.settings import Settings
from app.imports.interpret import Created, interpret_offer
from app.imports.llm import LlmConfig, OpenAICompatClient
from app.imports.service import detect_mime

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DIR = BACKEND_DIR / "calibration" / "prints"
FIELDS = ("tipo", "emissor", "taxa", "vencimento", "minimo")


def actual_fields(data) -> dict[str, str]:
    return {
        "tipo": data.tipo.value,
        "emissor": (data.emissor or "").strip().casefold(),
        "taxa": str(data.taxa),
        "vencimento": data.data_vencimento.isoformat() if data.data_vencimento else "",
        "minimo": str(data.valor_minimo),
    }


def _expected_fields(e: dict) -> dict[str, str]:
    from decimal import Decimal

    def dec(v) -> str:
        return str(Decimal(str(v))) if v is not None else ""

    return {
        "tipo": str(e.get("tipo", "")).upper(),
        "emissor": str(e.get("emissor", "")).strip().casefold(),
        "taxa": dec(e.get("taxa")),
        "vencimento": str(e.get("vencimento", "")),
        "minimo": dec(e.get("valor_minimo")),
    }


def compare(expected: list[dict], created: list) -> dict[str, tuple[int, int]]:
    """Acertos por campo: pareia por ordem; oferta que faltou conta como erro. Devolve {campo: (acertos, total)}."""
    result = {f: [0, 0] for f in FIELDS}
    for i, e in enumerate(expected):
        want = _expected_fields(e)
        got = actual_fields(created[i]) if i < len(created) else None
        for f in FIELDS:
            result[f][1] += 1
            if got is not None and got[f] == want[f]:
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
        created = []
        for offer in raw.ofertas:
            r = interpret_offer(offer, raw.plataforma, settings, today)
            created.extend([r.data] if isinstance(r, Created) else [])
        print(f"   {len(raw.ofertas)} ofertas lidas, {len(created)} interpretadas")
        exp_file = img.with_name(f"{img.stem}.esperado.json")
        if not exp_file.is_file():
            continue
        res = compare(json.loads(exp_file.read_text(encoding="utf-8")), created)
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
