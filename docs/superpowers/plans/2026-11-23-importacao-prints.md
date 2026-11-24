# Regras LCI/LCA/LCD + Importação por Print — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Execução escolhida pelo usuário:** subagent-driven. Implementador = subagente **Sonnet**; revisor por
> tarefa = subagente **Haiku**; orquestração e todo `.md` = Opus. Cada implementador recebe: a tarefa
> inteira, "Global Constraints", "Review Focus" e `CLAUDE.md`. Tarefas marcadas **[Orquestrador]** são
> feitas pelo Opus, não despachadas.

**Goal:** Fase 1 — prazos mínimos de LCI/LCA por indexação e novo tipo LCD. Fase 2 — enviar vários prints
de ofertas (XP, BTG, Nubank), extrair com o LLM local com visão em segundo plano, cadastrar
automaticamente com data de registro, envelhecer ofertas (alerta 14 d, fora do ranking 28 d).

**Architecture:** Domínio puro ganha `LCD`, prazos por indexação e regras de envelhecimento
(`domain/offers.py`). Um pacote novo `app/imports/` separa: esquema da resposta do LLM, interpretação
determinística (texto → `ProductData`), cliente OpenAI-compatível, serviço de importação (fila SQLite,
renovação, falhas) e um worker em thread no próprio processo. Frontend ganha a página Importar e
ajustes em Produtos/Detalhe/Configurações.

**Tech Stack:** o existente (FastAPI, pydantic v2, httpx, sqlite3, React/Vite/TS/Tailwind, react-query,
vitest, Playwright) + `python-multipart` (upload). Sem Pillow.

**Spec:** `docs/superpowers/specs/2026-11-23-importacao-prints-design.md` (e, para o resto do sistema,
`docs/superpowers/specs/2026-11-19-comparador-renda-fixa-design.md`).

## Resultado do spike com o modelo real (2026-11-23)

- Modelo: **`unsloth/Qwen3.5-9B-GGUF`** com `mmproj-BF16` (cabe inteiro na VRAM de 16 GB). **Não usar o
  Qwen3.8-27B**: não cabe na VRAM, transborda para a RAM e esgotou a memória comprometida do Windows
  (derrubou o WSL). O servidor tem auto-switch ligado e carrega um modelo por vez.
- Visão OK; `response_format` `json_schema` é honrado (enum respeitado); `enable_thinking: false` aceito.
- Tempo: 12 s (app BTG, 2 ofertas, incluindo carga) e 51 s (tabela XP densa, 9 ofertas).
- **O modelo troca `texto` e `rotulo`** e despeja células que não são taxa em `taxas`. Por isso: no
  esquema, `rotulo` vem **antes** de `texto`, ambos com `description`; e a escolha da taxa aceita o valor
  em qualquer dos dois campos (Task 5).
- Plataforma acertada com notas mínimas (BTG, XP).

## Global Constraints

- Regras inegociáveis do `CLAUDE.md`: `Decimal` sempre; taxas como fração; % convertido só na borda
  (aqui: o parser de textos do print); `Settings` para prazos/limites; **testes sem rede**; TDD; commits
  `tipo(escopo): descrição` com a linha `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Código em inglês; campos e termos do domínio em português. UI 100% pt-BR.
- Branch: `claude/importacao-prints`.
- Configuração do LLM só por ambiente: `LLM_BASE_URL`, `CASA_LLM_MODEL`, `LLM_API_KEY` (opcional),
  `LLM_TIMEOUT_S` (padrão `300`). Ausência de `LLM_BASE_URL` ou `CASA_LLM_MODEL` ⇒ importação "não
  configurada". **O token nunca aparece em código, teste, fixture ou commit.**
- Modelo: `CASA_LLM_MODEL=unsloth/Qwen3.5-9B-GGUF` (nunca o 27B). Sem modelo carregado o servidor responde
  400 "No model loaded" (tratado como `LlmUnavailable`).
- Variáveis de teste/e2e: `LIQUIDO_LLM_FIXTURES=<dir>` usa o cliente falso; `LIQUIDO_IMPORT_WORKER=0`
  não inicia a thread.
- Prazos mínimos (padrões em `Settings`): LCI 6 meses; LCI IPCA+ 36; LCA 6; LCA IPCA+ 12; LCD 12.
- LCD: isenta de IR e IOF (entra nos padrões de `ir_exempt_types`/`iof_exempt_types`), cobertura
  padrão FGC (Res. CMN 5.169/2024), não pode ter liquidez `DIARIA`.
- Envelhecimento: `oferta_alerta_dias = 14`, `oferta_expira_dias = 28` (validar `1 ≤ alerta < expira`).
  Idade em dias corridos desde `data_registro`. Expirada ⇔ `idade ≥ expira` ou `today > disponivel_ate`.
  Exemplos e Tesouro nunca envelhecem.
- Estados: item `NA_FILA | LENDO | CONCLUIDO | ERRO`; falha `ABERTA | RESOLVIDA | DESCARTADA`.
- Uploads: PNG, JPEG, WEBP (detectados pelos bytes iniciais), até 20 MB cada. Prints gravados em
  `<pasta do banco>/prints/<sha256>.<ext>`.
- LLM: até 3 tentativas por item em falha de rede/timeout/5xx/"No model loaded", espera 5 s, 30 s;
  depois `ERRO`. Resposta ilegível após 1 nova tentativa ⇒ `ERRO`.
- Nada de imagens reais no git: `backend/calibration/` é ignorado. Fixtures commitadas são só JSON.

## Review Focus

1. **Servidor LLM fora do ar ou sem modelo carregado no meio de um lote de 30** → cada item tenta 3 vezes
   e vira `ERRO` com mensagem pt-BR clara ("Servidor LLM indisponível: …"); os demais seguem; "tentar de
   novo" recoloca na fila; o lote nunca fica preso em `LENDO`. (testes nas Tasks 6 e 7)
2. **Taxa e vencimento no mesmo texto** ("109% do CDI · 18 NOV 2031", "365 dias | 23/11/2027") → o parser
   acha a taxa e a data dentro do texto. (testes na Task 3)
3. **A mesma oferta duas vezes no mesmo print com mínimos diferentes** (LCD BNDES 15/03/2030 87% ×4) →
   um produto só, com o menor `valor_minimo`; item conta 1 criado + 3 renovados. (teste na Task 6)
4. **Arquivo que não é imagem, ou maior que 20 MB, junto com prints válidos** → os válidos entram; o
   inválido é recusado com mensagem por arquivo, sem derrubar o lote. (testes nas Tasks 6 e 7)
5. **Reenvio de oferta já expirada e editada à mão pelo usuário** → volta ao ranking (data renovada) e
   mantém as correções manuais (nome, mínimo, observações). (teste na Task 6)

---

## Estrutura de arquivos

```
backend/app/domain/products/base.py        # +LCD, +campos de oferta, +AlertCodes
backend/app/domain/products/{bank,factory,validation}.py
backend/app/domain/settings.py             # prazos por indexação, envelhecimento
backend/app/domain/offers.py               # NOVO: idade, expiração, alertas de oferta, chave de renovação
backend/app/domain/sources.py              # ManualSource pula expiradas
backend/app/imports/__init__.py            # NOVO pacote
backend/app/imports/schema.py              # RawRate, RawOffer, RawExtraction (+ JSON Schema)
backend/app/imports/parsing.py             # textos → Decimal/date/indexador
backend/app/imports/selection.py           # escolha da taxa (equivalente, riscada, gross-up)
backend/app/imports/interpret.py           # RawOffer → Created | Ignored | Failed
backend/app/imports/prompt_sistema.md      # [Orquestrador] prompt versionado
backend/app/imports/llm.py                 # LlmConfig, OpenAICompatClient, FakeLlmClient, erros
backend/app/imports/service.py             # fila, renovação, falhas
backend/app/imports/worker.py              # thread
backend/app/imports/eval.py                # script manual contra o modelo real
backend/app/data/db.py                     # novas tabelas
backend/app/data/imports_repo.py           # NOVO: ImportRepository, PrintStore
backend/app/api/imports.py                 # NOVO: rotas
backend/app/api/products.py                # carimbo de data, ProductView
backend/app/deps.py, backend/app/main.py   # wiring, migração, lifespan
backend/tests/fixtures/imports/*.json      # [Orquestrador] respostas transcritas dos prints
frontend/src/pages/Importar.tsx            # NOVO
frontend/src/components/{ProductForm,ProductDetail,Layout}.tsx, pages/{Produtos,Configuracoes}.tsx
frontend/src/api/{types,client}.ts, lib/labels.ts, lib/settingsForm.ts
frontend/e2e/importar.spec.ts              # NOVO
deploy/{liquido.service,install.sh}, README.md
```

---

## FASE 1 — Regras

### Task 1: Backend — LCD e prazos mínimos por indexação

**Files:**
- Modify: `backend/app/domain/products/base.py`, `bank.py`, `factory.py`, `validation.py`, `backend/app/domain/settings.py`
- Test: `backend/tests/domain/products/test_validation.py`, `backend/tests/domain/test_settings.py`, `backend/tests/domain/products/test_bank.py`

**Interfaces:**
- Produces: `ProductType.LCD = "LCD"`; `_DEFAULT_COVERAGE[LCD] = Coverage.FGC`; `class LCD(BankProduct)`
  registrada na fábrica; `_ISENTOS` inclui `LCD`.
- `Settings`: **remove** `carencia_min_meses_lci`/`carencia_min_meses_lca`; **adiciona**
  `prazo_min_meses_lci: int = 6`, `prazo_min_meses_lci_ipca: int = 36`, `prazo_min_meses_lca: int = 6`,
  `prazo_min_meses_lca_ipca: int = 12`, `prazo_min_meses_lcd: int = 12` (todos `≥ 0`, senão
  `ValueError` "prazo mínimo não pode ser negativo"). Nomes novos de propósito: valores antigos gravados
  (9/12) são ignorados pelo pydantic e os novos padrões valem.
- `Settings.prazo_minimo_meses(tipo: ProductType, indexador: Indexer) -> int | None` — `None` para
  tipos sem prazo mínimo.

- [ ] **Step 1: Testes que falham**

```python
TODAY = date(2026, 11, 23)

def test_lca_6_months_ok_and_5_fails():
    assert validate_product(make(tipo=LCA, data_vencimento=date(2027, 5, 24)), Settings(), TODAY) == []
    erros = validate_product(make(tipo=LCA, data_vencimento=date(2027, 5, 20)), Settings(), TODAY)
    assert "LCA exige prazo mínimo de 6 meses" in erros

def test_lci_ipca_needs_36_months():
    e = validate_product(make(tipo=LCI, indexador=IPCA_MAIS, taxa=D("0.06"), data_vencimento=date(2028, 11, 24)), Settings(), TODAY)
    assert "LCI exige prazo mínimo de 36 meses" in e

def test_lca_ipca_needs_12_months():
    e = validate_product(make(tipo=LCA, indexador=IPCA_MAIS, taxa=D("0.06"), data_vencimento=date(2027, 8, 1)), Settings(), TODAY)
    assert "LCA exige prazo mínimo de 12 meses" in e

def test_lcd_rules():
    assert make(tipo=LCD).cobertura == Coverage.FGC
    assert "LCD exige prazo mínimo de 12 meses" in validate_product(make(tipo=LCD, data_vencimento=date(2027, 6, 1)), Settings(), TODAY)
    assert "LCD não pode ter liquidez diária" in validate_product(make(tipo=LCD, liquidez=DIARIA, data_vencimento=date(2030, 1, 2)), Settings(), TODAY)
    assert LCD in Settings().ir_exempt_types and LCD in Settings().iof_exempt_types

def test_lcd_simulates_tax_free():
    r = build_product(make(tipo=LCD, indexador=PCT_CDI, taxa=D("0.90"), data_vencimento=date(2030, 3, 15))).simulate(D("10000"), date(2031, 1, 1), ctx)
    assert r.ir == 0 and r.iof == 0

def test_old_settings_keys_ignored():
    s = Settings.model_validate({"carencia_min_meses_lca": 9})
    assert s.prazo_min_meses_lca == 6

def test_negative_prazo_rejected():
    with pytest.raises(ValueError): Settings(prazo_min_meses_lcd=-1)
```
Atualizar as asserções existentes que usam "carência mínima" para a nova mensagem `"{TIPO} exige prazo mínimo de {n} meses"`.

- [ ] **Step 2:** Rodar `cd backend && uv run pytest -q tests/domain` → FAIL.
- [ ] **Step 3: Implementar.** Em `validation.py` a regra vale para `{LCI, LCA, LCD}`: proíbe `DIARIA`
  ("{TIPO} não pode ter liquidez diária"); referência = vencimento se `NO_VENCIMENTO`, senão
  `data_carencia`; meses = `settings.prazo_minimo_meses(tipo, indexador)` (IPCA+ usa o campo `_ipca`).
- [ ] **Step 4:** `uv run pytest -q` → PASS (suite inteira).
- [ ] **Step 5:** Commit `feat(domain): LCD e prazos mínimos de LCI/LCA por indexação`.

### Task 2: Frontend — LCD e novos prazos

**Files:**
- Modify: `frontend/src/api/types.ts`, `components/ProductForm.tsx`, `lib/labels.ts`, `lib/settingsForm.ts`, `pages/Configuracoes.tsx`, `pages/Comparador.tsx`
- Test: `components/ProductForm.test.tsx`, `pages/Configuracoes.test.tsx`, `lib/labels` (novo teste se não houver)

**Interfaces:**
- Consumes: Task 1 (`"LCD"` em `ProductType`; campos `prazo_min_meses_*` no `Settings` da API).
- Produces: `ProductType` inclui `"LCD"`; grupo de filtro `LCI_LCA` passa a se chamar **"LCI/LCA/LCD"** e
  `tipoGrupo("LCD") === "LCI_LCA"`; `ISENTOS_PADRAO` inclui `"LCD"`.

- [ ] **Step 1: Testes que falham** — `ProductForm`: opção "LCD" existe e, com LCD selecionada, "Liquidez
  diária" não aparece; `tipoGrupo("LCD") === "LCI_LCA"`; `Configuracoes`: os cinco campos
  ("LCI", "LCI IPCA+", "LCA", "LCA IPCA+", "LCD", em meses) aparecem com 6/36/6/12/12 e salvar envia
  `prazo_min_meses_lci_ipca: 36` etc.; o fixture de settings do teste troca `carencia_min_meses_*` pelos
  novos campos.
- [ ] **Step 2:** `cd frontend && npm test` → FAIL.
- [ ] **Step 3:** Implementar (seção "Prazos mínimos" em Configurações, onde hoje ficam as carências).
- [ ] **Step 4:** `npm test && npm run build` → PASS.
- [ ] **Step 5:** Commit `feat(ui): LCD e prazos mínimos por indexação`.

---

## FASE 2 — Importação por print

### Task 3: Campos de oferta, envelhecimento e carimbo de data (backend)

**Files:**
- Create: `backend/app/domain/offers.py`
- Modify: `base.py` (campos, AlertCodes, `_common_alerts`), `settings.py`, `sources.py`, `api/products.py`, `deps.py`
- Test: `backend/tests/domain/test_offers.py`, `backend/tests/api/test_products.py`, `backend/tests/domain/test_sources.py`

**Interfaces:**
- Produces em `base.py`:
  - `Periodicidade = Literal["MENSAL", "TRIMESTRAL", "SEMESTRAL", "ANUAL"]`
  - `class Amortizacao(BaseModel)`: `periodicidade: Periodicidade`, `inicio: date`
  - `ProductData` + `data_registro: date | None = None`, `disponivel_ate: date | None = None`,
    `origem: Literal["MANUAL", "IA"] = "MANUAL"`, `print_id: str | None = None`,
    `juros_periodicos: Periodicidade | None = None`, `amortizacao: Amortizacao | None = None`.
  - `AlertCode` + `OFERTA_ANTIGA`, `IMPORTADO_IA`.
- `Settings` + `oferta_alerta_dias: int = 14`, `oferta_expira_dias: int = 28` (validação
  `1 ≤ alerta < expira`, msg "o alerta de oferta antiga deve vir antes da expiração").
- `offers.py`:
  - `ages(data: ProductData) -> bool` — `False` se `exemplo` ou tipo `TESOURO_*`.
  - `offer_age_days(data, today) -> int | None`
  - `is_expired(data, settings, today) -> bool`
  - `offer_alerts(data, settings, today) -> list[Alert]` — `OFERTA_ANTIGA` "Oferta registrada há N dias —
    confira se ainda está disponível"; `IMPORTADO_IA` "Importado por IA de um print"; `MODELO_SIMPLIFICADO`
    "Paga juros {mensais|trimestrais|semestrais|anuais}; calculado como se pagasse tudo no vencimento"
    quando `juros_periodicos` ou `amortizacao` (texto "Amortiza em parcelas; …" quando só amortização).
  - `normalize_emissor(s: str) -> str` (minúsculas, sem acento, espaços colapsados, remove tokens
    `s.a.`, `s/a`, `sa`, `banco`, `ltda`, pontuação final e reticências "...").
  - `normalize_plataforma(s: str) -> str` (minúsculas, sem acento; `"btg pactual"` → `"btg"`).
  - `offer_key(data) -> tuple` = `(tipo, normalize_plataforma, indexador, taxa.normalize(), data_vencimento, normalize_emissor)`.
- `_common_alerts` acrescenta `offer_alerts(self.data, ctx.settings, ctx.today)`.
- `ManualSource.load` pula `is_expired(...)` (precisa de `ctx.settings`/`ctx.today`).
- API: `class ProductView(ProductData)`: `idade_dias: int | None`, `expirada: bool`. `GET /api/products`
  devolve `list[ProductView]`. `POST /api/products` e `/duplicate` carimbam `data_registro = today`,
  `origem = "MANUAL"`, `print_id = None` (ignora o que vier do cliente). `PUT` **preserva**
  `data_registro`, `origem`, `print_id`, `juros_periodicos` e `amortizacao` do produto gravado;
  `disponivel_ate` é editável.
- `deps.stamp_missing_registration(products: ProductRepository, today: date) -> int` — produtos
  não-exemplo sem `data_registro` recebem `today`; chamado em `build_container` após o seed; idempotente.

- [ ] **Step 1: Testes que falham**

```python
T = date(2026, 11, 23)
def test_age_boundaries():
    s = Settings()
    p = lambda d: make(data_registro=T - timedelta(days=d))
    assert not offer_alerts(p(13), s, T) and codes(offer_alerts(p(14), s, T)) == {OFERTA_ANTIGA}
    assert not is_expired(p(27), s, T) and is_expired(p(28), s, T)
def test_disponivel_ate_expires_earlier():
    assert is_expired(make(data_registro=T, disponivel_ate=T - timedelta(days=1)), Settings(), T)
    assert not is_expired(make(data_registro=T, disponivel_ate=T), Settings(), T)
def test_examples_and_no_date_never_age():
    assert not is_expired(make(exemplo=True, data_registro=T - timedelta(days=99)), Settings(), T)
    assert offer_age_days(make(data_registro=None), T) is None
def test_simplified_alert_for_coupons():
    assert MODELO_SIMPLIFICADO in codes(offer_alerts(make(juros_periodicos="SEMESTRAL"), Settings(), T))
def test_offer_key_normalizes():
    a = make(emissor="BANCO COOPERATIVO SIC...", plataforma="BTG Pactual")
    b = make(emissor="Banco Cooperativo Sic", plataforma="BTG")
    assert offer_key(a) == offer_key(b)
    assert offer_key(make(taxa=D("0.90"))) == offer_key(make(taxa=D("0.9000")))
def test_manual_source_skips_expired(...):  # expirado some do load; inativo continua sumindo
def test_create_stamps_today_and_put_preserves(client):  # POST → data_registro == hoje, origem MANUAL mesmo enviando IA; PUT com data_registro diferente não muda
def test_list_has_age_and_expired(client)
def test_migration_stamps_once(tmp_path)  # 2ª chamada devolve 0; exemplos ficam None
def test_settings_validation_alert_before_expiry():
    with pytest.raises(ValueError): Settings(oferta_alerta_dias=28, oferta_expira_dias=28)
```
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** `uv run pytest -q` PASS.
- [ ] **Step 5:** Commit `feat(ofertas): data de registro, envelhecimento e alertas de oferta`.

### Task 4 [Orquestrador]: fixtures transcritas e prompt

Antes da Task 5, o Opus escreve (a partir dos prints que só ele viu):
- `backend/tests/fixtures/imports/<nome>.json` — uma `RawExtraction` (formato da Task 5) por print de
  `backend/calibration/prints/`, transcrita fielmente (inclui a linha cortada do XP app, a taxa riscada
  do Nubank, a coluna "Taxa Eq. do CDB" do BTG, "IR · 15%", carteira → `ofertas: []`).
- `backend/tests/fixtures/imports/README.md` — de onde vieram, sem imagens.
- `backend/app/imports/prompt_sistema.md` — prompt da §6.2 com as notas por plataforma da spec.
- Cópias locais `backend/calibration/prints/<nome>.esperado.json` (mesmo conteúdo) para o `eval`.
Commit `test(importacao): respostas transcritas dos prints e prompt do sistema`.

### Task 5: Esquema, parser, escolha da taxa e interpretação (puro)

**Files:**
- Create: `backend/app/imports/{__init__,schema,parsing,selection,interpret}.py`
- Test: `backend/tests/imports/test_parsing.py`, `test_selection.py`, `test_interpret.py`

**Interfaces:**
- Consumes: Task 1 (`LCD`, `validate_product`), Task 3 (campos de oferta, `Periodicidade`, `Amortizacao`), Task 4 (fixtures).
- `schema.py` (pydantic):
  - `RawRate`: `rotulo: str = ""` (description "rótulo ou cabeçalho da coluna, ex.: Taxa, Taxa eq. CDB"),
    `texto: str` (description "o valor como aparece, ex.: 90,00% do CDI") — **nesta ordem**
  - `RawOffer`: `tipo: str`, `emissor: str | None = None`, `nome_exibido: str | None = None`,
    `taxas: list[RawRate] = []`, `vencimento: str | None = None`, `aplicacao_minima: str | None = None`,
    `liquidez: str | None = None`, `carencia: str | None = None`, `disponivel_ate: str | None = None`,
    `codigo: str | None = None`, `juros: str | None = None`, `amortizacao: str | None = None`,
    `cortada: bool = False`
  - `RawExtraction`: `plataforma: str = "DESCONHECIDA"`, `ofertas: list[RawOffer] = []`
  - `EXTRACTION_JSON_SCHEMA: dict` = `RawExtraction.model_json_schema()`
- `parsing.py` (todas aceitam o valor **dentro** de um texto maior):
  - `parse_rate(texto: str) -> tuple[Indexer, Decimal] | None` — `%`/`% do CDI`/`% CDI` → `PCT_CDI`;
    `CDI +`/`CDI+` → `CDI_MAIS`; `IPCA +`/`IPC-A +`/`IPCA+` → `IPCA_MAIS`; número com `%` sem indexador
    (opcional `a.a.`, `Pré`) → `PRE`. Vírgula decimal; `Decimal` exato (`"102,5%"` → `Decimal("1.025")`).
  - `parse_date(texto: str) -> date | None` — `dd/mm/aaaa`, `dd/mm/aa`, `dd MMM aaaa` (jan…dez, qualquer caixa).
  - `parse_money(texto: str) -> Decimal | None` — `R$ 1.093,03` → `Decimal("1093.03")`.
  - `parse_carencia(texto: str, registro: date) -> date` — data, `N dias`, `D+N`; senão `ValueError`.
  - `parse_periodicidade(texto: str | None) -> Periodicidade | None` — "Mensal(is)", "Trimestral",
    "Semestral", "Anual"; "No Vencimento", "-", vazio → `None`.
  - `parse_amortizacao(texto: str | None) -> Amortizacao | None` — "Anual a partir de 15/03/2032"; "No Vencimento"/"-" → `None`.
- `selection.py`:
  - `EXCLUDED_LABEL = re.compile(r"equival|equiv|\beq\b|bruto|gross|riscad|\bir\b", re.I)` (aplicado ao
    rótulo **e** ao texto, sem acento).
  - `@dataclass RateChoice`: `indexador`, `taxa`, `ignoradas: list[str]` (cada uma `"111,76% do CDI (Equivalente CDB)"`)
  - `@dataclass RateAmbiguous`: `textos: list[str]`
  - `choose_rate(taxas: list[RawRate], tipo: ProductType, vencimento: date | None, settings: Settings, today: date) -> RateChoice | RateAmbiguous`
    — passos da spec §6.4: considera só entradas em que `texto` **ou** `rotulo` contém `%` e é
    interpretável por `parse_rate` (o valor pode estar em qualquer um dos dois — o modelo troca); o outro
    campo é o rótulo; exclui pelo regex aplicado aos dois campos; descarta não interpretáveis; colapsa iguais; se tipo em
    `settings.ir_exempt_types` e sobram duas do mesmo indexador com `maior ≈ menor/(1−aliquota(dias até
    o vencimento))` (tolerância relativa 3%) descarta a maior; exatamente uma ⇒ `RateChoice`.
- `interpret.py`:
  - `@dataclass Created`: `data: ProductData`
  - `@dataclass Ignored`: `motivo: str` (`"cortada"`, `"fundo"`, `"tesouro"`, `"tipo não suportado: LF"`)
  - `@dataclass Failed`: `erros: list[str]`, `parcial: dict` (o `RawOffer` em JSON + o que foi interpretado)
  - `PLATAFORMAS = {"XP": "XP", "BTG": "BTG", "NUBANK": "Nubank"}`
  - `interpret_offer(raw: RawOffer, plataforma: str, settings: Settings, today: date) -> Created | Ignored | Failed`
    — regras da spec §6.4: `origem="IA"`, `data_registro=today`, `nome = nome_exibido or f"{tipo} {emissor}"`;
    liquidez `DESCONHECIDA`/ausente → `NO_VENCIMENTO` + nota; "A mercado"/"No Vencimento" → `NO_VENCIMENTO`;
    mínimo ausente → `0` + nota "mínimo não visível no print"; notas em `observacoes` (uma por linha:
    taxas ignoradas, `Código: …`, `Juros: …`, `Amortização: …`); juros/amortização vão também para os
    campos estruturados; no fim `validate_product` — erros ⇒ `Failed`.
    Mensagens de falha: "Plataforma não identificada", "Emissor não visível", "Vencimento não visível",
    "Data sem dia: …", "Taxa ambígua: …", "Carência não reconhecida: …".

- [ ] **Step 1: Testes que falham**

```python
@pytest.mark.parametrize("texto,esperado", [
    ("95% do CDI", (PCT_CDI, D("0.95"))), ("102,5% CDI", (PCT_CDI, D("1.025"))),
    ("90,00%\ndo CDI", (PCT_CDI, D("0.9"))), ("CDI + 1,900%", (CDI_MAIS, D("0.019"))),
    ("IPC-A + 7,800%", (IPCA_MAIS, D("0.078"))), ("IPCA + 12,04%", (IPCA_MAIS, D("0.1204"))),
    ("15,100%", (PRE, D("0.151"))), ("18,26% a.a.", (PRE, D("0.1826"))),
    ("109% do CDI · 18 NOV 2031", (PCT_CDI, D("1.09"))),      # Review Focus 2
    ("abc", None)])
def test_parse_rate(texto, esperado): assert parse_rate(texto) == esperado

def test_parse_dates():
    assert parse_date("18 NOV 2031") == date(2031, 11, 18)
    assert parse_date("365 dias | 23/11/2027") == date(2027, 11, 23)   # Review Focus 2
    assert parse_date("mai/2028") is None
def test_parse_carencia():
    assert parse_carencia("D+90", date(2026, 11, 23)) == date(2027, 2, 21)
    with pytest.raises(ValueError): parse_carencia("após o 3º mês", date(2026, 11, 23))
def test_parse_amortizacao():
    assert parse_amortizacao("Anual a partir de 15/03/2032") == Amortizacao(periodicidade="ANUAL", inicio=date(2032, 3, 15))

def test_btg_eq_cdb_label_discarded():
    c = choose_rate([RawRate(texto="90,00% do CDI", rotulo="Taxa"), RawRate(texto="108,46% do CDI", rotulo="Taxa eq. CDB")], LCI, date(2027,11,23), Settings(), T)
    assert (c.indexador, c.taxa) == (PCT_CDI, D("0.9")) and "108,46% do CDI (Taxa eq. CDB)" in c.ignoradas
def test_gross_up_without_label():
    c = choose_rate([RawRate(texto="90% do CDI"), RawRate(texto="107,93% do CDI")], LCI, date(2028,5,24), Settings(), T)
    assert c.taxa == D("0.9")
def test_strikethrough_and_ir_discarded():
    c = choose_rate([RawRate(texto="107% do CDI", rotulo="riscada"), RawRate(texto="108% do CDI", rotulo=""), RawRate(texto="15%", rotulo="IR")], CDB, date(2028,11,18), Settings(), T)
    assert c.taxa == D("1.08")
def test_swapped_fields_and_junk_cells():   # comportamento real do Qwen3.5-9B
    taxas = [RawRate(rotulo="90,00% do CDI", texto="Taxa"), RawRate(rotulo="108,46% do CDI", texto="Taxa eq. CDB"),
             RawRate(rotulo="R$ 500,00", texto="Aplicação mínima"), RawRate(texto="22/11/2028", rotulo="Vencimento"),
             RawRate(texto="2", rotulo="Risco")]
    assert choose_rate(taxas, LCI, date(2027,11,23), Settings(), T).taxa == D("0.9")
def test_two_unrelated_rates_are_ambiguous():
    assert isinstance(choose_rate([RawRate(texto="95% do CDI"), RawRate(texto="99% do CDI")], CDB, date(2028,1,3), Settings(), T), RateAmbiguous)

def test_interpret_fixtures():   # usa backend/tests/fixtures/imports/*.json da Task 4
    # btg-app-lci-eq-cdb: 2 Created LCI 0.90 BTG; xp-app-cdb-lista: 2 Created + 1 Ignored("cortada");
    # xp-web-carteira-fundos: 0 ofertas; nubank-app-fundos: 2 Ignored("fundo");
    # nubank-app-cdb-ultravioleta: CDB 1.08 Cloudwalk Infinitepay venc 2028-11-18, plataforma "Nubank";
    # xp-web-tabela-lcd: LCD BNDES 0.87 venc 2030-03-15; btg-web-cri-cra-ipca: CRI AUTOMOB IPCA_MAIS 0.1204,
    #   juros_periodicos SEMESTRAL, "Código: 22L2288690" nas observações;
    # btg-web-lca-eq-cdb-a: LCA 0.88 venc 2027-05-24 é Created (prazo de 6 meses).
def test_missing_platform_fails():
    assert "Plataforma não identificada" in interpret_offer(raw_ok, "DESCONHECIDA", Settings(), T).erros
def test_missing_minimum_defaults_zero_with_note()
def test_fund_and_tesouro_ignored()
```
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** `uv run pytest -q` PASS.
- [ ] **Step 5:** Commit `feat(importacao): interpretação determinística das ofertas extraídas`.

### Task 6: Persistência, prints e serviço de importação

**Files:**
- Create: `backend/app/data/imports_repo.py`, `backend/app/imports/service.py`, `backend/app/imports/llm.py` (só o protocolo e os erros)
- Modify: `backend/app/data/db.py`
- Test: `backend/tests/data/test_imports_repo.py`, `backend/tests/imports/test_service.py`

**Interfaces:**
- Consumes: Task 3 (`offer_key`, campos), Task 5 (`RawExtraction`, `interpret_offer`).
- `llm.py` (nesta task, só): `class LlmUnavailable(Exception)` (re-tentável: rede, timeout, 5xx, "No model
  loaded"), `class LlmBadResponse(Exception)` (não re-tentável), `class LlmClient(Protocol)`:
  `def extract(self, image: bytes, mime: str) -> RawExtraction` e `def ping(self) -> bool`.
- `db.py` + tabelas (spec §7.4): `prints(id, sha256 UNIQUE, mime, caminho, criado_em)`,
  `import_batches(id, criado_em)`, `import_items(id, batch_id, print_id, nome_arquivo, status, tentativas,
  proxima_tentativa, erro, resposta_bruta, criados, renovados, ignorados, falhas, iniciado_em, concluido_em)`,
  `import_failures(id, item_id, dados_parciais, erros, status)`.
- `imports_repo.py`:
  - `PrintStore(dir: Path, conn)`: `save(content: bytes, mime: str) -> str` (id; reaproveita por sha256),
    `path(print_id: str) -> tuple[Path, str] | None`
  - `ImportRepository(conn)`: `create_batch() -> str`, `add_item(batch_id, print_id, nome_arquivo) -> str`,
    `next_ready(now: datetime) -> ImportItem | None` (NA_FILA com `proxima_tentativa` nula ou ≤ now, mais
    antigo), `set_status(...)`, `requeue_reading() -> int`, `get_batch(id)`, `list_batches(limit=20)`,
    `add_failure(item_id, parcial: dict, erros: list[str]) -> str`, `list_failures(status)`,
    `set_failure_status(id, status)`, `get_failure(id)`.
  - `ImportItem`, `ImportBatch`, `ImportFailure` (pydantic, campos = colunas; `erros: list[str]`, `parcial: dict`).
- `service.py`:
  - `class ImportService(products: ProductRepository, settings: SettingsRepository, repo: ImportRepository, prints: PrintStore, llm: LlmClient | None, lock: RLock, today_fn, now_fn, retry_waits_s: tuple[int, int] = (5, 30))`
  - `enqueue(files: list[UploadedFile]) -> tuple[str, list[str]]` — `UploadedFile(nome: str, content: bytes)`;
    detecta mime por assinatura (PNG `\x89PNG`, JPEG `\xff\xd8\xff`, WEBP `RIFF....WEBP`); recusa
    não-imagem ("{nome}: formato não suportado (use PNG, JPEG ou WEBP)") e > 20 MB ("{nome}: maior que
    20 MB"); devolve `(batch_id, recusas)`; se todos recusados, não cria lote e levanta `ValueError(recusas)`.
  - `process_next() -> bool` — pega `next_ready`, marca `LENDO`, chama `llm.extract(bytes, mime)` **fora
    do lock**, guarda `resposta_bruta`, interpreta cada oferta, aplica `upsert_offer`, registra falhas,
    fecha o item com contagens. `LlmUnavailable` ⇒ `tentativas += 1`; se < 3, volta a `NA_FILA` com
    `proxima_tentativa = now + retry_waits_s[tentativas-1]`; na 3ª ⇒ `ERRO` "Servidor LLM indisponível:
    {detalhe}". `LlmBadResponse` ⇒ `ERRO` "Resposta do modelo ilegível". `llm is None` ⇒ `ERRO`
    "Importação não configurada". Exceção inesperada ⇒ `ERRO` com a mensagem (item nunca fica `LENDO`).
  - `upsert_offer(data: ProductData, batch_print_ids: set[str]) -> Literal["criado", "renovado"]` — procura
    produto não-exemplo com `offer_key` igual (inclui expirados/inativos); renovação: `data_registro =
    today`, `print_id = data.print_id`, `disponivel_ate` novo se não `None`; se o encontrado veio de um
    print **deste lote**, `valor_minimo = min(...)`; demais campos intocados.
  - `resolve_failure(id, data: ProductData) -> ProductData` — valida (`422` vira `ValueError(erros)`),
    carimba `origem="IA"`, `print_id` da falha, `data_registro=today`, passa por `upsert_offer`, marca RESOLVIDA.
  - `discard_failure(id)`, `retry_item(id)` (ERRO → NA_FILA, zera tentativas).

- [ ] **Step 1: Testes que falham** (LLM stub devolvendo fixtures da Task 4; `today = 2026-11-23`)

```python
def test_process_creates_products_and_counts(svc):   # btg-app-lci-eq-cdb → 2 criados, item CONCLUIDO
def test_same_offer_repeated_in_print_keeps_lowest_min(svc):   # Review Focus 3: xp-web-tabela-lcd
    # LCD BNDES 15/03/2030 87% aparece 4x → 1 produto; criados conta 1, renovados 3
def test_reupload_renews_expired_and_keeps_manual_edits(svc):  # Review Focus 5
    # cria via import, simula 30 dias (today_fn), usuário edita nome/observações via repo,
    # reimporta → data_registro = novo today, nome editado preservado, não expirado
def test_failures_recorded_and_resolved(svc):   # oferta sem vencimento → falha ABERTA; resolve → produto origem IA com print_id
def test_print_dedup_by_hash(svc)
def test_enqueue_rejects_bad_files_but_keeps_good(svc):   # Review Focus 4 (parte do serviço)
def test_requeue_reading_on_start(svc)
def test_three_failures_then_error_then_retry(svc_with_failing_llm):   # Review Focus 1
    # 3 x process_next com now avançando além das esperas → item ERRO "Servidor LLM indisponível: …";
    # outro item do lote CONCLUIDO; retry_item → NA_FILA com tentativas 0; nenhum item fica LENDO
def test_bad_response_errors_immediately(svc)
```
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** `uv run pytest -q` PASS.
- [ ] **Step 5:** Commit `feat(importacao): fila, prints, renovação e falhas`.

### Task 7: Cliente LLM, worker, API e configuração

**Files:**
- Create: `backend/app/imports/llm.py`, `backend/app/imports/worker.py`, `backend/app/api/imports.py`
- Modify: `backend/app/deps.py`, `backend/app/main.py`, `backend/pyproject.toml` (+`python-multipart`)
- Test: `backend/tests/imports/test_llm.py`, `test_worker.py`, `backend/tests/api/test_imports.py`

**Interfaces:**
- Consumes: Task 5 (`RawExtraction`, `EXTRACTION_JSON_SCHEMA`), Task 6 (`ImportService`), `prompt_sistema.md` (Task 4).
- `llm.py` (acrescenta à Task 6; erros e protocolo já existem):
  - `@dataclass LlmConfig(base_url: str, model: str, api_key: str | None, timeout_s: float)` +
    `LlmConfig.from_env() -> LlmConfig | None`.
  - `class OpenAICompatClient(config, http: httpx.Client)` — `POST {base_url}/chat/completions`,
    `temperature: 0`, `chat_template_kwargs: {"enable_thinking": false}`, mensagem de sistema = conteúdo
    de `prompt_sistema.md`, imagem como `data:{mime};base64,…`; `response_format` `json_schema`
    (`EXTRACTION_JSON_SCHEMA`); se a resposta for 400 citando `response_format`, repete **sem** ele e
    passa a não enviá-lo (memoriza). Remove `<think>…</think>` e cercas ```json antes do parse; JSON
    inválido ⇒ uma nova chamada acrescentando "Sua resposta anterior não era JSON válido: {erro}" ⇒
    `LlmBadResponse`. `ping() -> bool` (`GET {base_url}/models`, timeout 3 s).
  - `class FakeLlmClient(fixtures_dir: Path)` — procura `<sha256 da imagem>.json`, senão `default.json`
    no diretório; `ping()` → `True`.
- `OpenAICompatClient` levanta `LlmUnavailable` para erro de rede/timeout/5xx e para 400 cujo corpo
  contenha "No model loaded"; `LlmBadResponse` para JSON inválido após a nova tentativa.
- `worker.py`: `class ImportWorker(service, wake: threading.Event, idle_s: float = 5.0)`: `start()`,
  `stop()`; laço `while not stopping: if not service.process_next(): wake.wait(idle_s); wake.clear()`;
  exceção inesperada é logada e o laço continua.
- `deps.Container` + `imports: ImportService | None`, `import_wake: threading.Event`; `build_container`
  monta `LlmConfig.from_env()` → `OpenAICompatClient`, ou `FakeLlmClient` se `LIQUIDO_LLM_FIXTURES`;
  `PrintStore(db_path.parent / "prints")`; chama `requeue_reading()`.
- `main.create_app`: `lifespan` que inicia/para o `ImportWorker` salvo `LIQUIDO_IMPORT_WORKER=0`.
- `api/imports.py` (prefixo `/api`):
  - `GET /imports/status` → `{"configurado": bool, "alcancavel": bool | None, "modelo": str | None}`
  - `POST /imports` (multipart, campo `arquivos`, vários) → `201 {"lote": ImportBatchView, "recusados": [str]}`;
    `503` "Importação não configurada (defina LLM_BASE_URL e CASA_LLM_MODEL)"; `422` se todos recusados.
    Acorda o worker (`import_wake.set()`).
  - `GET /imports` → `list[ImportBatchView]`; `GET /imports/{id}` → `ImportBatchView` (`404` pt-BR)
  - `POST /imports/items/{id}/retry` → `ImportItemView`
  - `GET /imports/failures?status=ABERTA` → `list[ImportFailureView]`
  - `POST /imports/failures/{id}/resolve` (corpo `ProductData`) → `201 ProductData` (`422` com erros)
  - `POST /imports/failures/{id}/discard` → `204`
  - `GET /prints/{id}` → arquivo com o mime gravado; `Cache-Control: private, max-age=31536000, immutable`
  - Views: `ImportItemView(id, nome_arquivo, print_id, status, erro, criados, renovados, ignorados, falhas)`,
    `ImportBatchView(id, criado_em, pendentes: int, itens: list[ImportItemView])`,
    `ImportFailureView(id, item_id, print_id, nome_arquivo, erros, parcial, status)`.

- [ ] **Step 1: Testes que falham** (`httpx.MockTransport`; nenhum acesso à rede)

```python
def test_sends_schema_image_and_parses(mock): ...       # corpo tem response_format, data URL, enable_thinking False
def test_falls_back_without_response_format(mock): ...   # 1ª 400 "response_format not supported" → 2ª sem → OK; 3ª chamada já sem
def test_strips_think_and_fences(mock): ...
def test_invalid_json_retries_once_then_bad_response(mock): ...
def test_no_model_loaded_is_unavailable(mock): ...      # 400 "No model loaded…" → LlmUnavailable
def test_from_env_none_without_vars(monkeypatch): ...
def test_worker_processes_until_empty_and_stops(): ...
def test_upload_mixed_files(client):   # Review Focus 4: 1 png + 1 .txt + 1 de 21 MB → 201, 1 item, 2 recusados com nomes
def test_upload_503_when_not_configured(client_sem_llm)
def test_status_endpoint(client)
def test_failure_resolve_and_discard(client)
def test_print_served_with_mime(client)
```
- [ ] **Step 2:** FAIL. **Step 3:** Implementar; `uv add python-multipart`. **Step 4:** `uv run pytest -q` PASS.
- [ ] **Step 5:** Commit `feat(importacao): cliente LLM, worker em segundo plano e API`.

### Task 8: Frontend — página Importar

**Files:**
- Create: `frontend/src/pages/Importar.tsx`, `frontend/src/pages/Importar.test.tsx`
- Modify: `frontend/src/App.tsx` (rota `/importar`), `components/Layout.tsx` (item "Importar" no menu, desktop e barra inferior), `api/types.ts`, `api/client.ts`

**Interfaces:**
- Consumes: API da Task 7.
- Produces em `client.ts`: `api.imports.status()`, `.upload(files: File[])` (FormData, campo `arquivos`;
  `request` atual é JSON — acrescentar caminho multipart), `.list()`, `.get(id)`, `.retry(itemId)`,
  `.failures()`, `.resolve(id, p)`, `.discard(id)`; `printUrl(id) => "/api/prints/" + id`.
  Tipos `ImportStatus`, `ImportItemView`, `ImportBatchView`, `ImportFailureView` espelhando o backend.

- [ ] **Step 1: Testes que falham** (`Importar.test.tsx`, API mockada):
  - não configurado ⇒ mostra "Importação não configurada" e o seletor fica desabilitado;
  - escolher 3 arquivos ⇒ chama `upload` com os 3; recusas aparecem por nome;
  - item `LENDO` ⇒ "lendo…"; `CONCLUIDO` com `criados=4, renovados=1` ⇒ "✓ 4 cadastradas · 1 renovada";
    `falhas=1` ⇒ "⚠ 1 falha"; `ERRO` ⇒ mensagem + botão "Tentar de novo" que chama `retry`;
  - com itens pendentes a consulta repete (`refetchInterval` 3000 ms) e para quando `pendentes === 0`;
  - ao concluir, invalida `["products"]` e `["simulate"]` (o ranking se atualiza).
- [ ] **Step 2:** FAIL. **Step 3:** Implementar (input `type=file multiple accept="image/png,image/jpeg,image/webp"`
  — no iPhone abre a galeria; área de soltar no desktop; histórico dos últimos lotes).
- [ ] **Step 4:** `npm test && npm run build` PASS.
- [ ] **Step 5:** Commit `feat(ui): página Importar com acompanhamento do lote`.

### Task 9: Frontend — falhas, produtos, detalhe e configurações

**Files:**
- Modify: `pages/Importar.tsx` (seção Falhas), `components/ProductForm.tsx`, `components/ProductDetail.tsx`, `pages/Produtos.tsx`, `pages/Configuracoes.tsx`, `lib/labels.ts`, `lib/settingsForm.ts`, `api/types.ts`
- Test: os `.test.tsx` correspondentes

**Interfaces:**
- Consumes: Tasks 3, 7, 8. `ProductData` ganha os campos da Task 3; `ProductView` com `idade_dias`, `expirada`.
- `ProductForm` ganha props opcionais `initial?: Partial<ProductData>`, `printId?: string` e
  `onSubmitOverride?: (p) => Promise<ProductData>` (usado para `resolve`). Campo novo "Disponível até"
  (opcional); "Registrado em dd/mm/aaaa" somente leitura quando houver.
- Labels: `OFERTA_ANTIGA` ⇒ `{icon: "⏳", text: "Oferta antiga", tone: "warn"}`; `IMPORTADO_IA` ⇒
  `{icon: "🤖", text: "Importado por IA", tone: "off"}`.

- [ ] **Step 1: Testes que falham**:
  - Falhas: lista com miniatura (`<img src="/api/prints/…">`), erros e "Corrigir" (abre o form
    preenchido com o print ao lado; salvar chama `resolve`) e "Descartar" (chama `discard`);
  - Produtos: mostra "há 3 dias"; expirada aparece com selo "expirada", em cinza, no fim; filtro
    "Mostrar expiradas" (padrão ligado) a esconde;
  - Detalhe: "Registrado em 20/11/2026 (há 3 dias)", "Disponível até", link "Ver print" quando `print_id`;
  - Configurações: seção "Ofertas" com "Alertar após (dias)" 14 e "Tirar do ranking após (dias)" 28;
    erro do servidor exibido.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** `npm test && npm run build` PASS.
- [ ] **Step 5:** Commit `feat(ui): falhas de importação, idade das ofertas e configurações`.

### Task 10: e2e, implantação e script de avaliação

**Files:**
- Create: `frontend/e2e/importar.spec.ts`, `backend/tests/fixtures/imports/e2e/default.json`, `frontend/e2e/fixtures/print-sintetico.png` (imagem gerada, sem conteúdo real), `backend/app/imports/eval.py`
- Modify: `frontend/playwright.config.ts` (env `LIQUIDO_LLM_FIXTURES`, `LLM_BASE_URL`/`CASA_LLM_MODEL` fictícios), `deploy/liquido.service`, `deploy/install.sh`, `README.md`

**Interfaces:**
- `eval.py`: `uv run python -m app.imports.eval [pasta]` (padrão `backend/calibration/prints`) — exige
  `LLM_BASE_URL`/`CASA_LLM_MODEL`; para cada imagem chama o modelo real, grava a resposta em
  `backend/calibration/respostas/<nome>.json`, interpreta, e, se existir `<nome>.esperado.json`, imprime
  acertos por campo (tipo, emissor, taxa escolhida, vencimento, mínimo) e o total. **Nunca grava no banco.**
  Sem a pasta: "Pasta de calibração não encontrada" e sai com código 1.
- Deploy: `liquido.service` ganha `EnvironmentFile=-/etc/liquido/liquido.env`; `install.sh` cria
  `/etc/liquido/liquido.env` (modo 600, dono root) **só se não existir**, com `LLM_BASE_URL=`,
  `CASA_LLM_MODEL=`, `LLM_API_KEY=` vazios e comentário pedindo para preencher; cria `backend/data/prints`.
  README: seção "Importar prints" (variáveis, auto-switch de modelo no servidor) e backup inclui `backend/data/prints/`.

- [ ] **Step 1:** e2e (desktop) — abrir `/importar`, enviar o PNG sintético, esperar "✓ 2 cadastradas ·",
  ir ao Comparador e ver um card com "Importado por IA"; corrigir uma falha (fixture com uma oferta sem
  vencimento) e ver o produto em Produtos.
- [ ] **Step 2:** `cd frontend && npm run build && npx playwright test --trace off` → FAIL, depois implementar, depois PASS (suite inteira).
- [ ] **Step 3:** `bash -n deploy/install.sh`; `uv run python -m app.imports.eval /nao/existe` → código 1 e a mensagem.
- [ ] **Step 4:** Commit `feat(importacao): e2e, implantação e script de avaliação`.

### Task 11 [Orquestrador]: calibração e importação real

1. Com o servidor LLM acessível e o modelo carregável: `uv run python -m app.imports.eval`; ajustar
   `prompt_sistema.md` até a taxa escolhida e o vencimento baterem em todos os prints de calibração
   (commits `fix(importacao): …`). Registrar tempo médio por print.
2. Subir o backend local com as variáveis reais, enviar os 16 prints pela página Importar, e relatar ao
   usuário: cadastradas, renovadas, ignoradas, falhas, erros.
3. Revisão final do branch inteiro (subagente) contra as duas specs antes de oferecer o merge.

---

## Cobertura da spec (autoverificação)

§2 objetivos → T3, T5–T9 · §3 env/token → T7, T10 · §6.1 chamada → T7 · §6.2 prompt → T4, T11 ·
§6.3 esquema → T5 · §6.4 interpretação → T5 · §7.1 campos/migração → T3 · §7.2 envelhecimento → T3, T9 ·
§7.3 renovação → T3 (`offer_key`), T6 · §7.4 tabelas → T6 · §8 worker → T7 · §9 API/telas → T7–T9 ·
§10 calibração → T4, T10, T11 · §12 implantação → T10 · §14 itens 1–2 → T1–T2; item 3 (captura) → T3, T5;
item 4 → T5 (botão cinza ignorado); item 5 → T11.
