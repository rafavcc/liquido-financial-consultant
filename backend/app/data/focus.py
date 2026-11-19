import json
from datetime import date
from decimal import Decimal


def _latest_rows(json_text: str) -> tuple[date, list[dict]]:
    rows = json.loads(json_text)["value"]
    if not rows:
        raise ValueError("Focus sem registros")
    latest = max(r["Data"] for r in rows)
    return date.fromisoformat(latest), [r for r in rows if r["Data"] == latest]


def _fraction(mediana) -> Decimal:
    return Decimal(str(mediana)) / 100


def parse_annual(json_text: str) -> tuple[date, dict[int, Decimal]]:
    data, rows = _latest_rows(json_text)
    return data, {int(r["DataReferencia"]): _fraction(r["Mediana"]) for r in rows}


def parse_monthly(json_text: str) -> tuple[date, dict[str, Decimal]]:
    data, rows = _latest_rows(json_text)
    out: dict[str, Decimal] = {}
    for r in rows:
        month, year = r["DataReferencia"].split("/")
        out[f"{year}-{month}"] = _fraction(r["Mediana"])
    return data, out
