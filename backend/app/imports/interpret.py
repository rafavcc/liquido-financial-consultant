"""Interpretação determinística de uma oferta lida do print (spec §6.4). Sem rede, banco ou LLM."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.products.base import Liquidity, ProductData, ProductType
from app.domain.products.validation import validate_product
from app.domain.settings import Settings
from app.imports.parsing import (
    parse_amortizacao,
    parse_carencia,
    parse_date,
    parse_money,
    parse_periodicidade,
)
from app.imports.schema import RawOffer
from app.imports.selection import RateAmbiguous, choose_rate

PLATAFORMAS = {"XP": "XP", "BTG": "BTG", "NUBANK": "Nubank"}
_SUPPORTED = {
    ProductType.CDB, ProductType.LCI, ProductType.LCA, ProductType.LCD,
    ProductType.CRI, ProductType.CRA,
}
_TRIVIAL = {"", "-", "no vencimento", "nao ha", "n/a"}


@dataclass
class Created:
    data: ProductData


@dataclass
class Ignored:
    motivo: str


@dataclass
class Failed:
    erros: list[str]
    parcial: dict


def _plain(texto: str | None) -> str:
    nfd = unicodedata.normalize("NFD", (texto or "").strip())
    return "".join(c for c in nfd if not unicodedata.combining(c)).lower()


def _liquidity(texto: str | None) -> tuple[Liquidity, str | None]:
    t = re.sub(r"[\s_]+", " ", _plain(texto))
    if t in ("diaria",):
        return Liquidity.DIARIA, None
    if t == "diaria apos carencia":
        return Liquidity.DIARIA_APOS_CARENCIA, None
    if t in ("no vencimento", "a mercado"):
        return Liquidity.NO_VENCIMENTO, None
    if t in ("", "desconhecida"):
        return Liquidity.NO_VENCIMENTO, "Importado: liquidez não visível no print, assumi no vencimento"
    return Liquidity.NO_VENCIMENTO, f"Importado: liquidez não reconhecida ({texto}), assumi no vencimento"


def interpret_offer(
    raw: RawOffer, plataforma: str, settings: Settings, today: date
) -> Created | Ignored | Failed:
    if raw.cortada:
        return Ignored("cortada")
    tipo_txt = raw.tipo.strip().upper()
    if tipo_txt.startswith("TESOURO"):
        return Ignored("tesouro")
    if tipo_txt == ProductType.FUNDO_RF.value:
        return Ignored("fundo")
    try:
        tipo = ProductType(tipo_txt)
    except ValueError:
        return Ignored(f"tipo não suportado: {tipo_txt}")
    if tipo not in _SUPPORTED:
        return Ignored(f"tipo não suportado: {tipo_txt}")

    erros: list[str] = []
    notas: list[str] = []
    parcial: dict = {"raw": raw.model_dump(mode="json"), "interpretado": {"tipo": tipo.value}}
    interp = parcial["interpretado"]

    plat = PLATAFORMAS.get(plataforma.strip().upper())
    if plat is None:
        erros.append("Plataforma não identificada")
    else:
        interp["plataforma"] = plat

    emissor = (raw.emissor or "").strip()
    if not emissor:
        erros.append("Emissor não visível")
    else:
        interp["emissor"] = emissor

    venc = None
    if not (raw.vencimento or "").strip():
        erros.append("Vencimento não visível")
    else:
        venc = parse_date(raw.vencimento)
        if venc is None:
            erros.append(f"Data sem dia: {raw.vencimento}")
        else:
            interp["data_vencimento"] = venc.isoformat()

    choice = choose_rate(raw.taxas, tipo, venc, settings, today)
    indexador = taxa = None
    if isinstance(choice, RateAmbiguous):
        detalhe = "; ".join(choice.textos) or "nenhuma taxa reconhecida"
        erros.append(f"Taxa ambígua: {detalhe}")
    else:
        indexador, taxa = choice.indexador, choice.taxa
        interp.update(indexador=indexador.value, taxa=str(taxa))
        notas.extend(f"Importado: ignorei {i}" for i in choice.ignoradas)

    liquidez, nota_liq = _liquidity(raw.liquidez)
    if nota_liq:
        notas.append(nota_liq)

    carencia = None
    if (raw.carencia or "").strip():
        try:
            carencia = parse_carencia(raw.carencia, today)
        except ValueError:
            erros.append(f"Carência não reconhecida: {raw.carencia}")

    minimo = parse_money(raw.aplicacao_minima) if raw.aplicacao_minima else None
    if minimo is None:
        minimo = Decimal(0)
        notas.append("Importado: mínimo não visível no print")

    disponivel_ate = None
    if (raw.disponivel_ate or "").strip():
        disponivel_ate = parse_date(raw.disponivel_ate)
        if disponivel_ate is None:
            notas.append(f"Importado: prazo da oferta não reconhecido ({raw.disponivel_ate})")

    juros = parse_periodicidade(raw.juros)
    amortizacao = parse_amortizacao(raw.amortizacao)
    if (raw.codigo or "").strip():
        notas.append(f"Código: {raw.codigo.strip()}")
    if (raw.juros or "").strip() and (juros or _plain(raw.juros) not in _TRIVIAL):
        notas.append(f"Juros: {raw.juros.strip()}")
    if (raw.amortizacao or "").strip() and (amortizacao or _plain(raw.amortizacao) not in _TRIVIAL):
        notas.append(f"Amortização: {raw.amortizacao.strip()}")

    if erros:
        return Failed(erros=erros, parcial=parcial)

    data = ProductData(
        tipo=tipo,
        nome=(raw.nome_exibido or "").strip() or f"{tipo.value} {emissor}",
        emissor=emissor,
        plataforma=plat,
        indexador=indexador,
        taxa=taxa,
        data_vencimento=venc,
        valor_minimo=minimo,
        liquidez=liquidez,
        data_carencia=carencia,
        observacoes="\n".join(notas),
        data_registro=today,
        disponivel_ate=disponivel_ate,
        origem="IA",
        juros_periodicos=juros,
        amortizacao=amortizacao,
    )
    erros = validate_product(data, settings, today)
    if erros:
        parcial["interpretado"] = data.model_dump(mode="json")
        return Failed(erros=erros, parcial=parcial)
    return Created(data=data)
