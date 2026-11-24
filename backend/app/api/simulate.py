from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError, model_validator
from pydantic_core import InitErrorDetails

from app.deps import Container, get_container
from app.domain.horizon import Horizonte, anos_a_frente
from app.domain.simulation import (
    SimulationResponse,
    build_market_summary,
    simulate_all,
    simulate_sem_data,
)
from app.domain.sources import ManualSource, TesouroSource

router = APIRouter()


class SimulationRequest(BaseModel):
    valor: Decimal
    data_alvo: date | None = None
    horizonte: Horizonte = Horizonte.DATA

    @model_validator(mode="before")
    @classmethod
    def _cliente_antigo_exige_data(cls, data: object) -> object:
        # Sem `horizonte` vale o contrato antigo, em que `data_alvo` era obrigatório.
        if isinstance(data, dict) and "horizonte" not in data and "data_alvo" not in data:
            campos = [c for c in ("valor", "data_alvo") if c not in data]
            erros = [InitErrorDetails(type="missing", loc=(c,), input=data) for c in campos]
            raise ValidationError.from_exception_data(cls.__name__, erros)
        return data


@router.post("/simulate", response_model=SimulationResponse)
def simulate(body: SimulationRequest, c: Container = Depends(get_container)) -> SimulationResponse:
    if body.valor <= 0:
        raise HTTPException(422, ["O valor deve ser maior que zero"])
    hoje = c.today_fn()
    if body.horizonte == Horizonte.DATA:
        if body.data_alvo is None:
            raise HTTPException(422, ["Informe a data de resgate"])
        if body.data_alvo <= hoje:
            raise HTTPException(422, ["A data de resgate deve ser posterior a hoje"])
    settings, snapshot = c.snapshot()
    ctx = c.context(settings, snapshot)
    with c.lock:
        products = [
            p for source in (ManualSource(c.products), TesouroSource()) for p in source.load(ctx, snapshot)
        ]
    data_alvo: date | None
    if body.horizonte == Horizonte.SEM_DATA:
        data_alvo = None
        ate, depois, indisp = simulate_sem_data(products, body.valor, ctx)
    else:
        if body.horizonte == Horizonte.DATA:
            data_alvo = body.data_alvo
        else:
            anos = 1 if body.horizonte == Horizonte.UM_ANO else 2
            data_alvo = anos_a_frente(hoje, anos, ctx.cal)
        assert data_alvo is not None
        ate, depois, indisp = simulate_all(products, body.valor, data_alvo, ctx)
    return SimulationResponse(
        horizonte=body.horizonte,
        data_alvo=data_alvo,
        vence_ate_data=ate,
        vence_depois=depois,
        indisponiveis=indisp,
        mercado=build_market_summary(snapshot, ctx),
    )
