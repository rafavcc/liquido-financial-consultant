from datetime import date
from decimal import Decimal

from app.domain.indexes import ProjecaoIndisponivel
from app.domain.products.accrual import accrual_factor, needs_index
from app.domain.products.base import (
    Alert,
    AlertCode,
    Liquidity,
    Product,
    SeriePoint,
    Section,
    SimContext,
    SimulationResult,
    brl,
)
from app.domain.taxes import apply_taxes


class BankProduct(Product):
    def simulate(self, valor: Decimal, data_alvo: date, ctx: SimContext) -> SimulationResult:
        d = self.data
        if d.data_vencimento is None:
            raise ValueError("produto bancário exige data_vencimento")
        if valor < d.valor_minimo:
            return self._unavailable(
                valor, AlertCode.ABAIXO_MINIMO, f"Valor abaixo do mínimo de {brl(d.valor_minimo)}", ctx
            )
        sem_dados = "Sem dados de mercado para calcular"
        if needs_index(d.indexador) and ctx.index is None:
            return self._unavailable(valor, AlertCode.SEM_DADOS_MERCADO, sem_dados, ctx)

        today = ctx.today
        venc = ctx.cal.adjust_next(d.data_vencimento)
        dias_parado = 0
        extra: list[Alert] = []
        if venc <= data_alvo:
            secao = Section.VENCE_ATE_DATA
            saida = venc
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
            resgatavel = d.liquidez == Liquidity.DIARIA or (
                d.liquidez == Liquidity.DIARIA_APOS_CARENCIA
                and d.data_carencia is not None
                and data_alvo >= d.data_carencia
            )
            if not resgatavel:
                alertas = self._common_alerts(valor, ctx, projecao=False) + [
                    Alert(
                        code=AlertCode.NAO_RESGATAVEL,
                        message="Sem liquidez antes do vencimento — não resgatável na sua data",
                    )
                ]
                return SimulationResult(
                    product=d,
                    secao=secao,
                    resgatavel=False,
                    valor_investido=valor,
                    alertas=alertas,
                )
            saida = data_alvo

        try:
            fator = accrual_factor(d.indexador, d.taxa, today, saida, ctx)
            fatores = self._cumulative_factors(saida, ctx)
        except ProjecaoIndisponivel:
            return self._unavailable(valor, AlertCode.SEM_DADOS_MERCADO, sem_dados, ctx)

        bruto = valor * fator
        serie = [SeriePoint(data=p, valor_bruto=valor * f) for p, f in fatores]
        serie[-1] = SeriePoint(data=saida, valor_bruto=bruto)  # sem deriva de arredondamento
        taxes = apply_taxes(bruto - valor, (saida - today).days, d.tipo, ctx.settings)
        liquido = bruto - taxes.iof - taxes.ir
        return SimulationResult(
            product=d,
            secao=secao,
            resgatavel=True,
            data_saida=saida,
            dias_parado=dias_parado,
            valor_investido=valor,
            valor_bruto=bruto,
            iof=taxes.iof,
            ir=taxes.ir,
            valor_liquido=liquido,
            rentab_liquida=liquido / valor - 1,
            taxa_liquida_aa=self._net_annual_rate(valor, liquido, today, saida, ctx.cal),
            alertas=self._common_alerts(valor, ctx) + extra,
            serie=serie,
        )

    def _cumulative_factors(self, saida: date, ctx: SimContext) -> list[tuple[date, Decimal]]:
        d = self.data
        pontos: list[date] = []
        y, m = ctx.today.year, ctx.today.month
        while True:
            eom = ctx.cal.last_business_day_of_month(y, m)
            if eom >= saida:
                break
            if eom > ctx.today:
                pontos.append(eom)
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        pontos.append(saida)

        fatores: list[tuple[date, Decimal]] = []
        anterior, acumulado = ctx.today, Decimal(1)
        for p in pontos:
            acumulado *= accrual_factor(d.indexador, d.taxa, anterior, p, ctx)
            fatores.append((p, acumulado))
            anterior = p
        return fatores


class CDB(BankProduct):
    pass


class LCI(BankProduct):
    pass


class LCA(BankProduct):
    pass


class CRI(BankProduct):
    pass


class CRA(BankProduct):
    pass
