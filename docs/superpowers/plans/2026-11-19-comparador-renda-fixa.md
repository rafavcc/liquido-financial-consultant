# Comparador de Renda Fixa — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Execução escolhida pelo usuário:** subagent-driven. Implementador = subagente **Sonnet**; revisor por tarefa = subagente **Haiku**; orquestração e `.md` = Opus. Cada implementador recebe: esta tarefa inteira, "Global Constraints", "Review Focus" e `CLAUDE.md`.

**Goal:** App pessoal que ranqueia produtos de renda fixa brasileiros pelo valor líquido na data alvo do usuário.

**Architecture:** Backend FastAPI com domínio financeiro puro em Python (`Decimal`, calendário ANBIMA), persistência SQLite (stdlib `sqlite3`), dados de mercado de BCB/Focus/Tesouro com cache. Frontend React (Vite, TS, Tailwind) como PWA, compilado e servido pelo próprio FastAPI. Um serviço systemd; HTTPS via `tailscale serve`.

**Tech Stack:** Python ≥3.12, uv, FastAPI, pydantic v2, httpx, bizdays 2.0.0 (calendário `ANBIMA` embutido), pytest · Node 22, React 18.3.1, Vite 5.4, TypeScript 5.6, Tailwind 3.4, react-router-dom 6.28, @tanstack/react-query 5.59, recharts 2.13, @radix-ui/react-dialog 1.1, vite-plugin-pwa 0.20, vitest 2.1, @playwright/test (usar o Chromium pré-instalado).

**Spec:** `docs/superpowers/specs/2026-11-19-comparador-renda-fixa-design.md`

## Global Constraints

- Dinheiro e taxas em `Decimal` no backend; nenhum `float` em cálculo. Contexto decimal com `prec = 28`.
- Taxas como fração (`0.1375` = 13,75%). Conversão de % só em parsing de fontes e no frontend.
- Acúmulo de índices/taxas por dia útil ANBIMA, base 252, intervalo `(início, fim]`. IR e IOF por dias corridos.
- Na API, todo `Decimal` serializa como string; datas como `YYYY-MM-DD`.
- Alíquotas, isenções, custos, spread CDI–Selic, TTL e limite FGC vêm de `Settings`.
- Testes sem rede (fixtures em `backend/tests/fixtures/`).
- UI em pt-BR: `R$ 1.234,56`, `dd/mm/aaaa`, `13,65%`. Tema claro/escuro. Layout responsivo; navegação inferior no celular.
- `data_inicio` da simulação = hoje; `data_alvo` > hoje e `valor` > 0 (senão HTTP 422 com mensagem em pt-BR).
- Vencimento/pagamento em dia não útil é liquidado no próximo dia útil (`adjust_next`).
- Produto dependente de projeção ⇒ alerta `PROJECAO`; saída antecipada do Tesouro ⇒ `ESTIMATIVA_MERCADO`.
- Fontes: SGS `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{n}?formato=json` (432 Selic meta, 13522 IPCA 12m); Focus `https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/` (`ExpectativasMercadoAnuais`, `ExpectativaMercadoMensais`, filtro `baseCalculo eq 0`, `Data` mais recente); Tesouro CSV `https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv`.

## Review Focus

1. **Primeira execução sem rede e sem cache** → a app abre; produtos PRE são calculados; os demais vão para "Indisponíveis" com alerta `SEM_DADOS_MERCADO`; banner de erro com a fonte que falhou. (teste na Task 8)
2. **SGS 432 devolve ponto com data futura** (ex.: `09/12/2026` consultado em 19/11/2026) → usar o último ponto com data ≤ hoje; se não houver, o último. (teste na Task 3)
3. **`data_alvo` muito além do horizonte do Focus** (ex.: 2045) → projeção mantém o último valor, sem exceção; LCI/CDB com vencimento 2027 continuam corretos. (teste na Task 4)
4. **`data_alvo` em menos de 30 dias** → IOF aplicado em CDB de liquidez diária; LCI/LCA/CRI/CRA vão para seção vermelha como não resgatáveis. (teste na Task 5)
5. **Entrada de valor em formato brasileiro** (`50.000,00`, `50000`, `50.000`) → parse correto no frontend, sem confundir ponto de milhar com decimal. (teste na Task 9)

---

## Estrutura de arquivos

```
backend/
  pyproject.toml
  app/
    main.py              create_app(), montagem de rotas e static
    deps.py              Container (repos, market service, settings) via env
    api/{simulate,products,settings,market}.py
    domain/
      calendar.py        BusinessCalendar
      settings.py        Settings + defaults
      taxes.py           ir_rate, iof_rate, apply_taxes
      indexes.py         IndexPath (projeções e fatores)
      products/
        base.py          enums, ProductData, Alert, SimulationResult, SimContext, Product
        accrual.py       accrual_factor()
        bank.py          BankProduct, CDB, LCI, LCA, CRI, CRA
        treasury.py      Tesouro* + pricing helpers
        fund.py          FundoRendaFixa
        factory.py       build_product()
        validation.py    validate_product()
      sources.py         ProductSource, ManualSource, TesouroSource
      simulation.py      simulate_all()
    data/
      db.py              connect(), migrações
      repositories.py    ProductRepository, SettingsRepository, MarketCacheRepository
      bcb.py, focus.py, tesouro.py   parsing + fetch
      market.py          MarketSnapshot, MarketFetchers, HttpFetchers, FixtureFetchers, MarketService
    seed/products_example.json
  scripts/record_fixtures.py
  tests/  (espelha app/) + fixtures/
frontend/  (Task 9–12)
deploy/    liquido.service, install.sh, update.sh
README.md
```

---

### Task 1: Esqueleto do backend + calendário ANBIMA

**Files:**
- Create: `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/app/domain/__init__.py`, `backend/app/domain/calendar.py`
- Test: `backend/tests/domain/test_calendar.py`, `backend/tests/test_health.py`
- Modify: `.gitignore` (adicionar `backend/.venv/`, `backend/data/`, `frontend/node_modules/`, `frontend/dist/`, `__pycache__/`, `*.db`)

**Interfaces:**
- Produces:
  - `class BusinessCalendar` com `is_business_day(d: date) -> bool`, `business_days_between(start: date, end: date) -> int` (conta `(start, end]`), `business_days(start: date, end: date) -> list[date]` (dias úteis em `(start, end]`), `adjust_next(d: date) -> date`, `add_business_days(d: date, n: int) -> date`, `last_business_day_of_month(year: int, month: int) -> date`.
  - `get_calendar() -> BusinessCalendar` (singleton, `bizdays.Calendar.load("ANBIMA")`).
  - `create_app(...) -> FastAPI` com `GET /api/health → {"status": "ok"}` (assinatura final na Task 8).

- [ ] **Step 1:** `uv init --package` não; crie `pyproject.toml` à mão (projeto `liquido`, python `>=3.12`, deps: `fastapi`, `uvicorn[standard]`, `pydantic>=2`, `httpx`, `bizdays==2.0.0`; dev: `pytest`, `pytest-cov`). Rode `cd backend && uv sync`. Esperado: sem erro.
- [ ] **Step 2: Testes que falham**

```python
from datetime import date
from app.domain.calendar import get_calendar

cal = get_calendar()

def test_holidays_and_weekends():
    assert not cal.is_business_day(date(2026, 2, 17))   # Carnaval
    assert not cal.is_business_day(date(2026, 4, 21))   # Tiradentes
    assert not cal.is_business_day(date(2026, 11, 20))  # Consciência Negra
    assert not cal.is_business_day(date(2026, 11, 21))  # sábado
    assert cal.is_business_day(date(2026, 11, 19))

def test_between_excludes_start_includes_end():
    assert cal.business_days_between(date(2026, 12, 24), date(2026, 12, 28)) == 1
    assert cal.business_days_between(date(2026, 11, 19), date(2026, 11, 19)) == 0
    assert cal.business_days(date(2026, 11, 18), date(2026, 11, 23)) == [date(2026, 11, 19), date(2026, 11, 23)]

def test_adjust_and_month_end():
    assert cal.adjust_next(date(2027, 1, 1)) == date(2027, 1, 4)
    assert cal.adjust_next(date(2026, 11, 19)) == date(2026, 11, 19)
    assert cal.last_business_day_of_month(2027, 5) == date(2027, 5, 31)
    assert cal.last_business_day_of_month(2026, 5) == date(2026, 5, 29)
    assert cal.add_business_days(date(2026, 11, 19), 1) == date(2026, 11, 23)
```
e `test_health`: `TestClient(create_app()).get("/api/health").json() == {"status": "ok"}`.

- [ ] **Step 3:** `uv run pytest -q` → FAIL (módulo inexistente).
- [ ] **Step 4:** Implementar `calendar.py` (wrapper fino sobre bizdays) e `main.py` mínimo.
- [ ] **Step 5:** `uv run pytest -q` → PASS.
- [ ] **Step 6:** Commit `chore(backend): esqueleto FastAPI e calendário ANBIMA`.

---

### Task 2: Settings e tributos

**Files:**
- Create: `backend/app/domain/settings.py`, `backend/app/domain/taxes.py`
- Test: `backend/tests/domain/test_settings.py`, `backend/tests/domain/test_taxes.py`

**Interfaces:**
- Consumes: `ProductType` — **defina o enum nesta task** em `backend/app/domain/products/base.py` (o restante do arquivo vem na Task 5): `CDB, LCI, LCA, CRI, CRA, TESOURO_SELIC, TESOURO_PREFIXADO, TESOURO_PREFIXADO_JUROS, TESOURO_IPCA, TESOURO_IPCA_JUROS, TESOURO_RENDA_MAIS, TESOURO_EDUCA_MAIS, FUNDO_RF` (`StrEnum`).
- Produces:
  - `class IrBracket(BaseModel)`: `max_days: int | None`, `rate: Decimal`.
  - `class Settings(BaseModel)` com defaults:
    - `ir_brackets = [(180, 0.225), (360, 0.20), (720, 0.175), (None, 0.15)]`
    - `iof_table`: 29 valores para os dias 1–29: `0.96 0.93 0.90 0.86 0.83 0.80 0.76 0.73 0.70 0.66 0.63 0.60 0.56 0.53 0.50 0.46 0.43 0.40 0.36 0.33 0.30 0.26 0.23 0.20 0.16 0.13 0.10 0.06 0.03`
    - `ir_exempt_types = {LCI, LCA, CRI, CRA}`, `iof_exempt_types = {LCI, LCA, CRI, CRA}`
    - `come_cotas_longo = 0.15`, `come_cotas_curto = 0.20`
    - `custodia_b3_aa = 0.0020`, `tesouro_selic_isencao_custodia = 10000`
    - `spread_cdi_selic = 0.0010`
    - `projection_mode: Literal["focus", "manual"] = "focus"`, `manual_selic_by_year: dict[int, Decimal] = {}`, `manual_ipca_by_year: dict[int, Decimal] = {}`
    - `market_cache_ttl_hours = 6`, `fgc_limite = 250000`
    - `carencia_min_meses_lci = 12`, `carencia_min_meses_lca = 9`
  - Validadores do `Settings`: alíquotas em `[0, 1]`; `ir_brackets` com `max_days` estritamente crescente e último `None`; `iof_table` com exatamente 29 itens não crescentes; TTL ≥ 1; modo manual exige ao menos um ano em cada dicionário.
  - `ir_rate(days: int, s: Settings) -> Decimal`; `iof_rate(days: int, s: Settings) -> Decimal` (dias ≥ 30 ⇒ 0; dias < 1 tratado como 1).
  - `class TaxBreakdown(BaseModel)`: `iof: Decimal`, `ir: Decimal`.
  - `apply_taxes(gain: Decimal, days: int, tipo: ProductType, s: Settings) -> TaxBreakdown`: IOF = `gain × iof_rate`; IR = `(gain − iof) × ir_rate`; ambos quantizados a centavos `ROUND_HALF_EVEN`; ganho ≤ 0 ⇒ zeros; isenções por tipo.

- [ ] **Step 1: Testes que falham**

```python
def test_ir_brackets():
    s = Settings()
    assert [ir_rate(d, s) for d in (1, 180, 181, 360, 361, 720, 721, 5000)] == \
        [D("0.225"), D("0.225"), D("0.20"), D("0.20"), D("0.175"), D("0.175"), D("0.15"), D("0.15")]

def test_iof():
    s = Settings()
    assert iof_rate(1, s) == D("0.96") and iof_rate(29, s) == D("0.03") and iof_rate(30, s) == 0

def test_apply_taxes_cdb_and_exempt():
    s = Settings()
    assert apply_taxes(D("1000"), 10, ProductType.CDB, s) == TaxBreakdown(iof=D("660.00"), ir=D("76.50"))
    assert apply_taxes(D("1511.00"), 365, ProductType.CDB, s) == TaxBreakdown(iof=D("0.00"), ir=D("264.42"))
    assert apply_taxes(D("1000"), 10, ProductType.LCI, s) == TaxBreakdown(iof=D("0"), ir=D("0"))
    assert apply_taxes(D("-5"), 400, ProductType.CDB, s) == TaxBreakdown(iof=D("0"), ir=D("0"))

def test_settings_validation():
    with pytest.raises(ValidationError): Settings(custodia_b3_aa=D("-0.01"))
    with pytest.raises(ValidationError): Settings(ir_brackets=[IrBracket(max_days=360, rate=D("0.2")), IrBracket(max_days=180, rate=D("0.2")), IrBracket(max_days=None, rate=D("0.15"))])
    with pytest.raises(ValidationError): Settings(projection_mode="manual")
    assert Settings.model_validate_json(Settings().model_dump_json()) == Settings()
```
- [ ] **Step 2:** `uv run pytest tests/domain -q` → FAIL.
- [ ] **Step 3:** Implementar `settings.py` e `taxes.py`.
- [ ] **Step 4:** → PASS. **Step 5:** Commit `feat(domain): settings e tributos (IR, IOF)`.

---

### Task 3: Dados de mercado — clientes, cache e serviço

**Files:**
- Create: `backend/app/data/{__init__,db,repositories,bcb,focus,tesouro,market}.py`, `backend/scripts/record_fixtures.py`
- Test: `backend/tests/data/test_bcb.py`, `test_focus.py`, `test_tesouro.py`, `test_market_service.py`; fixtures em `backend/tests/fixtures/`

**Interfaces:**
- Produces:
  - `db.connect(path: Path) -> sqlite3.Connection` (cria tabelas: `products(id TEXT PK, payload TEXT)`, `kv(key TEXT PK, value TEXT)`, `market_cache(source TEXT PK, payload TEXT, fetched_at TEXT, error TEXT)`).
  - `MarketCacheRepository(conn)`: `load(source: str) -> CacheEntry | None`, `save(source: str, payload: dict, fetched_at: datetime)`, `save_error(source: str, error: str)`.
  - `bcb.parse_sgs(json_text: str) -> list[SgsPoint]` (`SgsPoint(data: date, valor: Decimal)` — valor em %, cru); `bcb.latest_until(points, today: date) -> SgsPoint`.
  - `focus.parse_annual(json_text: str) -> tuple[date, dict[int, Decimal]]` (Data mais recente, `DataReferencia → Mediana/100`); `focus.parse_monthly(json_text: str) -> tuple[date, dict[str, Decimal]]` (`"MM/YYYY" → "YYYY-MM"`, mediana/100, só a `Data` mais recente).
  - `class TesouroQuote(BaseModel)`: `tipo: str`, `vencimento: date`, `data_base: date`, `taxa_compra`, `taxa_venda` (fração), `pu_compra`, `pu_venda: Decimal`.
  - `tesouro.parse_latest(csv_text: str) -> list[TesouroQuote]`: separador `;`, vírgula decimal, só a maior `Data Base`, só `pu_compra > 0`, descarta `Tesouro IGPM+ com Juros Semestrais`.
  - `class MarketSnapshot(BaseModel)`: `selic_meta: Decimal | None`, `ipca_12m: Decimal | None`, `ipca_12m_ref: date | None`, `focus_data: date | None`, `focus_selic_anual: dict[int, Decimal]`, `focus_ipca_anual: dict[int, Decimal]`, `focus_ipca_mensal: dict[str, Decimal]`, `tesouro: list[TesouroQuote]`, `tesouro_data_base: date | None`, `fetched_at: dict[str, datetime]`, `errors: dict[str, str]`. Fontes: `"bcb"`, `"focus"`, `"tesouro"`.
  - `class MarketFetchers(Protocol)`: `fetch_bcb(today) -> dict`, `fetch_focus() -> dict`, `fetch_tesouro() -> dict` (cada um devolve o pedaço de campos do snapshot daquela fonte).
  - `HttpFetchers(client: httpx.Client)`; `FixtureFetchers(dir: Path)` (lê os mesmos arquivos gravados por `record_fixtures.py`).
  - `MarketService(cache: MarketCacheRepository, fetchers: MarketFetchers, now: Callable[[], datetime])` com `get_snapshot(ttl_hours: int, force: bool = False) -> MarketSnapshot`: por fonte, usa cache se dentro do TTL; senão busca; falha ⇒ mantém último payload e registra `errors[fonte]`; sem payload ⇒ campos vazios + erro.

- [ ] **Step 1:** Escreva `scripts/record_fixtures.py` (baixa SGS 432 e 13522 últimos 5, Focus anual Selic+IPCA, Focus mensal IPCA, e o CSV do Tesouro **reduzido às 2 últimas `Data Base`**) para `tests/fixtures/market/`. Rode uma vez: `uv run python scripts/record_fixtures.py`. Esperado: 6 arquivos criados, CSV < 50 KB. Commit das fixtures.
- [ ] **Step 2: Testes que falham** (fixtures mínimas inline + as gravadas)

```python
def test_sgs_future_point_ignored():
    pts = parse_sgs('[{"data":"18/11/2026","valor":"13.75"},{"data":"09/12/2026","valor":"13.75"}]')
    assert latest_until(pts, date(2026, 11, 19)) == SgsPoint(data=date(2026, 11, 18), valor=D("13.75"))
    assert latest_until(pts[1:], date(2026, 11, 19)).data == date(2026, 12, 9)

def test_focus_annual():
    data, anual = parse_annual(FOCUS_SELIC_SAMPLE)  # amostra com Data 2026-11-13 e 2026-11-06 misturadas
    assert data == date(2026, 11, 13) and anual[2027] == D("0.1275")

def test_focus_monthly():
    _, mensal = parse_monthly('{"value":[{"Indicador":"IPCA","Data":"2026-11-13","DataReferencia":"11/2028","Mediana":0.3200,"baseCalculo":0}]}')
    assert mensal == {"2028-11": D("0.0032")}

TESOURO_CSV = """Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;Taxa Venda Manha;PU Compra Manha;PU Venda Manha;PU Base Manha
Tesouro Prefixado;01/01/2028;18/11/2026;14,38;14,50;861,32;859,85;859,85
Tesouro Prefixado;01/01/2028;17/11/2026;14,30;14,42;862,00;860,50;860,50
Tesouro IGPM+ com Juros Semestrais;01/01/2031;18/11/2026;7,63;7,75;8110,14;8076,03;8076,03
Tesouro Selic;01/03/2029;18/11/2026;0,05;0,06;20310,33;20295,34;20295,34"""

def test_tesouro_parse_latest():
    q = parse_latest(TESOURO_CSV)
    assert [x.tipo for x in q] == ["Tesouro Prefixado", "Tesouro Selic"]
    assert q[0] == TesouroQuote(tipo="Tesouro Prefixado", vencimento=date(2028,1,1), data_base=date(2026,11,18),
        taxa_compra=D("0.1438"), taxa_venda=D("0.1450"), pu_compra=D("861.32"), pu_venda=D("859.85"))

def test_service_ttl_and_failure(tmp_path):
    # fetchers falsos contando chamadas; now controlável
    # 1ª chamada busca as 3 fontes; 2ª dentro do TTL não busca; após TTL busca de novo;
    # fetch_focus lançando erro ⇒ snapshot mantém focus anterior e errors["focus"] preenchido;
    # cache vazio + erro ⇒ focus_selic_anual == {} e "focus" in errors; force=True ignora TTL.
```
- [ ] **Step 3:** `uv run pytest tests/data -q` → FAIL. **Step 4:** Implementar. **Step 5:** → PASS.
- [ ] **Step 6:** Commit `feat(data): clientes BCB/Focus/Tesouro com cache`.

---

### Task 4: Projeções de índices (`IndexPath`)

**Files:**
- Create: `backend/app/domain/indexes.py`
- Test: `backend/tests/domain/test_indexes.py`

**Interfaces:**
- Consumes: `BusinessCalendar` (Task 1), `Settings` (Task 2), `MarketSnapshot` (Task 3).
- Produces:
  - `IndexPath.build(snapshot: MarketSnapshot, settings: Settings, cal: BusinessCalendar, today: date) -> IndexPath | None` (None se modo focus e `selic_meta` ausente).
  - `selic_aa(d: date) -> Decimal`; `cdi_aa(d) = selic_aa(d) − spread_cdi_selic`; `ipca_month(year: int, month: int) -> Decimal`.
  - `cdi_factor(start, end, pct: Decimal = 1, spread: Decimal = 0) -> Decimal` = ∏ sobre dias úteis `(start, end]` de `(1 + pct·cdi_d) · (1 + spread)^(1/252)`, com `cdi_d = (1 + cdi_aa(d))^(1/252) − 1`.
  - `selic_factor(start, end) -> Decimal` (idem com `selic_aa`, pct 1).
  - `ipca_factor(start, end) -> Decimal` = ∏ dias úteis de `(1 + ipca_month(m))^(1/du_mês)`, `du_mês` = dias úteis do mês civil.
  - `pre_factor(rate: Decimal, start, end) -> Decimal` (estático) = `(1 + rate)^(du/252)`.
  - `fonte: str` (`"Focus 13/11/2026"` ou `"Cenário manual"`); `yearly_table() -> list[tuple[int, Decimal, Decimal]]` (ano, Selic fim de ano, IPCA anual) para a tela Mercado.
- Regras (design 7.4): âncoras Selic = `(today, selic_meta)` + `(31/12/ano, mediana)`; interpolação linear diária; antes/depois mantém extremos. Modo manual usa `manual_selic_by_year` como âncoras de 31/12. IPCA: mensal do Focus quando houver; senão `(1 + anual_do_ano)^(1/12) − 1`; sem ano ⇒ último anual conhecido. Memoize taxas diárias por data.

- [ ] **Step 1: Testes que falham**

```python
def flat_snapshot(selic="0.1375", ipca_anual="0.045"):
    return MarketSnapshot(selic_meta=D(selic), focus_selic_anual={2026: D(selic), 2027: D(selic)},
        focus_ipca_anual={2026: D(ipca_anual), 2027: D(ipca_anual)}, focus_ipca_mensal={}, ...)

def test_flat_cdi_one_year():
    p = IndexPath.build(flat_snapshot(), Settings(), cal, TODAY)
    end = cal.add_business_days(TODAY, 252)
    assert abs(p.cdi_factor(TODAY, end) - D("1.1365")) < D("1e-9")
    d = (D("1.1365") ** (D(1) / 252)) - 1
    assert abs(p.cdi_factor(TODAY, end, pct=D("1.10")) - (1 + D("1.10") * d) ** 252) < D("1e-9")

def test_interpolation():
    snap = flat_snapshot(); snap.focus_selic_anual = {2026: D("0.1375"), 2027: D("0.1275")}
    p = IndexPath.build(snap, Settings(), cal, TODAY)
    assert p.selic_aa(date(2027, 12, 31)) == D("0.1275")
    assert D("0.1275") < p.selic_aa(date(2027, 7, 1)) < D("0.1375")
    assert p.selic_aa(date(2045, 1, 1)) == D("0.1275")          # Review Focus 3

def test_ipca_monthly_overrides_annual():
    snap = flat_snapshot(); snap.focus_ipca_mensal = {"2026-12": D("0.0050")}
    p = IndexPath.build(snap, Settings(), cal, TODAY)
    assert p.ipca_month(2026, 12) == D("0.0050")
    assert abs(p.ipca_month(2027, 3) - (D("1.045") ** (D(1) / 12) - 1)) < D("1e-12")
    assert abs(p.ipca_factor(date(2026, 11, 30), date(2026, 12, 31)) - D("1.0050")) < D("1e-9")

def test_manual_mode_and_missing():
    s = Settings(projection_mode="manual", manual_selic_by_year={2027: D("0.10")}, manual_ipca_by_year={2027: D("0.04")})
    assert IndexPath.build(flat_snapshot(), s, cal, TODAY).fonte == "Cenário manual"
    assert IndexPath.build(MarketSnapshot.empty(), Settings(), cal, TODAY) is None
```
(adicione `MarketSnapshot.empty()` na Task 3 se ainda não existir — classmethod com tudo vazio.)
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS (suite de 252 dias deve rodar < 1 s).
- [ ] **Step 5:** Commit `feat(domain): projeções de Selic/CDI/IPCA`.

---

### Task 5: Modelo de produto + produtos bancários e securitizados

**Files:**
- Create/Modify: `backend/app/domain/products/{__init__,base,accrual,bank,validation}.py`
- Test: `backend/tests/domain/products/test_bank.py`, `test_validation.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces (em `base.py`):
  - Enums `Indexer {PRE, PCT_CDI, CDI_MAIS, IPCA_MAIS, SELIC}`, `Liquidity {NO_VENCIMENTO, DIARIA, DIARIA_APOS_CARENCIA}`, `Coverage {FGC, TESOURO, NENHUMA}`, `Section {VENCE_ATE_DATA, VENCE_DEPOIS, INDISPONIVEL}`, `AlertCode {PROJECAO, FGC_LIMITE, SEM_FGC, ESTIMATIVA_MERCADO, FUNDO_SEM_GARANTIA, PARADO, EXEMPLO, MODELO_SIMPLIFICADO, ABAIXO_MINIMO, NAO_RESGATAVEL, SEM_DADOS_MERCADO, RESGATE_DN}`.
  - `ProductData(BaseModel)`: `id: str`, `tipo: ProductType`, `nome`, `emissor`, `plataforma: str`, `indexador: Indexer`, `taxa: Decimal` (PRE: taxa a.a.; PCT_CDI: fração do CDI, ex. `1.12`; CDI_MAIS/IPCA_MAIS: spread a.a.; SELIC: ágio a.a.), `data_vencimento: date | None`, `valor_minimo: Decimal`, `liquidez: Liquidity`, `data_carencia: date | None`, `cobertura: Coverage | None` (validador preenche: CDB/LCI/LCA→FGC, CRI/CRA/FUNDO_RF→NENHUMA, TESOURO_*→TESOURO), `ativo: bool = True`, `exemplo: bool = False`, `observacoes: str = ""`, `taxa_adm: Decimal | None`, `prazo_resgate_dias: int | None`, `classe_tributaria: Literal["LONGO", "CURTO"] | None`.
  - `Alert(BaseModel)`: `code: AlertCode`, `message: str` (pt-BR).
  - `SeriePoint(BaseModel)`: `data: date`, `valor_bruto: Decimal`.
  - `SimulationResult(BaseModel)`: `product: ProductData`, `secao: Section`, `resgatavel: bool`, `estimativa_mercado: bool`, `data_saida: date | None`, `dias_parado: int`, `valor_investido: Decimal`, `valor_bruto`, `iof`, `ir`, `custodia`, `come_cotas`, `taxa_adm: Decimal` (default 0), `valor_liquido: Decimal | None`, `rentab_liquida: Decimal | None`, `taxa_liquida_aa: Decimal | None`, `data_solicitacao_resgate: date | None`, `alertas: list[Alert]`, `serie: list[SeriePoint]`.
  - `SimContext(dataclass)`: `today: date`, `cal: BusinessCalendar`, `settings: Settings`, `index: IndexPath | None`.
  - `class Product(ABC)`: `data: ProductData`; `simulate(valor: Decimal, data_alvo: date, ctx: SimContext) -> SimulationResult` (abstrato); helpers comuns: `_unavailable(...)`, `_common_alerts(...)`, `_net_annual_rate(valor, liquido, start, end, cal)` = `(liquido/valor)^(252/du) − 1`.
- `accrual.py`: `accrual_factor(indexador: Indexer, taxa: Decimal, start: date, end: date, ctx: SimContext) -> Decimal` (PRE→pre_factor; PCT_CDI→cdi_factor(pct=taxa); CDI_MAIS→cdi_factor(spread=taxa); IPCA_MAIS→ipca_factor·pre_factor(taxa); SELIC→selic_factor·pre_factor(taxa)). `needs_index(indexador) -> bool`.
- `bank.py`: `BankProduct(Product)` + subclasses `CDB`, `LCI`, `LCA`, `CRI`, `CRA`. Algoritmo (design 7.1):
  1. `valor < valor_minimo` ⇒ `INDISPONIVEL` + `ABAIXO_MINIMO`.
  2. Precisa de índice e `ctx.index is None` ⇒ `INDISPONIVEL` + `SEM_DADOS_MERCADO`.
  3. `venc = adjust_next(data_vencimento)`. `venc ≤ data_alvo` ⇒ `VENCE_ATE_DATA`, saída = venc, `dias_parado = (data_alvo − venc).days` (alerta `PARADO` se > 0).
  4. Senão `VENCE_DEPOIS`; resgatável se `DIARIA` ou (`DIARIA_APOS_CARENCIA` e `data_alvo ≥ data_carencia`); saída = `data_alvo`; não resgatável ⇒ valores `None`, alerta `NAO_RESGATAVEL`.
  5. bruto = valor·fator; `apply_taxes(bruto − valor, (saída − today).days, tipo)`; líquido = bruto − iof − ir.
  6. `serie`: um ponto no último dia útil de cada mês até a saída, mais o ponto da saída.
  7. Alertas: `PROJECAO` (indexador ≠ PRE), `FGC_LIMITE` (FGC e valor > `fgc_limite`), `SEM_FGC` (NENHUMA), `EXEMPLO`.
- `validation.py`: `validate_product(data: ProductData, settings: Settings, today: date) -> list[str]` — mensagens pt-BR: vencimento obrigatório e futuro (exceto FUNDO_RF); LCI/LCA não podem ter `DIARIA`; LCI/LCA: `data_carencia` (ou vencimento, se `NO_VENCIMENTO`) ≥ today + `carencia_min_meses_*`; `DIARIA_APOS_CARENCIA` exige `data_carencia` < vencimento; taxa plausível (PRE/CDI_MAIS/IPCA_MAIS em `[0, 0.5]`, PCT_CDI em `[0.5, 2]`); FUNDO_RF exige `taxa_adm`, `prazo_resgate_dias`, `classe_tributaria` e indexador PCT_CDI/CDI_MAIS; tipos TESOURO_* não são cadastráveis.

- [ ] **Step 1: Testes que falham** (contexto com `IndexPath` plano de CDI 13,65% e `TODAY = date(2026, 11, 19)`)

```python
def test_cdb_matures_before_target():
    p = CDB(make(tipo=CDB, indexador=PCT_CDI, taxa=D("1.10"), data_vencimento=cal.add_business_days(TODAY, 252)))
    r = p.simulate(D("10000"), date(2028, 6, 1), ctx)
    assert r.secao == Section.VENCE_ATE_DATA and r.dias_parado > 0
    assert abs(r.valor_bruto - D("11511")) < D("1")
    assert r.ir == ((r.valor_bruto - 10000) * D("0.175")).quantize(D("0.01"))
    assert {a.code for a in r.alertas} >= {AlertCode.PROJECAO, AlertCode.PARADO}

def test_lci_92_equals_cdb_110_roughly():   # exemplo do design
    lci = LCI(make(tipo=LCI, taxa=D("0.92"), data_vencimento=cal.add_business_days(TODAY, 252)))
    assert abs(lci.simulate(D("10000"), date(2028,1,1), ctx).valor_liquido - D("11249")) < D("2")

def test_short_target_iof_and_unredeemable():          # Review Focus 4
    alvo = TODAY + timedelta(days=10)
    cdb = CDB(make(tipo=CDB, liquidez=DIARIA, taxa=D("1.0"), data_vencimento=date(2030,1,2)))
    r = cdb.simulate(D("10000"), alvo, ctx)
    assert r.secao == Section.VENCE_DEPOIS and r.resgatavel and r.iof > 0
    lca = LCA(make(tipo=LCA, liquidez=NO_VENCIMENTO, data_vencimento=date(2028,1,3)))
    r2 = lca.simulate(D("10000"), alvo, ctx)
    assert not r2.resgatavel and r2.valor_liquido is None and AlertCode.NAO_RESGATAVEL in codes(r2)

def test_grace_then_daily():
    lci = LCI(make(tipo=LCI, liquidez=DIARIA_APOS_CARENCIA, data_carencia=date(2027,11,19), data_vencimento=date(2029,1,15)))
    assert lci.simulate(D("10000"), date(2028,3,1), ctx).resgatavel
    assert not lci.simulate(D("10000"), date(2027,6,1), ctx).resgatavel

def test_holiday_maturity_adjusted():
    r = CDB(make(data_vencimento=date(2027,1,1))).simulate(D("10000"), date(2027,1,2), ctx)
    assert r.secao == Section.VENCE_DEPOIS                         # paga em 04/01/2027
    assert CDB(make(data_vencimento=date(2027,1,1))).simulate(D("10000"), date(2027,1,4), ctx).data_saida == date(2027,1,4)

def test_below_minimum_and_no_market():
    assert CDB(make(valor_minimo=D("5000"))).simulate(D("1000"), date(2028,1,1), ctx).secao == Section.INDISPONIVEL
    r = CDB(make(indexador=PCT_CDI)).simulate(D("10000"), date(2028,1,1), ctx_sem_indice)
    assert r.secao == Section.INDISPONIVEL and AlertCode.SEM_DADOS_MERCADO in codes(r)
    assert CDB(make(indexador=PRE, taxa=D("0.142"))).simulate(D("10000"), date(2028,1,1), ctx_sem_indice).secao != Section.INDISPONIVEL

def test_cri_no_fgc_and_fgc_limit():
    assert AlertCode.SEM_FGC in codes(CRI(make(tipo=CRI)).simulate(D("10000"), date(2033,1,1), ctx))
    assert AlertCode.FGC_LIMITE in codes(CDB(make()).simulate(D("300000"), date(2033,1,1), ctx))
```
e `test_validation.py` cobrindo cada mensagem acima (uma asserção por regra, ex.: `"LCI exige carência mínima de 12 meses" in validate_product(...)`).
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(domain): produtos bancários e securitizados`.

---

### Task 6: Tesouro Direto

**Files:**
- Create: `backend/app/domain/products/treasury.py`
- Test: `backend/tests/domain/products/test_treasury.py`

**Interfaces:**
- Consumes: `TesouroQuote` (Task 3), `Product`/`SimulationResult` (Task 5), `IndexPath` (Task 4).
- Produces:
  - `TIPO_MAP: dict[str, ProductType]` (`"Tesouro Selic"→TESOURO_SELIC`, `"Tesouro Prefixado"→TESOURO_PREFIXADO`, `"Tesouro Prefixado com Juros Semestrais"→TESOURO_PREFIXADO_JUROS`, `"Tesouro IPCA+"→TESOURO_IPCA`, `"Tesouro IPCA+ com Juros Semestrais"→TESOURO_IPCA_JUROS`, `"Tesouro Renda+ Aposentadoria Extra"→TESOURO_RENDA_MAIS`, `"Tesouro Educa+"→TESOURO_EDUCA_MAIS`).
  - `build_treasury(q: TesouroQuote) -> TreasuryProduct` (id `tesouro-{tipo-slug}-{AAAA-MM-DD}`, nome `"{tipo} {AAAA}"`, plataforma `"Tesouro Direto"`, `valor_minimo = max(30, 0.01·pu_compra)`).
  - Helpers puros:
    - `cash_flow_dates(venc: date, months_step: int, after: date) -> list[date]` (datas a cada `months_step` meses **para trás a partir do vencimento**, estritamente > `after`).
    - `flows(tipo, venc, after) -> list[tuple[date, Decimal]]` em unidades de "valor de face/VNA": LTN `[(venc, 1)]`; NTN-F cupom `1.10^0.5 − 1` semestral + 1 no vencimento; NTN-B Principal/LFT `[(venc, 1)]`; NTN-B cupom `1.06^0.5 − 1` semestral + 1; Renda+ 240 e Educa+ 60 parcelas mensais iguais de `1/N`, a última no vencimento.
    - `pv_factor(flows, rate: Decimal, ref: date, cal) -> Decimal` = Σ `f / (1 + rate)^(du(ref, adjust_next(d))/252)`.
  - Valoração: face nominal = 1000 (LTN/NTN-F); para LFT/NTN-B/Renda+/Educa+, `VNA_hoje = pu_compra / pv_factor(flows, taxa_compra, today)` e `VNA(t) = VNA_hoje · selic_factor|ipca_factor(today, t)`.
  - Simulação: `qtd = floor_2casas(valor / pu_compra)`, `valor_investido = qtd·pu_compra`. Fluxos recebidos até `min(data_alvo, venc)` são tributados no recebimento (IR pelos dias desde hoje) e **ficam parados**. `venc ≤ data_alvo` ⇒ `VENCE_ATE_DATA`. Senão `VENCE_DEPOIS`, `resgatavel=True`, `estimativa_mercado=True`, valor de saída = `qtd · VNA(data_alvo) · pv_factor(fluxos restantes, taxa_venda, data_alvo)` (face 1000 para pré), alerta `ESTIMATIVA_MERCADO`. IR no ganho de capital da saída. Custódia: `custodia_b3_aa · base_média · dias/365`, base_média = média entre investido e valor bruto de saída; Tesouro Selic: base = excedente acima de `tesouro_selic_isencao_custodia`. `PROJECAO` em todos exceto TESOURO_PREFIXADO/_JUROS; `MODELO_SIMPLIFICADO` em Renda+/Educa+.

- [ ] **Step 1: Testes que falham**

```python
def test_ltn_and_ntnf_pricing_matches_published_pu():
    for q in parse_latest(fixture("market/tesouro.csv")):
        if q.tipo in ("Tesouro Prefixado", "Tesouro Prefixado com Juros Semestrais"):
            f = flows(TIPO_MAP[q.tipo], q.vencimento, q.data_base)
            assert abs(1000 * pv_factor(f, q.taxa_compra, q.data_base, cal) - q.pu_compra) < D("0.10"), q

def test_coupon_dates_backwards():
    assert cash_flow_dates(date(2035,5,15), 6, date(2026,11,19))[:2] == [date(2027,5,15), date(2027,11,15)]
    assert cash_flow_dates(date(2032,8,15), 6, date(2026,11,19))[0] == date(2027,2,15)

def test_ltn_held_to_maturity():
    q = TesouroQuote(tipo="Tesouro Prefixado", vencimento=date(2028,1,1), data_base=TODAY, taxa_compra=D("0.1438"), taxa_venda=D("0.1450"), pu_compra=D("861.32"), pu_venda=D("859.85"))
    r = build_treasury(q).simulate(D("10000"), date(2028,6,1), ctx)
    assert r.secao == Section.VENCE_ATE_DATA and r.valor_investido == D("11.61") * D("861.32")
    assert r.valor_bruto == D("11610.00") and AlertCode.PROJECAO not in codes(r)

def test_early_exit_is_market_estimate():
    r = build_treasury(q_ltn_2032).simulate(D("10000"), date(2028,6,1), ctx)
    assert r.secao == Section.VENCE_DEPOIS and r.estimativa_mercado and AlertCode.ESTIMATIVA_MERCADO in codes(r)

def test_ntnb_coupons_idle_and_taxed():
    r = build_treasury(q_ntnb_juros_2035).simulate(D("10000"), date(2035,6,1), ctx)
    # cupons de 2027..2035 recebidos e parados; IR descontado em cada um; dias_parado > 0
    assert r.secao == Section.VENCE_ATE_DATA and r.ir > 0 and AlertCode.PROJECAO in codes(r)

def test_selic_custody_exemption():
    small = build_treasury(q_selic_2029).simulate(D("9000"), date(2029,3,5), ctx)
    big = build_treasury(q_selic_2029).simulate(D("100000"), date(2029,3,5), ctx)
    assert small.custodia == 0 and big.custodia > 0
```
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS. **Step 5:** Commit `feat(domain): títulos do Tesouro Direto`.

---

### Task 7: Fundos de Renda Fixa

**Files:**
- Create: `backend/app/domain/products/fund.py`, `backend/app/domain/products/factory.py`
- Test: `backend/tests/domain/products/test_fund.py`, `test_factory.py`

**Interfaces:**
- Produces:
  - `FundoRendaFixa(Product)`. Saída = `data_alvo` (sempre `VENCE_ATE_DATA` se disponível). Por dia útil: `fator_dia = (1 + idx_dia) · (1 − taxa_adm)^(1/252)` onde `idx_dia` vem de PCT_CDI/CDI_MAIS. Come-cotas no último dia útil de maio e novembro em `(today, saída]`: `cc = aliquota · (valor − base)` se positivo, `valor −= cc`, `base = valor`; alíquota `come_cotas_longo|curto` por `classe_tributaria`. No resgate: `ir_total = ir_rate(dias)·(valor_sem_cc_acumulado − investido)`… implemente como: `ir_final = max(0, ir_rate(dias)·ganho_total_bruto − cc_pago)`, IOF se dias < 30. `taxa_adm` do resultado = bruto sem taxa − bruto com taxa. `data_solicitacao_resgate = data_alvo − prazo_resgate_dias` (dias corridos) + alerta `RESGATE_DN`. Alertas `PROJECAO`, `FUNDO_SEM_GARANTIA`, `SEM_FGC`.
  - `build_product(data: ProductData) -> Product` (mapeia `tipo` → CDB/LCI/LCA/CRI/CRA/FundoRendaFixa; TESOURO_* ⇒ `ValueError`).

- [ ] **Step 1: Testes que falham**

```python
def test_fund_admin_fee_reduces_return():
    a = fundo(taxa=D("1.0"), taxa_adm=D("0")).simulate(D("10000"), ALVO_1ANO, ctx)
    b = fundo(taxa=D("1.0"), taxa_adm=D("0.01")).simulate(D("10000"), ALVO_1ANO, ctx)
    assert b.valor_bruto < a.valor_bruto and b.taxa_adm > 0

def test_come_cotas_total_tax_equals_regressive():
    r = fundo(taxa=D("1.0"), taxa_adm=D("0"), classe="LONGO").simulate(D("10000"), date(2029,1,15), ctx)
    ganho = r.valor_bruto + r.come_cotas - 10000
    assert r.come_cotas > 0
    assert abs((r.come_cotas + r.ir) - ganho * D("0.15")) < D("0.05")       # > 720 dias

def test_come_cotas_dates():
    # alvo 2027-06-15: come-cotas em 2026-11-30 e 2027-05-31 → 2 eventos (expor contagem via r.alertas ou helper come_cotas_dates)
    assert come_cotas_dates(cal, TODAY, date(2027,6,15)) == [date(2026,11,30), date(2027,5,31)]

def test_redemption_request_date():
    r = fundo(prazo=30).simulate(D("10000"), date(2027,6,15), ctx)
    assert r.data_solicitacao_resgate == date(2027,5,16) and AlertCode.RESGATE_DN in codes(r)

def test_factory():
    assert isinstance(build_product(make(tipo=ProductType.LCA)), LCA)
    with pytest.raises(ValueError): build_product(make(tipo=ProductType.TESOURO_SELIC))
```
- [ ] **Step 2:** FAIL. **Step 3:** Implementar (`come_cotas_dates(cal, start, end) -> list[date]` público em `fund.py`). **Step 4:** PASS. **Step 5:** Commit `feat(domain): fundos de renda fixa com come-cotas`.

---

### Task 8: Fontes, simulação, persistência, seed e API

**Files:**
- Create: `backend/app/domain/sources.py`, `backend/app/domain/simulation.py`, `backend/app/deps.py`, `backend/app/api/{__init__,simulate,products,settings,market}.py`, `backend/app/seed/products_example.json`
- Modify: `backend/app/data/repositories.py`, `backend/app/main.py`
- Test: `backend/tests/domain/test_simulation.py`, `backend/tests/api/test_api.py`

**Interfaces:**
- Consumes: Tasks 1–7.
- Produces:
  - `ProductRepository(conn)`: `list() -> list[ProductData]`, `get(id) -> ProductData | None`, `create(data) -> ProductData` (gera `id` uuid4 se vazio), `update(id, data) -> ProductData`, `delete(id) -> None`, `count() -> int`.
  - `SettingsRepository(conn)`: `get() -> Settings` (default se vazio), `save(s: Settings)`, `reset() -> Settings`; `kv` também guarda `seeded = "1"`.
  - `class ProductSource(Protocol)`: `name: str`; `load(ctx: SimContext, snapshot: MarketSnapshot) -> list[Product]`. Implementações `ManualSource(repo)` (só `ativo`) e `TesouroSource()`.
  - `SimulationResponse(BaseModel)`: `vence_ate_data: list[SimulationResult]`, `vence_depois: list[SimulationResult]`, `indisponiveis: list[SimulationResult]`, `mercado: MarketSummary`.
  - `MarketSummary(BaseModel)`: `selic_meta`, `cdi_aa`, `ipca_12m`, `ipca_12m_ref`, `fonte_projecao: str | None`, `projecao: list[{ano, selic, ipca}]`, `fetched_at: dict[str, datetime]`, `errors: dict[str, str]`, `tesouro_data_base`.
  - `simulate_all(products: list[Product], valor: Decimal, data_alvo: date, ctx: SimContext) -> tuple[list, list, list]`. Ordenação: verdes por `valor_liquido` desc, empate `taxa_liquida_aa` desc; vermelhos resgatáveis por `valor_liquido` desc, depois não resgatáveis por `data_vencimento` asc; indisponíveis por `nome`. Exceção em um produto não derruba os outros: vira `INDISPONIVEL` com mensagem.
  - `create_app(db_path: Path | None = None, fetchers: MarketFetchers | None = None, static_dir: Path | None = None) -> FastAPI` — defaults por env: `LIQUIDO_DB` (padrão `backend/data/liquido.db`), `LIQUIDO_MARKET_FIXTURES` (se definido ⇒ `FixtureFetchers`), `LIQUIDO_STATIC_DIR` (padrão `frontend/dist`). Na inicialização: cria DB; se `seeded` ausente e sem produtos ⇒ importa o seed.
  - Rotas (`/api`):
    - `POST /simulate` body `{"valor": "50000", "data_alvo": "2029-06-15"}` → `SimulationResponse`; 422 se `valor ≤ 0` ou `data_alvo ≤ hoje`.
    - `GET /products` → `list[ProductData]` (manuais); `GET /products/tesouro` → títulos do snapshot como `ProductData`; `POST /products`, `PUT /products/{id}`, `DELETE /products/{id}`, `POST /products/{id}/duplicate`. Validação via `validate_product` ⇒ 422 `{"detail": [mensagens]}`.
    - `GET /settings`, `PUT /settings` (422 com erros pydantic legíveis), `POST /settings/reset`.
    - `GET /market` → `MarketSummary`; `POST /market/refresh` → força atualização.
    - `GET /health`.
  - Seed: os 13 produtos do design §9, `exemplo: true`, `id` fixo `exemplo-01`…`exemplo-13`, vencimento no dia 15 do mês indicado (Prefixado 03 em 2027-11-16; LCI 08 com `data_carencia` 2027-11-19). Valores mínimos: 01 1000 · 02 1000 · 03 5000 · 04 1000 · 05 5000 · 06 10000 · 07 1000 · 08 3000 · 09 1000 · 10 1000 · 11 1000 · 12 500 · 13 25000. Fundos: 12 `PCT_CDI 0.99`, adm `0.003`, `prazo_resgate_dias 0`, LONGO; 13 `CDI_MAIS 0.015`, adm `0.008`, prazo 30, LONGO.

- [ ] **Step 1: Testes que falham**

```python
def test_sections_and_ordering(): ...   # 3 produtos verdes com valores distintos saem em ordem desc; vermelho resgatável antes de não resgatável
def test_one_broken_product_does_not_break_all(): ...

def test_api_simulate_offline(client_fixtures):
    r = client_fixtures.post("/api/simulate", json={"valor": "50000", "data_alvo": "2029-06-15"})
    body = r.json(); assert r.status_code == 200
    assert body["vence_ate_data"] and isinstance(body["vence_ate_data"][0]["valor_liquido"], str)
    liq = [D(x["valor_liquido"]) for x in body["vence_ate_data"]]; assert liq == sorted(liq, reverse=True)
    assert any(x["product"]["tipo"].startswith("TESOURO") for x in body["vence_depois"] + body["vence_ate_data"])

def test_api_validation(client_fixtures):
    assert client_fixtures.post("/api/simulate", json={"valor": "0", "data_alvo": "2029-06-15"}).status_code == 422
    assert client_fixtures.post("/api/simulate", json={"valor": "100", "data_alvo": "2020-01-01"}).status_code == 422

def test_first_run_no_network_no_cache(tmp_path):                # Review Focus 1
    client = TestClient(create_app(tmp_path / "db.sqlite", fetchers=AlwaysFailFetchers()))
    body = client.post("/api/simulate", json={"valor": "50000", "data_alvo": "2029-06-15"}).json()
    assert set(body["mercado"]["errors"]) == {"bcb", "focus", "tesouro"}
    assert any(x["product"]["indexador"] == "PRE" for x in body["vence_ate_data"])
    assert all(any(a["code"] == "SEM_DADOS_MERCADO" for a in x["alertas"]) for x in body["indisponiveis"] if x["product"]["indexador"] != "PRE")

def test_products_crud_and_validation(client_fixtures): ...   # cria, edita, duplica, exclui; LCI com vencimento em 6 meses → 422 com mensagem
def test_settings_roundtrip_and_reset(client_fixtures): ...   # PUT custódia 0.0025 → GET reflete; valor inválido → 422; reset volta 0.0020
def test_seed_once(tmp_path): ...                             # 13 produtos; após excluir todos e reiniciar, não reimporta
```
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** `uv run pytest -q` → PASS (suite inteira).
- [ ] **Step 5:** Smoke manual: `LIQUIDO_MARKET_FIXTURES=tests/fixtures/market uv run uvicorn app.main:app` e `curl -s localhost:8000/api/simulate -d '{"valor":"50000","data_alvo":"2029-06-15"}' -H 'content-type: application/json' | head -c 400` → JSON com cards.
- [ ] **Step 6:** Commit `feat(api): simulação, produtos, configurações e mercado`.

---

### Task 9: Frontend — base, design system e Comparador

**Files:**
- Create: `frontend/` (Vite React TS), `src/main.tsx`, `src/App.tsx`, `src/api/{types,client}.ts`, `src/lib/{format,parse}.ts`, `src/components/{Layout,InputsBar,MarketStrip,Filters,ProductCard,AlertBadge,SectionHeader}.tsx`, `src/pages/Comparador.tsx`
- Test: `src/lib/format.test.ts`, `src/lib/parse.test.ts`, `src/components/ProductCard.test.tsx`

**Interfaces:**
- Consumes: contratos JSON da Task 8 (espelhar em `types.ts`; Decimal = `string`).
- Produces:
  - `formatBRL(v: string | null) -> string` (`"71840.1"` → `"R$ 71.840,10"`; null → `"—"`), `formatPct(fraction: string, digits = 2) -> string` (`"0.1365"` → `"13,65%"`), `formatDate(iso: string) -> string` (`"2029-06-15"` → `"15/06/2029"`).
  - `parseBRL(input: string) -> string | null`: `"50.000,00"→"50000.00"`, `"50000"→"50000"`, `"50.000"→"50000"`, `"1.234,5"→"1234.5"`, `"R$ 2.500,75"→"2500.75"`, `"abc"→null`, `"0"→"0"`. Regra: vírgula é o separador decimal; ponto é sempre milhar.
  - `api.simulate(valor, dataAlvo)`, `api.market()`, `api.refreshMarket()`, `api.products.*`, `api.settings.*` (fetch para `/api`, erros 422 viram `ApiError` com `messages: string[]`).
  - Layout: header com nome "Liquido" + navegação (Comparador, Produtos, Configurações, Mercado); no celular (< 640px) barra inferior fixa; toggle de tema (claro/escuro/sistema, `localStorage` em try/catch).
  - Comparador: `InputsBar` (valor com máscara BRL, data alvo `<input type="date">`, lembrados em `localStorage`), `MarketStrip` (Selic, CDI, IPCA 12m, "Atualizado em …", botão atualizar, banner de erro por fonte), `Filters` (tipo, plataforma, só FGC, só isentos — filtragem no cliente), seções "✅ Vencem até a sua data", "🔴 Vencem depois da sua data", "Indisponíveis para este valor" (cinza, recolhível). Recalcula com TanStack Query ao mudar inputs (debounce 400 ms).
  - `ProductCard`: posição `#n` (só verdes), nome, plataforma, tipo, indexação legível (`"112% do CDI"`, `"IPCA + 7,00%"`, `"Pré 14,20%"`, `"CDI + 1,20%"`), vencimento, isenção, líquido grande, `+x%`, `≈ y% a.a. líquido`, badges de alerta (ícone + texto curto; `PROJECAO` âmbar, `ESTIMATIVA_MERCADO` âmbar, `NAO_RESGATAVEL` vermelho, `EXEMPLO` cinza). Borda/realce vermelho na seção vermelha. Clique abre detalhe (Task 10).

- [ ] **Step 1:** `npm create vite@5 frontend -- --template react-ts`, fixe as versões do Tech Stack, configure Tailwind, Vitest (jsdom, @testing-library/react) e proxy `/api → http://127.0.0.1:8000`.
- [ ] **Step 2: Testes que falham**

```ts
test.each([["50.000,00","50000.00"],["50000","50000"],["50.000","50000"],["1.234,5","1234.5"],["R$ 2.500,75","2500.75"],["abc",null]])
  ("parseBRL(%s)", (i, o) => expect(parseBRL(i)).toBe(o));                        // Review Focus 5
test("formatBRL", () => { expect(formatBRL("71840.1")).toBe("R$ 71.840,10"); expect(formatBRL(null)).toBe("—"); });
test("formatPct", () => expect(formatPct("0.1365")).toBe("13,65%"));
test("ProductCard mostra alerta de projeção e posição", () => {
  render(<ProductCard result={fixtureResult} rank={1} />);
  expect(screen.getByText("#1")).toBeInTheDocument();
  expect(screen.getByText(/Depende de projeção/)).toBeInTheDocument();
  expect(screen.getByText("R$ 71.840,10")).toBeInTheDocument();
});
```
(normalize o espaço não separável de `Intl.NumberFormat` para espaço comum em `formatBRL`.)
- [ ] **Step 3:** `npm test` → FAIL. **Step 4:** Implementar. **Step 5:** `npm test && npm run build` → PASS.
- [ ] **Step 6:** Verificação visual: backend com fixtures + `npm run dev`; screenshot Playwright em 1280×800 e iPhone 13; conferir os três blocos e o tema escuro.
- [ ] **Step 7:** Commit `feat(frontend): comparador com cards ranqueados`.

---

### Task 10: Detalhe do produto

**Files:**
- Create: `frontend/src/components/ProductDetail.tsx`, `frontend/src/components/EvolutionChart.tsx`
- Modify: `frontend/src/pages/Comparador.tsx`
- Test: `frontend/src/components/ProductDetail.test.tsx`

**Interfaces:**
- Produces: `<ProductDetail result open onOpenChange />` (Radix Dialog; gaveta lateral no desktop, folha inferior em tela cheia no celular). Conteúdo: cabeçalho do produto; decomposição em linhas `Valor investido → Rendimento bruto → IOF → IR → Custódia → Come-cotas → Taxa de adm. → Valor líquido` (omitindo linhas zeradas); datas (aplicação, saída, solicitação de resgate, dias parado); premissas ("Projeção: Focus 13/11/2026 — Selic 12,75% em 2027…"); lista completa de alertas com mensagem; `EvolutionChart` (Recharts, área do `serie.valor_bruto`, eixo em datas pt-BR, tooltip BRL, cores via tokens CSS para os dois temas).

- [ ] **Step 1: Teste que falha:** renderiza com `fixtureResult` (CDB com IR e IOF zero) ⇒ mostra "IR" com `R$ 264,42`, **não** mostra linha "IOF", mostra "Premissas".
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** `npm test` PASS.
- [ ] **Step 5:** Commit `feat(frontend): detalhe do produto com decomposição e gráfico`.

---

### Task 11: Página de Produtos (cadastro)

**Files:**
- Create: `frontend/src/pages/Produtos.tsx`, `frontend/src/components/ProductForm.tsx`
- Test: `frontend/src/components/ProductForm.test.tsx`

**Interfaces:**
- Produces:
  - Lista dos produtos manuais (cartões compactos): switch ativo/inativo (PUT imediato), editar, duplicar, excluir (confirmação). Seção "Tesouro Direto (automático)" somente leitura a partir de `GET /products/tesouro`, com data base.
  - `ProductForm` dinâmico por `tipo`: comuns (nome, emissor, plataforma com sugestões XP/BTG, indexador, taxa, vencimento, valor mínimo, liquidez, carência, observações); FUNDO_RF troca vencimento/liquidez por taxa de adm., prazo de resgate (D+N) e classe tributária, e restringe indexador a % CDI e CDI +. Campo taxa com rótulo e sufixo que mudam por indexador (`% do CDI`, `% a.a.`, `IPCA + % a.a.`); usuário digita em % (`112`, `14,2`) e o form converte para fração. LCI/LCA escondem "Diária". Erros 422 do backend exibidos no topo e junto ao campo quando identificável.

- [ ] **Step 1: Testes que falham:** (a) escolher `FUNDO_RF` mostra "Taxa de administração" e esconde "Vencimento"; (b) indexador `PCT_CDI` + digitar `112` envia `taxa: "1.12"`; (c) `PRE` + `14,2` envia `"0.142"`; (d) LCI não oferece liquidez "Diária"; (e) resposta 422 mostra a mensagem.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(frontend): cadastro de produtos`.

---

### Task 12: Configurações e Mercado

**Files:**
- Create: `frontend/src/pages/Configuracoes.tsx`, `frontend/src/pages/Mercado.tsx`
- Test: `frontend/src/pages/Configuracoes.test.tsx`

**Interfaces:**
- Produces:
  - Configurações em grupos (cards): **Tributação** (tabela IR editável, tabela IOF 1–29 recolhível, come-cotas LP/CP, isenções de IR e IOF por tipo em checkboxes), **Custos** (custódia B3 % a.a., isenção Tesouro Selic R$), **Projeções** (Focus | Manual; no manual, tabela ano → Selic %, IPCA % com adicionar/remover linha; spread CDI–Selic em p.p.), **Dados** (TTL em horas; última atualização e erro por fonte; botão "Atualizar agora"), **Alertas** (limite FGC R$). Percentuais exibidos/editados em % e enviados como fração. Botões "Salvar" (habilitado só com alterações) e "Restaurar padrões" (confirmação). Erros 422 exibidos por campo.
  - Mercado: Selic meta, CDI, IPCA 12m com datas; tabela de projeção por ano (`yearly_table`) e gráfico de linhas Selic/IPCA; fonte da projeção; data base do Tesouro.

- [ ] **Step 1: Testes que falham:** (a) editar custódia para `0,25` e salvar envia `custodia_b3_aa: "0.0025"`; (b) "Salvar" desabilitado sem alterações; (c) modo Manual exibe tabela de anos; (d) 422 exibe a mensagem.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(frontend): configurações e painel de mercado`.

---

### Task 13: PWA, servir pelo FastAPI, deploy e e2e

**Files:**
- Modify: `frontend/vite.config.ts` (vite-plugin-pwa), `backend/app/main.py` (static + SPA fallback)
- Create: `frontend/public/icons/{icon.svg,icon-192.png,icon-512.png,apple-touch-icon.png}`, `frontend/e2e/comparador.spec.ts`, `frontend/playwright.config.ts`, `deploy/liquido.service`, `deploy/install.sh`, `deploy/update.sh`, `README.md`
- Test: `backend/tests/api/test_static.py`, `frontend/e2e/comparador.spec.ts`

**Interfaces:**
- Produces:
  - PWA: manifest `name "Liquido — Renda Fixa"`, `short_name "Liquido"`, `display "standalone"`, `lang "pt-BR"`, ícones; `apple-mobile-web-app-capable` e `theme-color` no `index.html`; service worker com cache do shell e **network-first para `/api`** (nunca servir simulação antiga sem rede sem indicar).
  - FastAPI: se `static_dir` existir, serve arquivos e devolve `index.html` para qualquer GET fora de `/api/*` sem arquivo correspondente; `/api/*` inexistente continua 404 JSON.
  - `deploy/liquido.service`: `ExecStart={APP_DIR}/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000`, `WorkingDirectory={APP_DIR}/backend`, `User={USER}`, `Environment=LIQUIDO_DB={APP_DIR}/backend/data/liquido.db`, `Restart=on-failure`.
  - `install.sh` (idempotente; pede sudo só para systemd): checa `uv`, `node ≥ 20`, `tailscale`; `uv sync --frozen`; `npm ci && npm run build`; renderiza o unit com `APP_DIR` e `USER`; `systemctl enable --now liquido`; `tailscale serve --bg 8000`; imprime a URL `https://<host>.<tailnet>.ts.net`.
  - `update.sh`: `git pull --ff-only` → `uv sync --frozen` → `npm ci && npm run build` → `sudo systemctl restart liquido` → `curl -fsS localhost:8000/api/health`.
  - README (pt-BR): o que é, requisitos, instalação, atualização, backup (`backend/data/liquido.db`), como adicionar ao iPhone (Safari → Compartilhar → Adicionar à Tela de Início), desenvolvimento local, onde ficam as configurações.

- [ ] **Step 1: Testes que falham:** `test_static.py` — com `static_dir` temporário contendo `index.html`, `GET /produtos` → 200 com o HTML; `GET /api/nao-existe` → 404 JSON. E2E (`playwright.config.ts` sobe o backend com `LIQUIDO_MARKET_FIXTURES` e DB temporário servindo o build): preencher `50.000,00` e uma data em 2029 → aparecem ≥ 3 cards na seção verde com `#1`; abrir o primeiro card → "Valor líquido" visível; ir a Configurações, mudar custódia, salvar, voltar → sem erro; viewport iPhone 13 mostra a barra inferior.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** `uv run pytest -q` e `npx playwright test --trace off` → PASS.
- [ ] **Step 5:** `bash -n deploy/*.sh` sem erro; `systemd-analyze verify` do unit renderizado, se disponível.
- [ ] **Step 6:** Commit `feat: PWA, deploy nativo com systemd e testes e2e`.

---

## Revisão final (após a Task 13)

Revisão de toda a branch contra o design (Opus): cobertura das seções 6–11 do design, consistência de nomes entre backend e `types.ts`, e uma simulação de ponta a ponta com dados reais (sem fixtures) conferindo um CDB e um Tesouro Prefixado à mão.
