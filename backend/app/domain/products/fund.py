from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

from app.domain.calendar import BusinessCalendar
from app.domain.indexes import ProjecaoIndisponivel
from app.domain.products.accrual import needs_index
from app.domain.products.base import (
    Alert,
    AlertCode,
    Indexer,
    Product,
    ProductType,
    SeriePoint,
    Section,
    SimContext,
    SimulationResult,
    brl,
)
from app.domain.taxes import apply_taxes

_ONE = Decimal(1)
_CENT = Decimal("0.01")
_DAYS_YEAR = Decimal(252)


def come_cotas_dates(cal: BusinessCalendar, start: date, end: date) -> list[date]:
    """Último dia útil de maio e novembro em (start, end]."""
    datas: list[date] = []
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        if m in (5, 11):
            eom = cal.last_business_day_of_month(y, m)
            if start < eom <= end:
                datas.append(eom)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return datas


class FundoRendaFixa(Product):
    def simulate(self, valor: Decimal, data_alvo: date, ctx: SimContext) -> SimulationResult:
        d = self.data
        if valor < d.valor_minimo:
            return self._unavailable(
                valor, AlertCode.ABAIXO_MINIMO, f"Valor abaixo do mínimo de {brl(d.valor_minimo)}", ctx
            )
        if needs_index(d.indexador) and ctx.index is None:
            return self._unavailable(
                valor, AlertCode.SEM_DADOS_MERCADO, "Sem dados de mercado para calcular", ctx
            )

        today = ctx.today
        prazo = d.prazo_resgate_dias or 0
        solicitacao = data_alvo - timedelta(days=prazo)
        if solicitacao < today:
            return SimulationResult(
                product=d,
                secao=Section.VENCE_DEPOIS,
                resgatavel=False,
                valor_investido=valor,
                alertas=self._common_alerts(valor, ctx, projecao=False)
                + [
                    Alert(
                        code=AlertCode.RESGATE_DN,
                        message=f"Resgate leva D+{prazo} — o dinheiro não chega até a sua data",
                    )
                ],
            )
        taxa_adm = d.taxa_adm or Decimal(0)
        aliquota_cc = (
            ctx.settings.come_cotas_curto
            if d.classe_tributaria == "CURTO"
            else ctx.settings.come_cotas_longo
        )
        bruto, cc_pago, serie = self._accumulate(valor, data_alvo, taxa_adm, aliquota_cc, ctx)
        sem_taxa = (
            self._accumulate(valor, data_alvo, Decimal(0), aliquota_cc, ctx)[0]
            if taxa_adm
            else bruto
        )

        ganho_total = bruto + cc_pago - valor
        taxes = apply_taxes(
            ganho_total, (data_alvo - today).days, ProductType.FUNDO_RF, ctx.settings,
            curto_prazo=d.classe_tributaria == "CURTO",
        )
        ir = max(Decimal(0), taxes.ir - cc_pago)
        liquido = bruto - taxes.iof - ir

        alertas = self._common_alerts(valor, ctx) + [
            Alert(
                code=AlertCode.FUNDO_SEM_GARANTIA,
                message="Fundo sem rentabilidade garantida — rentabilidade-alvo estimada",
            )
        ]
        if prazo > 0:
            alertas.append(
                Alert(
                    code=AlertCode.RESGATE_DN,
                    message=f"Solicite o resgate até {solicitacao:%d/%m/%Y} (D+{prazo})",
                )
            )
        return SimulationResult(
            product=d,
            secao=Section.VENCE_ATE_DATA,
            resgatavel=True,
            data_saida=data_alvo,
            valor_investido=valor,
            valor_bruto=bruto,
            iof=taxes.iof,
            ir=ir,
            come_cotas=cc_pago,
            taxa_adm=sem_taxa - bruto,
            valor_liquido=liquido,
            rentab_liquida=liquido / valor - 1,
            taxa_liquida_aa=self._net_annual_rate(valor, liquido, today, data_alvo, ctx.cal),
            data_solicitacao_resgate=solicitacao,
            alertas=alertas,
            serie=serie,
        )

    def _accumulate(
        self, valor: Decimal, saida: date, taxa_adm: Decimal, aliquota_cc: Decimal, ctx: SimContext
    ) -> tuple[Decimal, Decimal, list[SeriePoint]]:
        """Valor bruto após come-cotas, come-cotas pago e série mensal."""
        d, index, cal = self.data, ctx.index, ctx.cal
        if index is None:
            raise ProjecaoIndisponivel("sem projeção de CDI")
        pct, spread = (d.taxa, Decimal(0)) if d.indexador == Indexer.PCT_CDI else (_ONE, d.taxa)
        fator_adm = (_ONE - taxa_adm) ** (_ONE / _DAYS_YEAR) if taxa_adm else _ONE
        cc_datas = set(come_cotas_dates(cal, ctx.today, saida))
        pontos = set(self._series_dates(ctx.today, saida, cal))

        value = base = valor
        cc_pago = Decimal(0)
        serie: list[SeriePoint] = []
        anterior = ctx.today
        for dia in cal.business_days(ctx.today, saida):
            value *= index.cdi_factor(anterior, dia, pct, spread) * fator_adm
            anterior = dia
            if dia in cc_datas:
                cc = (aliquota_cc * (value - base)).quantize(_CENT, rounding=ROUND_HALF_EVEN)
                if cc > 0:
                    value -= cc
                    cc_pago += cc
                base = value
            if dia in pontos and dia != saida:
                serie.append(SeriePoint(data=dia, valor_bruto=value))
        serie.append(SeriePoint(data=saida, valor_bruto=value))
        return value, cc_pago, serie
