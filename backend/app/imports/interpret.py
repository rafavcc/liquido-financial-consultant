"""Interpretação determinística de uma oferta lida do print (spec §6.4). Sem rede, banco ou LLM."""

from __future__ import annotations

import re
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
    plain,
)
from app.imports.schema import RawExtraction, RawOffer
from app.imports.selection import RateAmbiguous, choose_rate

PLATAFORMAS = {"XP": "XP", "BTG": "BTG", "NUBANK": "Nubank"}
_SUPPORTED = {
    ProductType.CDB, ProductType.LCI, ProductType.LCA, ProductType.LCD,
    ProductType.CRI, ProductType.CRA,
}
# Pistas inequívocas de cada plataforma (texto sem acento, minúsculo), vindas dos prints reais.
_PISTAS = {
    "NUBANK": ("ultravioleta", "nubank", "nu invest"),
    "BTG": ("taxa eq. do cdb", "taxa eq. cdb", "produto e risco", "estoque", "btg pactual digital", "cra/cri/cdca"),
    "XP": ("quantidade disponivel", "liquidez xp", "rentabilidade (a.a)", "xp investimentos", "saiba mais"),
}
# Nome do produto: "LCA ORIGINAL - ABR/2030", "CDB BTG PACTUAL - ABR/203...", "CRI - AUTOMOB".
_NOME_EMISSOR = re.compile(
    r"^(?:CDB|LCI|LCA|LCD|CRI|CRA)\b\s*-?\s*(?P<emissor>.+?)\s*(?:-\s*[A-Za-zÇç]{3}/\d{0,4}\s*)?(?:\.\.\.|…)?$",
    re.IGNORECASE,
)
_SUFIXO_MES = re.compile(r"\s*-\s*[A-Za-zÇç]{3}/\d{2,4}\s*$")
_NOME_GENERICO = {"pos-fixado", "pos fixado", "prefixado", "pre-fixado", "ipca", "inflacao", "hibrido", "ultravioleta"}
_TRIVIAL = {"", "-", "—", "–", "no vencimento", "nao ha", "n/a"}


@dataclass
class Created:
    data: ProductData
    minimo_desconhecido: bool = False  # valor_minimo=0 é só preenchimento: não vale como mínimo real


@dataclass
class Ignored:
    motivo: str


@dataclass
class Failed:
    erros: list[str]
    parcial: dict


_NO_DAILY = {ProductType.LCI, ProductType.LCA, ProductType.LCD}


def resolve_platform(ext: RawExtraction) -> str:
    """A plataforma que o modelo deu; se ele não soube, a única cujas pistas aparecem nos indícios."""
    if ext.plataforma.strip().upper() in PLATAFORMAS:
        return ext.plataforma.strip().upper()
    texto = " ".join(plain(i) for i in ext.indicios)
    achadas = {p for p, pistas in _PISTAS.items() if any(x in texto for x in pistas)}
    return achadas.pop() if len(achadas) == 1 else "DESCONHECIDA"


def _issuer_from_name(nome: str | None) -> str | None:
    m = _NOME_EMISSOR.match((nome or "").strip())
    if not m:
        return None
    emissor = m.group("emissor").strip(" -")
    return None if not emissor or plain(emissor) in _NOME_GENERICO else emissor


def _liquidity(texto: str | None) -> tuple[Liquidity, str | None]:
    t = re.sub(r"[\s_]+", " ", plain(texto))
    if t == "diaria":
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
    if raw.cortada and (not raw.taxas or not (raw.vencimento or "").strip()):
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

    emissor = _SUFIXO_MES.sub("", (raw.emissor or "").strip())
    if not emissor and (emissor := _issuer_from_name(raw.nome_exibido) or ""):
        notas.append(f"Importado: emissor tirado do nome ({raw.nome_exibido})")
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
    if liquidez == Liquidity.DIARIA and tipo in _NO_DAILY:
        liquidez = Liquidity.NO_VENCIMENTO
        notas.append(f"Importado: {tipo.value} não tem liquidez diária, assumi no vencimento")

    carencia = None
    if plain(raw.carencia) not in _TRIVIAL:
        try:
            carencia = parse_carencia(raw.carencia, today)
        except ValueError:
            erros.append(f"Carência não reconhecida: {raw.carencia}")

    minimo = parse_money(raw.aplicacao_minima) if raw.aplicacao_minima else None
    minimo_desconhecido = minimo is None
    if minimo is None:
        minimo = Decimal(0)
        if (raw.aplicacao_minima or "").strip():
            notas.append(f"Importado: mínimo não reconhecido ({raw.aplicacao_minima.strip()})")
        else:
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
    if (raw.juros or "").strip() and (juros or plain(raw.juros) not in _TRIVIAL):
        notas.append(f"Juros: {raw.juros.strip()}")
    if (raw.amortizacao or "").strip() and (amortizacao or plain(raw.amortizacao) not in _TRIVIAL):
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
    return Created(data=data, minimo_desconhecido=minimo_desconhecido)
