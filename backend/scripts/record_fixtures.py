"""Grava as fixtures de mercado em tests/fixtures/market/ (rede; rodar manualmente).

Uso: cd backend && uv run python scripts/record_fixtures.py
"""

import sys
from datetime import date, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data.market import (  # noqa: E402
    FIXTURE_FILES,
    focus_url,
    sgs_url,
    TESOURO_URL,
)
from app.data.tesouro import decode_csv  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "market"


def fetch_focus(client: httpx.Client, resource: str, indicador: str, top: int) -> str:
    resp = client.get(focus_url(resource, indicador, top))
    resp.raise_for_status()
    return resp.text


def reduce_tesouro(csv_text: str, keep: int = 2) -> str:
    lines = csv_text.lstrip("﻿").splitlines()
    header, rows = lines[0], [ln for ln in lines[1:] if ln.strip()]
    base_col = header.split(";").index("Data Base")
    bases = {datetime.strptime(r.split(";")[base_col], "%d/%m/%Y") for r in rows}
    wanted = {d.strftime("%d/%m/%Y") for d in sorted(bases)[-keep:]}
    kept = [r for r in rows if r.split(";")[base_col] in wanted]
    return "\n".join([header, *kept]) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=90, follow_redirects=True) as client:
        for key, codigo in (("sgs_432", 432), ("sgs_13522", 13522)):
            resp = client.get(sgs_url(codigo, date.today()))
            resp.raise_for_status()
            (OUT / FIXTURE_FILES[key]).write_text(resp.text, encoding="utf-8")
        for key, resource, indicador, top in (
            ("focus_selic", "ExpectativasMercadoAnuais", "Selic", 100),
            ("focus_ipca", "ExpectativasMercadoAnuais", "IPCA", 100),
            ("focus_ipca_mensal", "ExpectativaMercadoMensais", "IPCA", 200),
        ):
            (OUT / FIXTURE_FILES[key]).write_text(
                fetch_focus(client, resource, indicador, top), encoding="utf-8"
            )
        resp = client.get(TESOURO_URL)
        resp.raise_for_status()
        (OUT / FIXTURE_FILES["tesouro"]).write_text(
            reduce_tesouro(decode_csv(resp.content)), encoding="utf-8"
        )
    for path in sorted(OUT.iterdir()):
        print(f"{path.name}: {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
