import calendar
import re
import unicodedata
from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal

from app.data.tesouro import TesouroQuote
from app.domain.calendar import BusinessCalendar
from app.domain.indexes import ProjecaoIndisponivel, daily_unit
from app.domain.products.accrual import needs_index
from app.domain.products.base import (
    Alert,
    AlertCode,
    Coverage,
    Indexer,
    Liquidity,
    Product,
    ProductData,
    ProductType,
    Section,
    SeriePoint,
    SimContext,
    SimulationResult,
    brl,
)
from app.domain.taxes import apply_taxes

TIPO_MAP: dict[str, ProductType] = {
    "Tesouro Selic": ProductType.TESOURO_SELIC,
    "Tesouro Prefixado": ProductType.TESOURO_PREFIXADO,
    "Tesouro Prefixado com Juros Semestrais": ProductType.TESOURO_PREFIXADO_JUROS,
    "Tesouro IPCA+": ProductType.TESOURO_IPCA,
    "Tesouro IPCA+ com Juros Semestrais": ProductType.TESOURO_IPCA_JUROS,
    "Tesouro Renda+ Aposentadoria Extra": ProductType.TESOURO_RENDA_MAIS,
    "Tesouro Educa+": ProductType.TESOURO_EDUCA_MAIS,
}

_FACE = Decimal(1000)
_ONE = Decimal(1)
_HALF = Decimal("0.5")
_CENT = Decimal("0.01")
_INSTALLMENTS = {ProductType.TESOURO_RENDA_MAIS: 240, ProductType.TESOURO_EDUCA_MAIS: 60}
_COUPON_BASE = {
    ProductType.TESOURO_PREFIXADO_JUROS: Decimal("1.10"),
    ProductType.TESOURO_IPCA_JUROS: Decimal("1.06"),
}
_PRE = {ProductType.TESOURO_PREFIXADO, ProductType.TESOURO_PREFIXADO_JUROS}

Flow = tuple[date, Decimal]


def _slug(tipo: str) -> str:
    text = unicodedata.normalize("NFKD", tipo.removeprefix("Tesouro ").replace("+", " mais "))
    text = text.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _months_back(d: date, months: int) -> date:
    total = d.year * 12 + (d.month - 1) - months
    year, month = divmod(total, 12)
    return date(year, month + 1, min(d.day, calendar.monthrange(year, month + 1)[1]))


def cash_flow_dates(venc: date, months_step: int, after: date, limit: int | None = None) -> list[date]:
    """Datas a cada `months_step` meses, para trás a partir do vencimento, estritamente > `after`."""
    dates: list[date] = []
    k = 0
    while limit is None or k < limit:
        d = _months_back(venc, k * months_step)
        if d <= after:
            break
        dates.append(d)
        k += 1
    return sorted(dates)


def flows(tipo: ProductType, venc: date, after: date) -> list[Flow]:
    """Fluxos em unidades de valor de face/VNA."""
    n = _INSTALLMENTS.get(tipo)
    if n is not None:
        return [(d, _ONE / n) for d in cash_flow_dates(venc, 1, after, limit=n)]
    base = _COUPON_BASE.get(tipo)
    if base is None:
        return [(venc, _ONE)] if venc > after else []
    coupon = base**_HALF - _ONE
    return [(d, coupon + (_ONE if d == venc else 0)) for d in cash_flow_dates(venc, 6, after)]


def pv_factor(fluxos: list[Flow], rate: Decimal, ref: date, cal: BusinessCalendar) -> Decimal:
    total = Decimal(0)
    v = _ONE / daily_unit(rate)
    for d, f in fluxos:
        # du até a data nominal (sem adjust_next): é a convenção que reproduz o PU publicado
        du = cal.business_days_between(ref, d)
        total += f * v**du
    return total


def build_treasury(q: TesouroQuote) -> "TreasuryProduct":
    tipo = TIPO_MAP[q.tipo]
    if tipo in _PRE:
        indexador, taxa = Indexer.PRE, q.taxa_compra
    elif tipo == ProductType.TESOURO_SELIC:
        indexador, taxa = Indexer.SELIC, q.taxa_compra
    else:
        indexador, taxa = Indexer.IPCA_MAIS, q.taxa_compra
    data = ProductData(
        id=f"tesouro-{_slug(q.tipo)}-{q.vencimento.isoformat()}",
        tipo=tipo,
        nome=f"{q.tipo} {q.vencimento.year}",
        emissor="Tesouro Nacional",
        plataforma="Tesouro Direto",
        indexador=indexador,
        taxa=taxa,
        data_vencimento=q.vencimento,
        valor_minimo=max(Decimal(30), Decimal("0.01") * q.pu_compra),
        liquidez=Liquidity.DIARIA,
        cobertura=Coverage.TESOURO,
    )
    return TreasuryProduct(data, q)


class TreasuryProduct(Product):
    def __init__(self, data: ProductData, quote: TesouroQuote) -> None:
        super().__init__(data)
        self.quote = quote

    def simulate(self, valor: Decimal, data_alvo: date, ctx: SimContext) -> SimulationResult:
        d = self.data
        if d.data_vencimento is None:
            raise ValueError("título do Tesouro exige data_vencimento")
        if valor < d.valor_minimo:
            return self._unavailable(
                valor, AlertCode.ABAIXO_MINIMO, f"Valor abaixo do mínimo de {brl(d.valor_minimo)}", ctx
            )
        sem_dados = "Sem dados de mercado para calcular"
        if needs_index(d.indexador) and ctx.index is None:
            return self._unavailable(valor, AlertCode.SEM_DADOS_MERCADO, sem_dados, ctx)
        if not flows(d.tipo, d.data_vencimento, ctx.today):
            return self._unavailable(
                valor, AlertCode.SEM_DADOS_MERCADO, "Título vencido ou sem fluxos futuros", ctx
            )
        try:
            return self._simulate(valor, data_alvo, ctx)
        except ProjecaoIndisponivel:
            return self._unavailable(valor, AlertCode.SEM_DADOS_MERCADO, sem_dados, ctx)

    def _simulate(self, valor: Decimal, data_alvo: date, ctx: SimContext) -> SimulationResult:
        d, q = self.data, self.quote
        tipo, cal, today, settings = d.tipo, ctx.cal, ctx.today, ctx.settings
        venc = cal.adjust_next(d.data_vencimento)
        maturity = venc <= data_alvo
        saida = venc if maturity else data_alvo
        extra: list[Alert] = []
        dias_parado = 0
        if maturity:
            secao = Section.VENCE_ATE_DATA
            dias_parado = (data_alvo - venc).days
            if dias_parado > 0:
                extra.append(
                    Alert(
                        code=AlertCode.PARADO,
                        message=f"Dinheiro parado por {dias_parado} dias após o vencimento",
                    )
                )
        else:
            secao = Section.VENCE_DEPOIS
            extra.append(
                Alert(
                    code=AlertCode.ESTIMATIVA_MERCADO,
                    message="Estimativa de venda antecipada a preço de mercado — pode variar",
                )
            )
        if tipo in _INSTALLMENTS:
            extra.append(
                Alert(code=AlertCode.MODELO_SIMPLIFICADO, message="Modelo simplificado de Renda+/Educa+")
            )

        qtd = (valor / q.pu_compra).quantize(_CENT, rounding=ROUND_DOWN)
        investido = qtd * q.pu_compra
        all_flows = flows(tipo, d.data_vencimento, today)
        pay_date = {fd: cal.adjust_next(fd) for fd, _ in all_flows}
        pontos = self._series_dates(today, saida, cal)
        face = self._face_function(
            [pay_date[fd] for fd, _ in all_flows if pay_date[fd] <= saida] + pontos, all_flows, ctx
        )

        principal = _ONE if tipo not in _INSTALLMENTS else Decimal(0)
        last_flow_date = all_flows[-1][0] if all_flows else None
        received: list[tuple[date, Decimal, Decimal]] = []  # (pagamento, valor bruto, fração f)
        for fd, f in all_flows:
            pay = pay_date[fd]
            if pay > saida:
                continue
            part = f - principal if (maturity and fd == last_flow_date) else f
            if part > 0:
                received.append((pay, qtd * face(pay) * part, part))

        if maturity:
            exit_value = qtd * face(venc) * principal
        else:
            remaining = [(fd, f) for fd, f in all_flows if pay_date[fd] > saida]
            exit_value = qtd * face(saida) * pv_factor(remaining, q.taxa_venda, saida, cal)

        # Renda+/Educa+: custo rateado entre as parcelas; cupons de NTN-F/NTN-B são tributados cheios.
        total_f = sum((f for _, f in all_flows), Decimal(0))
        iof = ir = Decimal(0)
        basis_received = Decimal(0)
        for pay, amount, f in received:
            basis = investido * f / total_f if tipo in _INSTALLMENTS else Decimal(0)
            basis_received += basis
            t = apply_taxes(max(Decimal(0), amount - basis), (pay - today).days, d.tipo, settings)
            iof += t.iof
            ir += t.ir
        exit_cost = investido - basis_received if tipo in _INSTALLMENTS else investido
        t = apply_taxes(exit_value - exit_cost, (saida - today).days, d.tipo, settings)
        iof += t.iof
        ir += t.ir

        bruto = exit_value + sum((a for _, a, _ in received), Decimal(0))
        base = (investido + exit_value) / 2
        if tipo == ProductType.TESOURO_SELIC:
            base = max(Decimal(0), base - settings.tesouro_selic_isencao_custodia)
        custodia = (
            settings.custodia_b3_aa * base * Decimal((saida - today).days) / 365
        ).quantize(_CENT, rounding=ROUND_HALF_EVEN)
        liquido = bruto - iof - ir - custodia

        serie: list[SeriePoint] = []
        for p in pontos[:-1]:
            restantes = [(fd, f) for fd, f in all_flows if pay_date[fd] > p]
            posicao = qtd * face(p) * pv_factor(restantes, q.taxa_compra, p, cal)
            recebido = sum((a for pay, a, _ in received if pay <= p), Decimal(0))
            serie.append(SeriePoint(data=p, valor_bruto=posicao + recebido))
        serie.append(SeriePoint(data=saida, valor_bruto=bruto))

        return SimulationResult(
            product=d,
            secao=secao,
            resgatavel=True,
            estimativa_mercado=not maturity,
            data_saida=saida,
            dias_parado=dias_parado,
            valor_investido=investido,
            valor_bruto=bruto,
            iof=iof,
            ir=ir,
            custodia=custodia,
            valor_liquido=liquido,
            rentab_liquida=liquido / investido - 1,
            taxa_liquida_aa=self._net_annual_rate(investido, liquido, today, saida, cal),
            alertas=self._common_alerts(valor, ctx) + extra,
            serie=serie,
        )

    def _face_function(self, dates: list[date], all_flows: list[Flow], ctx: SimContext):
        """Valor de face (1000 para pré) ou VNA projetado em cada data pedida."""
        if self.data.indexador == Indexer.PRE:
            return lambda _t: _FACE
        index = ctx.index
        if index is None:
            raise ProjecaoIndisponivel("sem dados de mercado")
        factor = index.selic_factor if self.data.indexador == Indexer.SELIC else index.ipca_factor
        vna_hoje = self.quote.pu_compra / pv_factor(
            all_flows, self.quote.taxa_compra, ctx.today, ctx.cal
        )
        table: dict[date, Decimal] = {ctx.today: vna_hoje}
        prev, acc = ctx.today, vna_hoje
        for t in sorted(set(dates)):
            if t > prev:
                acc *= factor(prev, t)
                prev = t
            table[t] = acc
        return table.__getitem__
