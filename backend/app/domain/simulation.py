import logging
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.data.market import MarketSnapshot
from app.domain.horizon import Horizonte, horizonte_natural, prazo_saida_dias
from app.domain.products.base import AlertCode, Product, Section, SimContext, SimulationResult

log = logging.getLogger(__name__)

_ZERO = Decimal(0)


class ProjecaoRow(BaseModel):
    ano: int
    selic: Decimal
    ipca: Decimal


class MarketSummary(BaseModel):
    selic_meta: Decimal | None
    selic_meta_data: date | None = None
    cdi_aa: Decimal | None
    ipca_12m: Decimal | None
    ipca_12m_ref: date | None
    fonte_projecao: str | None
    projecao: list[ProjecaoRow]
    fetched_at: dict[str, datetime]
    errors: dict[str, str]
    tesouro_data_base: date | None


class SimulationResponse(BaseModel):
    horizonte: Horizonte
    data_alvo: date | None
    vence_ate_data: list[SimulationResult]
    vence_depois: list[SimulationResult]
    indisponiveis: list[SimulationResult]
    mercado: MarketSummary


def _safe_simulate(product: Product, valor: Decimal, data_alvo: date, ctx: SimContext) -> SimulationResult:
    try:
        return product.simulate(valor, data_alvo, ctx)
    except Exception:  # noqa: BLE001 - um produto com erro não derruba os demais
        log.exception("Erro ao simular o produto %s", product.data.id)
        return Product._unavailable(product, valor, AlertCode.ERRO_CALCULO, "Erro ao calcular este produto", ctx)


def _safe_simulate_natural(product: Product, valor: Decimal, ctx: SimContext) -> SimulationResult:
    try:
        data_alvo = horizonte_natural(product.data, ctx.today, ctx.cal)
        return product.simulate(valor, data_alvo, ctx)
    except Exception:  # noqa: BLE001 - um produto com erro não derruba os demais
        log.exception("Erro ao simular o produto %s", product.data.id)
        return Product._unavailable(product, valor, AlertCode.ERRO_CALCULO, "Erro ao calcular este produto", ctx)


def _com_prazo(result: SimulationResult, ctx: SimContext) -> SimulationResult:
    if result.secao != Section.INDISPONIVEL:
        result.prazo_saida_dias = prazo_saida_dias(result.product, ctx.today, ctx.cal)
    return result


def simulate_all(
    products: list[Product], valor: Decimal, data_alvo: date, ctx: SimContext
) -> tuple[list[SimulationResult], list[SimulationResult], list[SimulationResult]]:
    results = [_com_prazo(_safe_simulate(p, valor, data_alvo, ctx), ctx) for p in products]
    ate = [r for r in results if r.secao == Section.VENCE_ATE_DATA]
    depois = [r for r in results if r.secao == Section.VENCE_DEPOIS]
    indisp = [r for r in results if r.secao == Section.INDISPONIVEL]

    ate.sort(key=lambda r: (-(r.valor_liquido or _ZERO), -(r.taxa_liquida_aa or _ZERO)))
    resgataveis = sorted(
        (r for r in depois if r.resgatavel), key=lambda r: -(r.valor_liquido or _ZERO)
    )
    nao_resgataveis = sorted(
        (r for r in depois if not r.resgatavel), key=lambda r: r.product.data_vencimento or date.max
    )
    indisp.sort(key=lambda r: r.product.nome)
    return ate, resgataveis + nao_resgataveis, indisp


def simulate_sem_data(
    products: list[Product], valor: Decimal, ctx: SimContext
) -> tuple[list[SimulationResult], list[SimulationResult], list[SimulationResult]]:
    """Simula cada produto até o seu horizonte natural; ordena por taxa líquida a.a."""
    results = [_com_prazo(_safe_simulate_natural(p, valor, ctx), ctx) for p in products]
    ate = [r for r in results if r.secao in (Section.VENCE_ATE_DATA, Section.VENCE_DEPOIS) and r.resgatavel]
    depois = [r for r in results if r.secao in (Section.VENCE_ATE_DATA, Section.VENCE_DEPOIS) and not r.resgatavel]
    indisp = [r for r in results if r.secao == Section.INDISPONIVEL]

    ate.sort(key=lambda r: (r.taxa_liquida_aa is None, -(r.taxa_liquida_aa or _ZERO), r.product.nome))
    depois.sort(key=lambda r: r.product.data_vencimento or date.max)
    indisp.sort(key=lambda r: r.product.nome)
    return ate, depois, indisp


def build_market_summary(snapshot: MarketSnapshot, ctx: SimContext) -> MarketSummary:
    index = ctx.index
    projecao: list[ProjecaoRow] = []
    if index is not None:
        try:
            projecao = [ProjecaoRow(ano=y, selic=s, ipca=i) for y, s, i in index.yearly_table()]
        except ValueError:  # sem dados de IPCA
            projecao = []
    selic = snapshot.selic_meta
    return MarketSummary(
        selic_meta=selic,
        selic_meta_data=snapshot.selic_meta_data,
        cdi_aa=None if selic is None else selic - ctx.settings.spread_cdi_selic,
        ipca_12m=snapshot.ipca_12m,
        ipca_12m_ref=snapshot.ipca_12m_ref,
        fonte_projecao=index.fonte if index is not None else None,
        projecao=projecao,
        fetched_at=snapshot.fetched_at,
        errors=snapshot.errors,
        tesouro_data_base=snapshot.tesouro_data_base,
    )
