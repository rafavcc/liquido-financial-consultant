from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import Container, get_container
from app.domain.simulation import SimulationResponse, build_market_summary, simulate_all
from app.domain.sources import ManualSource, TesouroSource

router = APIRouter()


class SimulationRequest(BaseModel):
    valor: Decimal
    data_alvo: date


@router.post("/simulate", response_model=SimulationResponse)
def simulate(body: SimulationRequest, c: Container = Depends(get_container)) -> SimulationResponse:
    if body.valor <= 0:
        raise HTTPException(422, ["O valor deve ser maior que zero"])
    if body.data_alvo <= c.today_fn():
        raise HTTPException(422, ["A data de resgate deve ser posterior a hoje"])
    settings, snapshot = c.snapshot()
    ctx = c.context(settings, snapshot)
    with c.lock:
        products = [
            p for source in (ManualSource(c.products), TesouroSource()) for p in source.load(ctx, snapshot)
        ]
    ate, depois, indisp = simulate_all(products, body.valor, body.data_alvo, ctx)
    return SimulationResponse(
        vence_ate_data=ate,
        vence_depois=depois,
        indisponiveis=indisp,
        mercado=build_market_summary(snapshot, ctx),
    )
