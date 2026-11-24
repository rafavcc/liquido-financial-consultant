import json
from datetime import date
from decimal import Decimal as D
from pathlib import Path

from app.domain.products.base import Indexer, Liquidity, ProductType
from app.domain.settings import Settings
from app.imports.interpret import Created, Failed, Ignored, interpret_offer, resolve_platform
from app.imports.schema import EXTRACTION_JSON_SCHEMA, RawExtraction, RawOffer, RawRate

T = date(2026, 11, 23)
FIX = Path(__file__).parent.parent / "fixtures" / "imports"


def run(nome: str) -> list:
    ext = RawExtraction.model_validate(json.loads((FIX / f"{nome}.json").read_text("utf-8")))
    return [interpret_offer(o, ext.plataforma, Settings(), T) for o in ext.ofertas]


def raw_ok(**kw) -> RawOffer:
    base = dict(
        tipo="CDB", emissor="Banco X", taxas=[RawRate(rotulo="Taxa", texto="110% do CDI")],
        vencimento="23/11/2028", aplicacao_minima="R$ 1.000,00",
    )
    base.update(kw)
    return RawOffer(**base)


def test_schema_field_order_and_json_schema():
    assert list(RawRate.model_fields) == ["rotulo", "texto"]
    assert "ofertas" in EXTRACTION_JSON_SCHEMA["properties"]


def test_btg_lci():
    r = run("btg-app-lci-eq-cdb")
    assert [type(x) for x in r] == [Created, Created, Ignored]
    assert r[2].motivo == "cortada"
    d = r[0].data
    assert (d.tipo, d.taxa, d.plataforma, d.origem) == (ProductType.LCI, D("0.9"), "BTG", "IA")
    assert d.data_registro == T and d.valor_minimo == D("500.00")
    assert d.nome == "LCI Banco BTG Pactual"
    assert "108,46% do CDI (Taxa eq. CDB)" in d.observacoes


def test_xp_cdb_lista():
    r = run("xp-app-cdb-lista")
    assert [type(x) for x in r] == [Created, Created, Ignored]
    assert r[2].motivo == "cortada"
    assert r[0].data.taxa == D("1.025") and r[0].data.plataforma == "XP"


def test_xp_carteira_empty():
    assert run("xp-web-carteira-fundos") == []


def test_nubank_fundos_ignored():
    r = run("nubank-app-fundos")
    assert [x.motivo for x in r] == ["fundo", "tipo não suportado: OUTRO"]


def test_nubank_cdb():
    r = run("nubank-app-cdb-ultravioleta")
    assert all(isinstance(x, Created) for x in r)
    d = r[1].data
    assert (d.taxa, d.emissor, d.data_vencimento, d.plataforma) == (
        D("1.08"), "Cloudwalk Infinitepay", date(2028, 11, 18), "Nubank")
    assert d.nome == "CDB Ultravioleta"


def test_lcd():
    r = run("xp-web-tabela-lcd")
    assert all(isinstance(x, Created) for x in r)
    d = r[2].data
    assert (d.tipo, d.emissor, d.taxa, d.data_vencimento) == (
        ProductType.LCD, "BNDES", D("0.87"), date(2030, 3, 15))
    assert d.juros_periodicos is None and d.amortizacao is None


def test_cri_cra():
    r = run("btg-web-cri-cra-ipca")
    assert all(isinstance(x, Created) for x in r)
    d = r[0].data
    assert (d.tipo, d.indexador, d.taxa) == (ProductType.CRI, Indexer.IPCA_MAIS, D("0.1204"))
    assert d.juros_periodicos == "SEMESTRAL" and d.amortizacao is None
    assert "Código: 22L2288690" in d.observacoes.splitlines()
    assert r[1].data.amortizacao.inicio == date(2031, 6, 16)


def test_lca_six_months():
    r = run("btg-web-lca-eq-cdb-a")
    assert all(isinstance(x, Created) for x in r)
    assert any(x.data.taxa == D("0.88") and x.data.data_vencimento == date(2027, 5, 24) for x in r)


def test_missing_platform_fails():
    r = interpret_offer(raw_ok(), "DESCONHECIDA", Settings(), T)
    assert isinstance(r, Failed) and "Plataforma não identificada" in r.erros


def test_missing_fields_fail():
    r = interpret_offer(raw_ok(emissor=None, vencimento=None), "XP", Settings(), T)
    assert "Emissor não visível" in r.erros and "Vencimento não visível" in r.erros
    assert r.parcial["raw"]["tipo"] == "CDB"


def test_date_without_day_fails():
    r = interpret_offer(raw_ok(vencimento="mai/2028"), "XP", Settings(), T)
    assert "Data sem dia: mai/2028" in r.erros


def test_ambiguous_rate_fails():
    o = raw_ok(taxas=[RawRate(texto="95% do CDI"), RawRate(texto="99% do CDI")])
    r = interpret_offer(o, "XP", Settings(), T)
    assert any(e.startswith("Taxa ambígua: ") for e in r.erros)


def test_carencia_unrecognized_fails():
    o = raw_ok(liquidez="DIARIA_APOS_CARENCIA", carencia="após o 3º mês")
    r = interpret_offer(o, "XP", Settings(), T)
    assert "Carência não reconhecida: após o 3º mês" in r.erros


def test_carencia_ok():
    o = raw_ok(liquidez="DIARIA_APOS_CARENCIA", carencia="D+90")
    d = interpret_offer(o, "XP", Settings(), T).data
    assert d.liquidez == Liquidity.DIARIA_APOS_CARENCIA and d.data_carencia == date(2027, 2, 21)


def test_liquidity_defaults():
    d = interpret_offer(raw_ok(liquidez="DESCONHECIDA"), "XP", Settings(), T).data
    assert d.liquidez == Liquidity.NO_VENCIMENTO and "liquidez" in d.observacoes
    d = interpret_offer(raw_ok(liquidez="A mercado"), "XP", Settings(), T).data
    assert d.liquidez == Liquidity.NO_VENCIMENTO
    d = interpret_offer(raw_ok(liquidez="DIARIA"), "XP", Settings(), T).data
    assert d.liquidez == Liquidity.DIARIA


def test_missing_minimum_defaults_zero_with_note():
    d = interpret_offer(raw_ok(aplicacao_minima=None), "XP", Settings(), T).data
    assert d.valor_minimo == 0 and "mínimo não visível no print" in d.observacoes


def test_disponivel_ate():
    d = interpret_offer(raw_ok(disponivel_ate="28/11/2026"), "XP", Settings(), T).data
    assert d.disponivel_ate == date(2026, 11, 28)


def test_fund_and_tesouro_ignored():
    assert interpret_offer(raw_ok(tipo="FUNDO_RF"), "XP", Settings(), T).motivo == "fundo"
    assert interpret_offer(raw_ok(tipo="TESOURO_IPCA"), "XP", Settings(), T).motivo == "tesouro"
    assert interpret_offer(raw_ok(tipo="LF"), "XP", Settings(), T).motivo == "tipo não suportado: LF"


def test_validation_errors_become_failed():
    r = interpret_offer(raw_ok(tipo="LCI", vencimento="23/12/2026"), "XP", Settings(), T)
    assert isinstance(r, Failed) and any("prazo mínimo" in e for e in r.erros)
    r = interpret_offer(raw_ok(taxas=[RawRate(texto="300% do CDI")]), "XP", Settings(), T)
    assert any("plausível" in e for e in r.erros)


def test_daily_liquidity_on_credit_notes_becomes_at_maturity():
    """LCI/LCA/LCD não têm liquidez diária (prazo mínimo legal): o modelo às vezes inventa; assume no vencimento."""
    for tipo in ("LCI", "LCA", "LCD"):
        r = interpret_offer(raw_ok(tipo=tipo, liquidez="DIARIA", vencimento="23/11/2029"), "BTG", Settings(), T)
        assert isinstance(r, Created), r
        assert r.data.liquidez == Liquidity.NO_VENCIMENTO
        assert "liquidez diária" in r.data.observacoes


def test_cut_flag_ignored_when_rate_and_maturity_are_readable():
    """O modelo marca "cortada" quando só o nome termina em "..."; com taxa e vencimento, cadastra."""
    r = interpret_offer(raw_ok(cortada=True), "XP", Settings(), T)
    assert isinstance(r, Created)
    assert interpret_offer(raw_ok(cortada=True, vencimento=None), "XP", Settings(), T) == Ignored("cortada")
    assert interpret_offer(raw_ok(cortada=True, taxas=[]), "XP", Settings(), T) == Ignored("cortada")


def test_issuer_taken_from_offer_name_when_missing():
    casos = {
        "LCA ORIGINAL - ABR/2030": "ORIGINAL",
        "CDB BTG PACTUAL - ABR/203...": "BTG PACTUAL",
        "CRI - AUTOMOB": "AUTOMOB",
    }
    for nome, emissor in casos.items():
        tipo = nome.split()[0]
        r = interpret_offer(raw_ok(tipo=tipo, emissor=None, nome_exibido=nome, vencimento="23/11/2030"),
                            "XP", Settings(), T)
        assert isinstance(r, Created), (nome, r)
        assert r.data.emissor == emissor and "emissor" in r.data.observacoes
    # nome genérico não é emissor
    r = interpret_offer(raw_ok(tipo="LCI", emissor=None, nome_exibido="LCI - Pós-fixado"), "BTG", Settings(), T)
    assert isinstance(r, Failed) and "Emissor não visível" in r.erros


def test_resolve_platform_uses_clues_when_model_is_unsure():
    def ext(**kw):
        return RawExtraction(**kw)
    assert resolve_platform(ext(plataforma="BTG")) == "BTG"
    assert resolve_platform(ext(plataforma="DESCONHECIDA", indicios=["Investimentos Ultravioleta"])) == "NUBANK"
    assert resolve_platform(ext(plataforma="DESCONHECIDA", indicios=["coluna Taxa Eq. do CDB", "Estoque"])) == "BTG"
    assert resolve_platform(ext(plataforma="DESCONHECIDA", indicios=["Quantidade Disponível", "Liquidez XP"])) == "XP"
    assert resolve_platform(ext(plataforma="DESCONHECIDA", indicios=["botão Investir"])) == "DESCONHECIDA"
    # pistas contraditórias: não chuta
    assert resolve_platform(ext(plataforma="DESCONHECIDA", indicios=["Ultravioleta", "Liquidez XP"])) == "DESCONHECIDA"


def test_schema_asks_for_clues_before_platform():
    assert list(RawExtraction.model_fields)[:2] == ["indicios", "plataforma"]


def test_dash_grace_period_means_none():
    for vazio in ("-", "—", "Não há", "N/A"):
        r = interpret_offer(raw_ok(carencia=vazio), "BTG", Settings(), T)
        assert isinstance(r, Created), (vazio, r)
        assert r.data.data_carencia is None


def test_issuer_loses_glued_maturity_suffix():
    """O 9B às vezes devolve o emissor com o mês do nome ("ASA SCFI - SET/2029"), o que duplica a oferta."""
    for bruto, limpo in (("ASA SCFI - SET/2029", "ASA SCFI"), ("FIBRA - ABR/2032", "FIBRA"), ("BRF", "BRF")):
        r = interpret_offer(raw_ok(emissor=bruto), "XP", Settings(), T)
        assert r.data.emissor == limpo
