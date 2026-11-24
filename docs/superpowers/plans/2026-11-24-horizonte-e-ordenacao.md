# Horizonte da simulação e modos de ordenação — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Execução (definida no `CLAUDE.md`):** subagent-driven. Implementador = subagente **Sonnet**; revisor por
> tarefa = subagente **Haiku**; orquestração e todo `.md` = Opus. Cada implementador recebe: a tarefa
> inteira, "Global Constraints", "Review Focus" e `CLAUDE.md`.

**Goal:** Permitir simular sem data (cada produto até o seu horizonte natural), em 1 ano, em 2 anos ou numa
data livre, e ordenar os resultados por valor líquido, taxa líquida a.a., custo-benefício, menor prazo de
saída ou segurança.

**Architecture:** O backend ganha um módulo de domínio puro (`domain/horizon.py`) que calcula datas de
1/2 anos, o prazo de saída e o horizonte natural de cada produto; `simulate_all` passa a preencher
`prazo_saida_dias` e surge `simulate_sem_data`. A API aceita `horizonte` e devolve a data resolvida. O
frontend ordena e calcula dominância **sobre a lista já filtrada** (`lib/ordering.ts`), só comparando valores.

**Tech Stack:** o existente (FastAPI, pydantic v2, React/Vite/TS/Tailwind, react-query, vitest, Playwright).
Nenhuma dependência nova.

**Spec:** `docs/superpowers/specs/2026-11-24-horizonte-e-ordenacao-design.md` (resto do sistema:
`docs/superpowers/specs/2026-11-19-comparador-renda-fixa-design.md`).

## Global Constraints

- Regras inegociáveis do `CLAUDE.md`: `Decimal` no backend; taxas como fração; dias úteis ANBIMA para
  acumular, **dias corridos** para IR/IOF e para `prazo_saida_dias`; Decimal como string na API; testes
  sem rede; TDD; commits `tipo(escopo): descrição` terminando com
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Código em inglês; campos e termos do domínio em português. UI 100% pt-BR (`R$ 1.234,56`, `dd/mm/aaaa`,
  `13,65%`).
- Branch: `claude/horizonte-ordenacao`.
- Nenhuma regra de cálculo de rendimento, IR, IOF, custódia ou come-cotas muda. O baseline
  `tests/api/test_simulate_regression.py` continua passando sem alterar `golden_simulate.json`.
- "1 ano" = mesmo dia/mês do ano seguinte (29/02 → 28/02), depois `cal.adjust_next`. "2 anos" idem com +2.
- Valores de `horizonte`: `"SEM_DATA" | "UM_ANO" | "DOIS_ANOS" | "DATA"`; padrão `"DATA"`.
- Valores de ordenação (frontend): `"VALOR_LIQUIDO" | "TAXA" | "CUSTO_BENEFICIO" | "PRAZO" | "SEGURANCA"`.
- Frontend não faz aritmética com dinheiro/taxas: só compara (`Number(a) - Number(b)` para ordenar é aceito).
- Alertas: Tesouro vendido antes do vencimento continua com `ESTIMATIVA_MERCADO`; pós-fixados com `PROJECAO`
  (nada a fazer: os produtos já emitem).

## Review Focus

1. **Data de 1/2 anos caindo em fim de semana, feriado ou partindo de 29/02** → vai para o próximo dia útil
   e fica sempre > 360 / > 720 dias corridos de hoje. (teste na Task 1)
2. **Filtro ativo escondendo o produto que "domina"** (ex.: "Só isentos" esconde o CDB que domina uma LCI)
   → a LCI não recebe o selo. (testes nas Tasks 4 e 5)
3. **Resultados sem `taxa_liquida_aa` ou sem `prazo_saida_dias`** (ex.: não resgatáveis) → nunca dominam nem
   são dominados, vão para o fim na ordenação, sem erro. (teste na Task 4)
4. **`localStorage` com valor antigo/inválido de horizonte ou ordenação, ou ordenação "valor líquido" salva
   ao entrar em sem data** → cai no padrão do modo (`DATA` / `TAXA`), sem tela quebrada. (teste na Task 5)
5. **Cliente antigo sem `horizonte`, ou `DATA` sem `data_alvo`** → o primeiro se comporta exatamente como
   hoje; o segundo recebe 422 com `["Informe a data de resgate"]`. (teste na Task 3)

---

## Estrutura de arquivos

```
backend/app/domain/horizon.py              # NOVO: anos_a_frente, prazo_saida_dias, horizonte_natural
backend/app/domain/products/base.py        # SimulationResult.prazo_saida_dias
backend/app/domain/simulation.py           # preenche prazo; simulate_sem_data; SimulationResponse
backend/app/api/simulate.py                # horizonte na requisição; data_alvo/horizonte na resposta
backend/tests/domain/test_horizon.py       # NOVO
backend/tests/domain/test_simulation.py
backend/tests/api/test_simulate_horizonte.py  # NOVO
frontend/src/api/{types,client}.ts
frontend/src/lib/ordering.ts (+ .test.ts)  # NOVO: ordenar, dominados
frontend/src/lib/labels.ts (+ .test.ts)    # prazoSaidaLabel, ORDENACOES, HORIZONTES
frontend/src/components/InputsBar.tsx      # seletor de horizonte
frontend/src/components/SortSelect.tsx     # NOVO
frontend/src/components/ProductCard.tsx    # destaque taxa, prazo, selo dominado
frontend/src/pages/Comparador.tsx (+ .test.tsx)
frontend/e2e/comparador.spec.ts
```

---

### Task 1: Domínio — datas de horizonte e prazo de saída

**Files:**
- Create: `backend/app/domain/horizon.py`
- Test: `backend/tests/domain/test_horizon.py`

**Interfaces:**
- Consumes: `ProductData`, `ProductType`, `Liquidity` (`app/domain/products/base.py`); `BusinessCalendar.adjust_next`.
- Produces:
  - `anos_a_frente(today: date, anos: int, cal: BusinessCalendar) -> date`
  - `prazo_saida_dias(d: ProductData, today: date, cal: BusinessCalendar) -> int`
  - `horizonte_natural(d: ProductData, today: date, cal: BusinessCalendar) -> date`

Regras (do spec):

| Caso | `prazo_saida_dias` | `horizonte_natural` |
|---|---|---|
| `FUNDO_RF` | `prazo_resgate_dias or 0` | `max(um_ano, cal.adjust_next(today + prazo_resgate_dias + 1 dia))` |
| `TESOURO_SELIC` | 0 | `min(venc, um_ano)` |
| demais `TESOURO_*` | `(venc - today).days` | `venc` |
| bancário `DIARIA` | 0 | `min(venc, um_ano)` |
| bancário `DIARIA_APOS_CARENCIA` | `max(0, (data_carencia - today).days)`; sem `data_carencia` → como `NO_VENCIMENTO` | `min(venc, max(data_carencia, um_ano))` |
| bancário `NO_VENCIMENTO` (inclui CRI/CRA) | `(venc - today).days` | `venc` |

Onde `venc = cal.adjust_next(d.data_vencimento)` e `um_ano = anos_a_frente(today, 1, cal)`. O fundo usa
`max(...)` para que `prazo_resgate_dias` > 1 ano continue resgatável.

- [ ] **Step 1: Write the failing tests** (use `cal`, `make` e `TODAY = date(2026, 11, 19)` de `tests/domain/products/product_helpers.py`)

```python
def test_anos_a_frente_mesmo_dia_ajustado():
    assert anos_a_frente(TODAY, 1, cal) == cal.adjust_next(date(2027, 11, 19))
    d2 = anos_a_frente(TODAY, 2, cal)  # 19/11/2028 é domingo e 20/11 é feriado
    assert d2 == cal.adjust_next(date(2028, 11, 19)) and d2 > date(2028, 11, 20)

def test_anos_a_frente_29_fev_e_faixas_ir():
    hoje = date(2028, 2, 29)
    um, dois = anos_a_frente(hoje, 1, cal), anos_a_frente(hoje, 2, cal)
    assert um == cal.adjust_next(date(2029, 2, 28)) and (um - hoje).days > 360
    assert dois == cal.adjust_next(date(2030, 2, 28)) and (dois - hoje).days > 720

@pytest.mark.parametrize("hoje", [date(2026, 11, 19), date(2026, 12, 24), date(2027, 1, 2), date(2028, 2, 29)])
def test_anos_a_frente_sempre_dia_util_e_acima_das_faixas(hoje):
    um, dois = anos_a_frente(hoje, 1, cal), anos_a_frente(hoje, 2, cal)
    assert cal.is_business_day(um) and cal.is_business_day(dois)
    assert (um - hoje).days > 360 and (dois - hoje).days > 720

def test_prazo_saida():
    venc = date(2030, 11, 18)
    dias_venc = (cal.adjust_next(venc) - TODAY).days
    assert prazo_saida_dias(make(liquidez=Liquidity.DIARIA, data_vencimento=venc), TODAY, cal) == 0
    assert prazo_saida_dias(make(data_vencimento=venc), TODAY, cal) == dias_venc
    car = make(liquidez=Liquidity.DIARIA_APOS_CARENCIA, data_vencimento=venc, data_carencia=date(2027, 5, 19))
    assert prazo_saida_dias(car, TODAY, cal) == (date(2027, 5, 19) - TODAY).days
    car_passada = car.model_copy(update={"data_carencia": date(2026, 1, 1)})
    assert prazo_saida_dias(car_passada, TODAY, cal) == 0
    fundo = make(tipo=ProductType.FUNDO_RF, data_vencimento=None, liquidez=Liquidity.DIARIA, prazo_resgate_dias=30)
    assert prazo_saida_dias(fundo, TODAY, cal) == 30
    selic = make(tipo=ProductType.TESOURO_SELIC, indexador=Indexer.SELIC, data_vencimento=venc)
    assert prazo_saida_dias(selic, TODAY, cal) == 0
    ipca = make(tipo=ProductType.TESOURO_IPCA, indexador=Indexer.IPCA_MAIS, data_vencimento=venc)
    assert prazo_saida_dias(ipca, TODAY, cal) == dias_venc

def test_horizonte_natural():
    um_ano = anos_a_frente(TODAY, 1, cal)
    longe, perto = date(2031, 11, 17), date(2027, 3, 15)
    assert horizonte_natural(make(data_vencimento=longe), TODAY, cal) == cal.adjust_next(longe)
    assert horizonte_natural(make(liquidez=Liquidity.DIARIA, data_vencimento=longe), TODAY, cal) == um_ano
    assert horizonte_natural(make(liquidez=Liquidity.DIARIA, data_vencimento=perto), TODAY, cal) == cal.adjust_next(perto)
    car = make(liquidez=Liquidity.DIARIA_APOS_CARENCIA, data_vencimento=longe, data_carencia=date(2028, 6, 1))
    assert horizonte_natural(car, TODAY, cal) == date(2028, 6, 1)  # carência depois de 1 ano
    fundo = make(tipo=ProductType.FUNDO_RF, data_vencimento=None, liquidez=Liquidity.DIARIA, prazo_resgate_dias=30)
    assert horizonte_natural(fundo, TODAY, cal) == um_ano
    fundo_longo = fundo.model_copy(update={"prazo_resgate_dias": 400})
    assert horizonte_natural(fundo_longo, TODAY, cal) == cal.adjust_next(TODAY + timedelta(days=401))
    selic = make(tipo=ProductType.TESOURO_SELIC, indexador=Indexer.SELIC, data_vencimento=longe)
    assert horizonte_natural(selic, TODAY, cal) == um_ano
```

Se `make(...)` rejeitar alguma combinação (validação de `ProductData`), ajuste só os campos acessórios
(ex.: `taxa`, `indexador`), nunca a regra testada. A data de carência `2028-06-01` deve ser dia útil; se não
for, troque por um dia útil próximo e mantenha a asserção.

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/domain/test_horizon.py -q`
Expected: FAIL (`ModuleNotFoundError: app.domain.horizon`)

- [ ] **Step 3: Implement the three functions in `backend/app/domain/horizon.py`** following the table above.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest tests/domain/test_horizon.py -q`
Expected: PASS

- [ ] **Step 5: Commit** — `feat(dominio): datas de 1/2 anos, prazo de saída e horizonte natural`

---

### Task 2: Simulação — `prazo_saida_dias` nos resultados e `simulate_sem_data`

**Files:**
- Modify: `backend/app/domain/products/base.py` (`SimulationResult`)
- Modify: `backend/app/domain/simulation.py`
- Test: `backend/tests/domain/test_simulation.py`

**Interfaces:**
- Consumes: Task 1 (`prazo_saida_dias`, `horizonte_natural`).
- Produces:
  - `SimulationResult.prazo_saida_dias: int | None = None`
  - `simulate_all(...)` (assinatura inalterada) preenche `prazo_saida_dias` em todo resultado cuja `secao != INDISPONIVEL`.
  - `simulate_sem_data(products: list[Product], valor: Decimal, ctx: SimContext) -> tuple[list[SimulationResult], list[SimulationResult], list[SimulationResult]]`
    — mesma tripla `(ate, depois, indisp)`. Cada produto simulado com `data_alvo = horizonte_natural(p.data, ctx.today, ctx.cal)`
    via `_safe_simulate`. Resultados resgatáveis (de `VENCE_ATE_DATA` **ou** `VENCE_DEPOIS`) vão juntos para `ate`,
    ordenados por `taxa_liquida_aa` desc (nulos por último), desempate por nome; não resgatáveis (defensivo) em
    `depois`, ordenados por vencimento; indisponíveis por nome. Todos com `prazo_saida_dias` preenchido (exceto indisponíveis).

- [ ] **Step 1: Write the failing tests**

```python
def test_simulate_all_preenche_prazo_saida():
    diaria = _p("d", liquidez=Liquidity.DIARIA, data_vencimento=date(2031, 11, 14))
    presa = _p("p", data_vencimento=date(2028, 11, 16))
    abaixo = _p("z", valor_minimo=D("999999"))
    ate, depois, indisp = simulate_all([diaria, presa, abaixo], D("50000"), ALVO, ctx)
    por_id = {r.product.id: r for r in ate + depois + indisp}
    assert por_id["d"].prazo_saida_dias == 0
    assert por_id["p"].prazo_saida_dias == (cal.adjust_next(date(2028, 11, 16)) - TODAY).days
    assert por_id["z"].prazo_saida_dias is None

def test_sem_data_simula_cada_um_ate_o_seu_horizonte():
    longo = _p("longo", indexador=Indexer.PRE, taxa=D("0.13"), data_vencimento=date(2031, 11, 17))
    curto = _p("curto", indexador=Indexer.PRE, taxa=D("0.12"), data_vencimento=date(2027, 11, 22))
    diaria = _p("diaria", liquidez=Liquidity.DIARIA, data_vencimento=date(2031, 11, 17))
    ate, depois, indisp = simulate_sem_data([curto, diaria, longo], D("50000"), ctx)
    assert depois == [] and indisp == []
    por_id = {r.product.id: r for r in ate}
    assert por_id["longo"].data_saida == cal.adjust_next(date(2031, 11, 17))
    assert por_id["diaria"].data_saida == anos_a_frente(TODAY, 1, cal)
    taxas = [r.taxa_liquida_aa for r in ate]
    assert taxas == sorted(taxas, reverse=True)
    assert ate[0].product.id == "longo"  # pré 13% com IR 15% supera os demais
    assert all(r.prazo_saida_dias is not None for r in ate)

def test_sem_data_produto_quebrado_vai_para_indisponiveis():
    # reaproveite a classe Broken de test_one_broken_product_does_not_break_all (extraia para o módulo)
    ate, depois, indisp = simulate_sem_data([Broken(), _p("ok")], D("50000"), ctx)
    assert [r.product.id for r in ate] == ["ok"] and [r.product.id for r in indisp] == ["quebrado"]
```

Importe `cal`, `TODAY` de `product_helpers` e `anos_a_frente` de `app.domain.horizon`. Se a asserção
`ate[0].product.id == "longo"` não valer com a projeção do `ctx` de teste (CDI 13,65%), troque as taxas do
teste, não a regra de ordenação.

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/domain/test_simulation.py -q`
Expected: FAIL (`ImportError: simulate_sem_data` / atributo `prazo_saida_dias` ausente)

- [ ] **Step 3: Implement** — campo em `SimulationResult`; em `simulation.py` um helper privado que atribui
  `prazo_saida_dias` a um resultado não indisponível, usado por `simulate_all` e `simulate_sem_data`.

- [ ] **Step 4: Run backend suite**

Run: `cd backend && uv run pytest -q`
Expected: PASS (inclusive `test_simulate_regression.py`, sem mudar o golden)

- [ ] **Step 5: Commit** — `feat(simulacao): prazo de saída nos resultados e simulação sem data`

---

### Task 3: API — `horizonte` na requisição, data resolvida na resposta

**Files:**
- Modify: `backend/app/api/simulate.py`, `backend/app/domain/simulation.py` (`SimulationResponse`)
- Test: `backend/tests/api/test_simulate_horizonte.py` (fixture `client_fixtures`, `TODAY = 2026-11-19`)

**Interfaces:**
- Consumes: Task 1 (`anos_a_frente`), Task 2 (`simulate_sem_data`, `simulate_all`).
- Produces (contrato HTTP que o frontend usa):
  - Request: `{ "valor": str, "horizonte"?: "SEM_DATA"|"UM_ANO"|"DOIS_ANOS"|"DATA" (padrão "DATA"), "data_alvo"?: "YYYY-MM-DD" }`
  - `Horizonte(StrEnum)` em `app/domain/horizon.py` com esses quatro valores.
  - `SimulationResponse` ganha `horizonte: Horizonte` e `data_alvo: date | None` (nula só em `SEM_DATA`).
  - Erros 422 (lista de strings pt-BR): `DATA` sem `data_alvo` → `["Informe a data de resgate"]`;
    `DATA` com `data_alvo <= hoje` → `["A data de resgate deve ser posterior a hoje"]` (mensagem atual).
    Em `UM_ANO`/`DOIS_ANOS`/`SEM_DATA`, `data_alvo` enviada é ignorada.

- [ ] **Step 1: Write the failing tests**

```python
def _post(client, **body):
    return client.post("/api/simulate", json={"valor": "50000", **body})

def test_um_e_dois_anos_resolvem_a_data(client_fixtures):
    cal = get_calendar()
    for h, anos in (("UM_ANO", 1), ("DOIS_ANOS", 2)):
        body = _post(client_fixtures, horizonte=h, data_alvo="2020-01-01").json()
        esperado = anos_a_frente(TODAY, anos, cal)
        assert body["horizonte"] == h and body["data_alvo"] == esperado.isoformat()
        direto = _post(client_fixtures, data_alvo=esperado.isoformat()).json()
        assert [r["valor_liquido"] for r in body["vence_ate_data"]] == [r["valor_liquido"] for r in direto["vence_ate_data"]]

def test_sem_data(client_fixtures):
    body = _post(client_fixtures, horizonte="SEM_DATA").json()
    assert body["horizonte"] == "SEM_DATA" and body["data_alvo"] is None
    assert body["vence_ate_data"] and body["vence_depois"] == []
    assert all(r["prazo_saida_dias"] is not None for r in body["vence_ate_data"])
    taxas = [D(r["taxa_liquida_aa"]) for r in body["vence_ate_data"] if r["taxa_liquida_aa"] is not None]
    assert taxas == sorted(taxas, reverse=True)
    selic = [r for r in body["vence_ate_data"] if r["product"]["tipo"] == "TESOURO_SELIC"]
    assert selic and all("ESTIMATIVA_MERCADO" in {a["code"] for a in r["alertas"]} for r in selic)

def test_cliente_antigo_e_validacao(client_fixtures):
    antigo = _post(client_fixtures, data_alvo="2029-06-15").json()
    assert antigo["horizonte"] == "DATA" and antigo["data_alvo"] == "2029-06-15"
    r = _post(client_fixtures, horizonte="DATA")
    assert r.status_code == 422 and r.json()["detail"] == ["Informe a data de resgate"]
    r = _post(client_fixtures, horizonte="DATA", data_alvo="2026-11-19")
    assert r.status_code == 422 and r.json()["detail"] == ["A data de resgate deve ser posterior a hoje"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_simulate_horizonte.py -q`
Expected: FAIL (`KeyError: 'horizonte'`)

- [ ] **Step 3: Implement** — `SimulationRequest.data_alvo: date | None = None`, `horizonte: Horizonte = Horizonte.DATA`;
  o endpoint resolve a data com `c.today_fn()` e o calendário do `ctx` e chama `simulate_sem_data` ou `simulate_all`.

- [ ] **Step 4: Run backend suite**

Run: `cd backend && uv run pytest -q`
Expected: PASS (inclusive `test_api.py::test_api_validation` e o golden)

- [ ] **Step 5: Commit** — `feat(api): horizonte da simulação (sem data, 1 ano, 2 anos, data)`

---

### Task 4: Frontend — contrato, ordenação, dominância e rótulos

**Files:**
- Modify: `frontend/src/api/types.ts`, `frontend/src/api/client.ts` (+ `client.test.ts`)
- Create: `frontend/src/lib/ordering.ts`, `frontend/src/lib/ordering.test.ts`
- Modify: `frontend/src/lib/labels.ts` (+ `labels.test.ts`), `frontend/src/test/fixtures.ts`

**Interfaces:**
- Consumes: contrato da Task 3.
- Produces:
  - `types.ts`: `export type Horizonte = "SEM_DATA" | "UM_ANO" | "DOIS_ANOS" | "DATA"`;
    `SimulationResult.prazo_saida_dias: number | null`; `SimulationResponse.horizonte: Horizonte`, `data_alvo: string | null`.
  - `client.ts`: `api.simulate(valor: string, horizonte: Horizonte, dataAlvo: string | null, signal?: AbortSignal)`
    — envia `data_alvo` só quando `horizonte === "DATA"`.
  - `ordering.ts`:
    - `export type Ordenacao = "VALOR_LIQUIDO" | "TAXA" | "CUSTO_BENEFICIO" | "PRAZO" | "SEGURANCA"`
    - `export function dominados(list: SimulationResult[]): Set<string>` — ids de produtos dominados (regra do spec;
      só entre resultados com `resgatavel`, `taxa_liquida_aa` e `prazo_saida_dias` não nulos).
    - `export function ordenar(list: SimulationResult[], ord: Ordenacao): SimulationResult[]` — nova lista; não muta.
      Resultados não resgatáveis ficam no fim na ordem original; campo necessário nulo vai para o fim do bloco
      resgatável; desempate final por `product.nome` (`localeCompare(..., "pt-BR")`).
      - `VALOR_LIQUIDO`: valor líquido desc, depois taxa desc.
      - `TAXA`: taxa desc.
      - `CUSTO_BENEFICIO`: não dominados por prazo asc (desempate taxa desc), depois dominados por taxa desc.
      - `PRAZO`: prazo asc, depois taxa desc.
      - `SEGURANCA`: cobertura `TESOURO` > `FGC` > `NENHUMA`, depois taxa desc.
  - `labels.ts`:
    - `export const ORDENACOES: { id: Ordenacao; label: string }[]` com rótulos exatos: "Valor líquido",
      "Taxa líquida a.a.", "Custo-benefício", "Menor prazo de saída", "Segurança".
    - `export const HORIZONTES: { id: Horizonte; label: string }[]`: "Sem data", "1 ano", "2 anos", "Escolher data".
    - `export function prazoSaidaLabel(r: SimulationResult, hoje: string): string | null` (`hoje` em ISO):
      `null` se `prazo_saida_dias === null`; fundo → `"D+N"` (N = `prazo_resgate_dias ?? 0`; N=0 → "Liquidez diária");
      `TESOURO_SELIC` ou bancário `DIARIA` → "Liquidez diária"; `DIARIA_APOS_CARENCIA` com carência > hoje →
      "Carência até dd/mm/aaaa", senão "Liquidez diária"; demais `TESOURO_*` → "Venda antes de dd/mm/aaaa a preço de mercado"
      (data = vencimento); demais bancários → "Preso até dd/mm/aaaa" (vencimento).

- [ ] **Step 1: Write the failing tests** (`ordering.test.ts`, com um helper `r(id, {taxa, prazo, valor, cobertura, resgatavel})`
  que estende `fixtureResult`)

```ts
test("dominância: paga mais e prende menos", () => {
  const a = r("A", { taxa: "0.128", prazo: 730 }), b = r("B", { taxa: "0.125", prazo: 1460 });
  const c = r("C", { taxa: "0.131", prazo: 1460 }), d = r("D", { taxa: "0.128", prazo: 730 });
  expect([...dominados([a, b, c, d])]).toEqual(["B"]); // empate exato A×D não domina
});
test("dominância só sobre a lista recebida (filtrada)", () => {
  const lci = r("LCI", { taxa: "0.11", prazo: 365 }), cdb = r("CDB", { taxa: "0.12", prazo: 365 });
  expect(dominados([lci, cdb]).has("LCI")).toBe(true);
  expect(dominados([lci]).size).toBe(0);
});
test("nulos e não resgatáveis não dominam nem são dominados e vão para o fim", () => {
  const ok = r("ok", { taxa: "0.12", prazo: 0 }), semTaxa = r("semTaxa", { taxa: null, prazo: 0 });
  const preso = r("preso", { taxa: null, prazo: null, resgatavel: false });
  expect(dominados([ok, semTaxa, preso]).size).toBe(0);
  for (const o of ["VALOR_LIQUIDO", "TAXA", "CUSTO_BENEFICIO", "PRAZO", "SEGURANCA"] as const) {
    expect(ordenar([preso, semTaxa, ok], o).map((x) => x.product.id)).toEqual(["ok", "semTaxa", "preso"]);
  }
});
test("custo-benefício forma a escada e manda dominados para o fim", () => {
  const lista = [r("X", { taxa: "0.131", prazo: 1460 }), r("Ruim", { taxa: "0.115", prazo: 900 }),
    r("Y", { taxa: "0.114", prazo: 0 }), r("W", { taxa: "0.123", prazo: 365 })];
  expect(ordenar(lista, "CUSTO_BENEFICIO").map((x) => x.product.id)).toEqual(["Y", "W", "X", "Ruim"]);
});
test("segurança e prazo", () => {
  const t = r("T", { taxa: "0.10", prazo: 3000, cobertura: "TESOURO" }), f = r("F", { taxa: "0.12", prazo: 0, cobertura: "FGC" });
  const n = r("N", { taxa: "0.14", prazo: 30, cobertura: "NENHUMA" });
  expect(ordenar([n, f, t], "SEGURANCA").map((x) => x.product.id)).toEqual(["T", "F", "N"]);
  expect(ordenar([t, n, f], "PRAZO").map((x) => x.product.id)).toEqual(["F", "N", "T"]);
});
test("não muta a entrada", () => { const l = [r("b", { taxa: "0.1", prazo: 1 }), r("a", { taxa: "0.2", prazo: 1 })];
  const copia = [...l]; ordenar(l, "TAXA"); expect(l).toEqual(copia); });
```

  E em `labels.test.ts`, um caso por linha da regra de `prazoSaidaLabel` (ex.: `"Preso até 16/11/2028"`,
  `"Carência até 19/05/2027"`, `"D+30"`, `"Liquidez diária"`, `"Venda antes de 15/05/2035 a preço de mercado"`).
  Em `client.test.ts`: `horizonte "UM_ANO"` envia `{ valor, horizonte: "UM_ANO" }` sem `data_alvo`; `"DATA"` envia `data_alvo`.
  Em `fixtures.ts`: `fixtureResult.prazo_saida_dias = 730`; `fixtureResponse.horizonte = "DATA"`, `data_alvo = "2029-06-15"`.

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/lib src/api`
Expected: FAIL (módulo `ordering` inexistente; `prazoSaidaLabel` indefinido)

- [ ] **Step 3: Implement** types, client, `ordering.ts` and labels as specified.

- [ ] **Step 4: Run frontend checks**

Run: `cd frontend && npm test && npx tsc --noEmit -p .`
Expected: PASS. Chamadas existentes a `api.simulate` que quebrarem o tipo são ajustadas na Task 5; se o
`tsc` acusar só `Comparador.tsx`, faça o ajuste mínimo (`api.simulate(valor, "DATA", dData, signal)`) aqui.

- [ ] **Step 5: Commit** — `feat(ui): ordenação, dominância e rótulo de prazo de saída`

---

### Task 5: Frontend — seletor de horizonte, seletor de ordenação e cards

**Files:**
- Modify: `frontend/src/components/InputsBar.tsx`, `frontend/src/components/ProductCard.tsx` (+ `ProductCard.test.tsx`)
- Create: `frontend/src/components/SortSelect.tsx`
- Modify: `frontend/src/pages/Comparador.tsx` (+ `Comparador.test.tsx`)

**Interfaces:**
- Consumes: Task 4 (`Horizonte`, `Ordenacao`, `ordenar`, `dominados`, `ORDENACOES`, `HORIZONTES`, `prazoSaidaLabel`, `api.simulate`).
- Produces (UI):
  - `InputsBar` ganha `horizonte: Horizonte`, `onHorizonte(h)`, `dataResolvida: string | null`. Grupo de botões
    `role="radiogroup"` com `aria-label="Horizonte"` e um `role="radio"` por item de `HORIZONTES`. O campo
    "Preciso do dinheiro em" só existe em `DATA`; em `UM_ANO`/`DOIS_ANOS` mostra "Resgate em dd/mm/aaaa"
    (`dataResolvida`, vinda da resposta); em `SEM_DATA`, "Cada produto até o vencimento (ou 1 ano, se tiver liquidez diária)".
  - `SortSelect({ value, onChange, semData })`: `<select aria-label="Ordenar por">` com `ORDENACOES`; omite
    `VALOR_LIQUIDO` quando `semData`. Estilo do `<select>` de plataforma em `Filters.tsx`.
  - `ProductCard` ganha `destaque?: "valor" | "taxa"` (padrão `"valor"`), `dominado?: boolean`, `hoje: string`.
    `"taxa"`: número grande = `formatPct(taxa_liquida_aa)` + " a.a."; linha abaixo = `formatBRL(valor_liquido)` +
    " em " + `formatDate(data_saida)`. Sempre mostra `prazoSaidaLabel` como texto na linha de chips. `dominado` →
    chip "Há opção melhor e mais curta".
  - `Comparador`: estados `horizonte` (`localStorage` `liquido.horizonte`, padrão/valor inválido → `"DATA"`) e
    `ordenacao` (`liquido.ordenacao`, padrão/inválido → `"VALOR_LIQUIDO"`, ou `"TAXA"` em `SEM_DATA`). Ao entrar em
    `SEM_DATA` com `VALOR_LIQUIDO`, troca para `TAXA`. `queryKey: ["simulate", valorNum, horizonte, dData|null]`;
    validação da data só em `DATA`. Por seção: `filtrada = applyFilters(...)`; `dom = dominados(filtrada)`;
    `lista = ordenar(filtrada, ordenacao)`. Em `SEM_DATA`: uma seção "Todos os produtos — até o vencimento ou 1 ano"
    (cards com `destaque="taxa"` e `rank`), sem a seção vermelha; demais modos como hoje, com `fmtAlvo` vindo de
    `data.data_alvo`. O `SortSelect` fica junto dos `Filters`.

- [ ] **Step 1: Write the failing tests** (`Comparador.test.tsx`, mantendo o mock de `api`)

```tsx
test("sem data: esconde a data, chama a API com SEM_DATA e ordena por taxa", async () => {
  mocked.simulate.mockResolvedValue({ ...fixtureResponse, horizonte: "SEM_DATA", data_alvo: null, vence_ate_data: [baixa, alta] });
  setup();
  await userEvent.click(await screen.findByRole("radio", { name: "Sem data" }));
  expect(screen.queryByLabelText("Preciso do dinheiro em")).toBeNull();
  await waitFor(() => expect(mocked.simulate).toHaveBeenLastCalledWith(expect.any(String), "SEM_DATA", null, expect.anything()));
  expect((screen.getByLabelText("Ordenar por") as HTMLSelectElement).value).toBe("TAXA");
  const titulos = (await screen.findAllByRole("article")).map((a) => a.querySelector("h3")?.textContent);
  expect(titulos).toEqual([alta.product.nome, baixa.product.nome]);
});
test("1 ano mostra a data resolvida pelo backend", async () => {
  mocked.simulate.mockResolvedValue({ ...fixtureResponse, horizonte: "UM_ANO", data_alvo: "2027-11-19" });
  setup();
  await userEvent.click(await screen.findByRole("radio", { name: "1 ano" }));
  expect(await screen.findByText(/Resgate em 19\/11\/2027/)).toBeInTheDocument();
});
test("selo de dominado respeita o filtro", async () => {
  // cdb (FGC, CDB) domina lci (LCI) na mesma seção; com "Só isentos" o cdb some e o selo também
  mocked.simulate.mockResolvedValue({ ...fixtureResponse, vence_ate_data: [cdb, lci] });
  setup();
  expect(await screen.findByText("Há opção melhor e mais curta")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Só isentos" }));
  expect(screen.queryByText("Há opção melhor e mais curta")).toBeNull();
});
test("localStorage inválido cai no padrão", async () => {
  localStorage.setItem("liquido.horizonte", "\"XYZ\""); localStorage.setItem("liquido.ordenacao", "\"ABC\"");
  setup();
  expect(await screen.findByRole("radio", { name: "Escolher data" })).toHaveAttribute("aria-checked", "true");
  expect((screen.getByLabelText("Ordenar por") as HTMLSelectElement).value).toBe("VALOR_LIQUIDO");
});
```

  Grave os valores em `localStorage` no mesmo formato que `writeStore` usa (confira `lib/storage.ts`).
  Em `ProductCard.test.tsx`: `destaque="taxa"` mostra "11,80% a.a." e "R$ 71.840,10 em 16/11/2028"; `dominado`
  mostra o selo; o rótulo de prazo aparece ("Preso até 15/11/2028" para `fixtureResult`).
  Ajuste os testes existentes que chamam `api.simulate` com a assinatura antiga.

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/pages/Comparador.test.tsx src/components/ProductCard.test.tsx`
Expected: FAIL (radio "Sem data" inexistente)

- [ ] **Step 3: Implement** InputsBar, SortSelect, ProductCard and Comparador as specified.

- [ ] **Step 4: Run frontend checks**

Run: `cd frontend && npm test && npm run build`
Expected: PASS e build sem erros de tipo.

- [ ] **Step 5: Commit** — `feat(ui): horizonte da simulação e seletor de ordenação no comparador`

---

### Task 6: E2E e documentação

**Files:**
- Modify: `frontend/e2e/comparador.spec.ts`
- Modify (orquestrador): `docs/superpowers/specs/2026-11-19-comparador-renda-fixa-design.md` — nota no topo apontando
  para o novo design onde ele muda entradas e ordenação.

**Interfaces:**
- Consumes: Tasks 3 e 5.

- [ ] **Step 1: Write the e2e test**

```ts
test("sem data e custo-benefício", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Quanto você quer investir?").fill("50.000,00");
  await page.getByRole("radio", { name: "Sem data" }).click();
  await expect(page.getByLabel("Preciso do dinheiro em")).toHaveCount(0);
  const secao = page.locator("section").filter({ has: page.getByRole("heading", { name: /Todos os produtos/ }) });
  await expect(secao.locator("article").first()).toBeVisible();
  await expect(secao.locator("article").first().getByText(/a\.a\./).first()).toBeVisible();
  await page.getByLabel("Ordenar por").selectOption("CUSTO_BENEFICIO");
  await expect(secao.locator("article").first()).toBeVisible();
  await page.getByRole("radio", { name: "2 anos" }).click();
  await expect(page.getByText(/Resgate em \d{2}\/\d{2}\/\d{4}/)).toBeVisible();
});
```

  O teste existente continua válido: ele preenche "Preciso do dinheiro em", então primeiro clique em
  `radio "Escolher data"` se o padrão salvo puder ser outro (o contexto do Playwright começa com `localStorage` vazio,
  logo o padrão é `DATA`).

- [ ] **Step 2: Run e2e**

Run: `cd frontend && npx playwright test --trace off`
Expected: PASS

- [ ] **Step 3: Full verification**

Run: `cd backend && uv run pytest -q && cd ../frontend && npm test && npm run build`
Expected: tudo PASS.

- [ ] **Step 4: Commit** — `test(e2e): horizonte sem data e ordenação custo-benefício` (+ `docs: ...` para a nota no design principal)
