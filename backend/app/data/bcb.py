import json
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class SgsPoint(BaseModel):
    data: date
    valor: Decimal  # percentual cru, como publicado pelo SGS


def parse_sgs(json_text: str) -> list[SgsPoint]:
    return [
        SgsPoint(
            data=datetime.strptime(row["data"], "%d/%m/%Y").date(),
            valor=Decimal(str(row["valor"])),
        )
        for row in json.loads(json_text)
    ]


def latest_until(points: list[SgsPoint], today: date) -> SgsPoint:
    """Último ponto com data <= today; se não houver, o último ponto."""
    if not points:
        raise ValueError("série SGS vazia")
    ordered = sorted(points, key=lambda p: p.data)
    valid = [p for p in ordered if p.data <= today]
    return valid[-1] if valid else ordered[-1]
