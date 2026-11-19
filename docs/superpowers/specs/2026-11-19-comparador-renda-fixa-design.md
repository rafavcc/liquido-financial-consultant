# Comparador de Renda Fixa — Design

Data: 2026-11-19 · Status: aprovado (2026-11-19)

## 1. Intenção

Ferramenta **pessoal** (um único usuário) para apoiar decisões de investimento em renda fixa
no Brasil. O usuário informa **quanto** vai investir e **até quando** (os "MEUS INPUTS"); o
sistema calcula, para cada produto cadastrado, o **valor líquido na data informada** — já
descontados impostos e custos — e apresenta os produtos como **cards ranqueados pelo maior
rendimento**.

O objetivo é responder com confiança à pergunta "onde rende mais, de verdade, para o meu prazo?",
comparando de forma justa prefixados, pós-fixados, IPCA+, isentos e tributados.

Exigência explícita do usuário: **produto muito bem acabado**.

## 2. Objetivos, não-objetivos e anti-objetivos

### Objetivos
- Comparar: CDB, LCI, LCA, CRI, CRA, Tesouro Direto (todos os tipos) e Fundos de Renda Fixa.
- Indexadores: prefixado, % do CDI, CDI + taxa, IPCA + taxa, Selic (Tesouro Selic).
- Buscar índices automaticamente na internet (Selic, CDI, IPCA) e projeções (Focus/BCB).
- Buscar automaticamente os títulos do Tesouro Direto à venda, com taxas e preços do dia.
- Cadastro manual de produtos (formulário dinâmico por tipo).
- Ranking por valor líquido; seção separada (vermelha) para produtos que vencem depois da data.
- Página de configurações para parâmetros tributários, de custos e de projeção.
- Uso no PC e no iPhone (PWA instalável), via Tailscale, no servidor caseiro do usuário.

### Não-objetivos (por ora)
- Buscar ofertas de XP/BTG automaticamente (bloqueiam acesso automatizado / exigem login).
- Buscar ofertas na App Renda Fixa (apprendafixa.com.br): só há API interna não documentada; acesso
  automatizado bloqueado nesta sessão. Fica para uma fonte futura (preferência: importação por colagem).
- Importação por copiar/colar (o usuário trará os dados depois; será outra etapa).
- Multiusuário, login, renda variável, acompanhamento de carteira, reinvestimento após vencimento.
- Debêntures (extensão fácil no futuro, não pedida).

### Anti-objetivos (falharia mesmo "funcionando")
- Centavos errados silenciosamente (cálculo financeiro impreciso ou com dias corridos onde deveriam ser úteis).
- Apresentar projeção como certeza — todo valor dependente de projeção precisa de alerta visível.
- Mostrar índices desatualizados sem avisar (data da última atualização sempre visível).
- Falsa precisão em estimativas de saída antecipada de Tesouro (sempre rotuladas como estimativa de mercado).

## 3. Restrições

- Execução **nativa no Linux**, sem Docker. Servidor caseiro, acessado via Tailscale.
- PWA no iOS exige HTTPS → `tailscale serve` (certificado válido em `*.ts.net`). Nada exposto à internet.
- Backend Python + FastAPI; frontend React (decisões do usuário).
- Fontes de dados públicas e gratuitas (verificadas em 2026-11-19, todas respondendo):
  - **BCB SGS** — `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{n}?formato=json`
    - 432: meta Selic (% a.a.) — hoje 13,75
    - 12: CDI diário (% a.d.) · 4389: CDI anualizado base 252
    - 433: IPCA mensal (%) · 13522: IPCA acumulado 12 meses — último 4,63 (out/2026)
  - **BCB Focus (Olinda OData)** — `https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/`
    - `ExpectativasMercadoSelic` (mediana por reunião do Copom)
    - `ExpectativaMercadoMensais` (IPCA mês a mês)
    - `ExpectativasMercadoAnuais` (Selic fim de ano, IPCA anual) — hoje Selic 2026: 13,75; 2027: 12,75
  - **Tesouro Transparente** — CSV `PrecoTaxaTesouroDireto.csv` (~15 MB, histórico completo; `;` como
    separador, vírgula decimal). Colunas: `Tipo Titulo; Data Vencimento; Data Base; Taxa Compra Manha;
    Taxa Venda Manha; PU Compra Manha; PU Venda Manha; PU Base Manha`. Usar apenas a `Data Base` mais recente.

## 4. Abordagens consideradas

| Abordagem | Trade-off | Decisão |
|---|---|---|
| **A) FastAPI (Python) + React, serviços nativos** | Melhor motor financeiro (Decimal, calendário ANBIMA), UI de app; duas linguagens | **Escolhida** |
| B) Next.js full TypeScript | Uma linguagem; suporte fraco a dias úteis BR e decimal | Descartada: risco no núcleo do sistema |
| C) Django + HTMX | Admin grátis, mais simples; UI menos "app" | Descartada: acabamento inferior no iPhone |

Variação de A decidida pelo usuário: **sem Docker**, serviços systemd nativos.

## 5. Arquitetura

```
iPhone / PC ──HTTPS (tailscale serve)──▶ 127.0.0.1:8000  uvicorn (systemd: liquido.service)
                                           ├── /api/*      FastAPI
                                           └── /*          React compilado (static, PWA)
                                           │
                                           ├── SQLite  (data/liquido.db)  produtos, configs, cache de índices
                                           └── HTTP ──▶ BCB SGS · BCB Focus · Tesouro Transparente
```

- **Um único processo** em produção. O Node só é usado para compilar o frontend.
- Atualização de dados de mercado: **cache com validade** (configurável, padrão 6 h). Ao calcular,
  se o cache estiver vencido, busca de novo; na falha, usa o último valor e exibe aviso
  "dados de DD/MM HH:MM — falha ao atualizar". Botão "Atualizar agora" na UI. Sem serviço/timer extra.
- **Fontes de produtos plugáveis**: interface `ProductSource` (`load(ctx) -> list[Product]`). Na v1:
  `ManualSource` (SQLite) e `TesouroSource` (CSV do Tesouro). Futuro: importador por colagem, App Renda Fixa.
- Sem autenticação: o serviço escuta só em `127.0.0.1` e é publicado apenas na tailnet. *(decisão minha)*

### Estrutura do repositório (proposta)

```
backend/
  app/
    main.py                 # FastAPI, monta /api e o static do frontend
    api/                    # rotas: simulate, products, settings, market
    domain/
      calendar.py           # dias úteis ANBIMA (lib bizdays)
      indexes.py            # trajetórias projetadas de CDI/Selic/IPCA (fator diário por dia útil)
      taxes.py              # IR regressivo, IOF, come-cotas, isenções (lidos das configs)
      products/
        base.py             # Product (abstrata) + resultado de simulação
        bank.py             # CDB, LCI, LCA
        securitized.py      # CRI, CRA
        treasury.py         # TesouroSelic, TesouroPrefixado, TesouroPrefixadoJuros,
                            # TesouroIPCA, TesouroIPCAJuros, TesouroRendaMais, TesouroEducaMais
        fund.py             # FundoRendaFixa
      simulation.py         # orquestra: inputs → resultados → ranking/seções
    data/
      bcb.py, focus.py, tesouro.py   # clientes HTTP + parsing
      repository.py                  # SQLite (SQLAlchemy/SQLModel)
    seed/products_example.json       # produtos fictícios
  tests/
frontend/
  src/ (React + Vite + TypeScript + Tailwind)
deploy/
  liquido.service, install.sh, update.sh
docs/
```

## 6. Modelo de domínio

### Classe base `Product`
Campos comuns: `id`, `nome`, `tipo`, `emissor`, `plataforma` (XP, BTG, Tesouro…), `indexador`
(PRE, PCT_CDI, CDI_MAIS, IPCA_MAIS, SELIC), `taxa`, `data_vencimento`, `valor_minimo`,
`liquidez` (NO_VENCIMENTO | DIARIA | DIARIA_APOS_CARENCIA), `data_carencia`, `cobertura`
(FGC | TESOURO | NENHUMA), `ativo` (aparece na comparação), `exemplo` (produto fictício), `observacoes`.

Interface principal:
```python
def simulate(self, valor: Decimal, data_inicio: date, data_alvo: date, ctx: MarketContext, cfg: Settings) -> SimulationResult
```

`SimulationResult`: `secao` (VENCE_ATE_DATA | VENCE_DEPOIS | INDISPONIVEL), `valor_bruto`,
`ir`, `iof`, `custodia`, `taxa_adm`, `come_cotas`, `valor_liquido`, `rentab_liquida_pct`,
`taxa_liquida_aa` (equivalente anual, base 252), `data_efetiva_saida`, `dias_parado`,
`depende_projecao` (bool + quais índices), `resgatavel` (bool), `estimativa_mercado` (bool),
`alertas[]`, `serie_evolucao[]` (para o gráfico do detalhe).

### Subclasses e particularidades
| Classe | IR | IOF | Cobertura | Particularidades |
|---|---|---|---|---|
| CDB | regressivo | sim | FGC | qualquer indexador e regra de liquidez |
| LCI / LCA | isento | isento | FGC | carência mínima legal: LCI 12 meses, LCA 9 meses (validação no cadastro, configurável) |
| CRI / CRA | isento | isento | nenhuma | geralmente sem liquidez antes do vencimento; alerta de risco de crédito |
| Tesouro * | regressivo | sim | Tesouro | custódia B3; saída antecipada a preço de mercado |
| FundoRendaFixa | regressivo + come-cotas | sim | nenhuma | taxa adm, prazo de resgate D+N, sem vencimento, rentabilidade-alvo não garantida |

Isenções e alíquotas vêm **das configurações**, não de constantes no código.

## 7. Regras de cálculo

### 7.1 Datas e seções
- `data_inicio` = hoje (data da simulação); `data_alvo` deve ser posterior a hoje (validação). *(decisão minha)*
- **Vence até a data alvo** → valor congela no vencimento; `dias_parado` = dias corridos entre vencimento e data alvo.
  Ranqueado por `valor_liquido` (desc); empate → `taxa_liquida_aa`.
- **Vence depois da data alvo** → seção vermelha, ordenada pela **estimativa de saída** (desc):
  - Liquidez diária (ou carência já cumprida na data alvo): cálculo exato até a data alvo (com IR/IOF do prazo).
  - Tesouro: estimativa a preço de mercado (7.5), rótulo "estimativa — risco de mercado".
  - Sem liquidez na data: "Não resgatável" — vai ao fim da seção, sem valor.
- **Indisponível** (valor investido < `valor_minimo`): faixa cinza "Indisponíveis para este valor", no fim. *(decisão minha)*
- Fundos não têm vencimento: saída = data alvo; o resgate deve ser solicitado D+N antes (mostrado no card).

### 7.2 Dias úteis
Calendário ANBIMA (lib `bizdays`). Fatores diários por dia útil, base 252. IR/IOF usam dias corridos
(como na legislação).

### 7.3 Indexadores
- **PRE**: `fator = (1 + taxa)^(du/252)`.
- **% CDI**: para cada dia útil, `fator *= 1 + pct × cdi_diario(d)`, com `cdi_diario = (1+CDI_aa)^(1/252) − 1`.
- **CDI + taxa**: `fator *= (1+cdi_diario(d)) × (1+taxa)^(1/252)`.
- **IPCA + taxa**: IPCA mensal projetado aplicado pro rata por dia útil dentro de cada mês,
  composto com `(1+taxa)^(1/252)`. *(simplificação minha da metodologia de VNA; diferença irrelevante para comparação)*
- **Selic (Tesouro Selic)**: Selic diária projetada, aplicada sobre o PU com o ágio/deságio do CSV.

### 7.4 Projeções (trajetória diária)
- Selic: âncoras = Selic meta atual (hoje) e medianas anuais de fim de ano do Focus (31/12 de cada ano);
  interpolação linear diária entre âncoras; após a última âncora, último valor mantido. *(decisão minha:
  dispensa calendário do Copom; diferença desprezível para comparação)* CDI = Selic − `spread_cdi_selic` (config, padrão 0,10 p.p.).
- IPCA: medianas mensais do Focus (próximos ~12–18 meses), depois anuais convertidas em mensal; depois último valor.
- Modo **manual** nas configurações: o usuário informa Selic e IPCA por ano (cenários), substituindo o Focus.
- Qualquer produto com indexador ≠ PRE (ou fundo) recebe alerta "⚠ Depende de projeção de CDI/IPCA (Focus, DD/MM)".

### 7.5 Tesouro Direto
- Títulos ofertados = linhas da `Data Base` mais recente com `Taxa Compra` > 0 (ou PU compra > 0).
- Compra: quantidade = `valor / PU_compra` (fracionamento de 0,01 título; sobra é ignorada e mostrada). *(decisão minha)*
- Valor no vencimento: LTN = 1.000; NTN-B Principal = VNA projetado; LFT = VNA Selic projetado.
- Cupons (NTN-F 10% a.a., NTN-B 6% a.a., semestrais): tributados no recebimento e **ficam parados**
  até a data alvo (coerente com a regra "não rende após receber"). *(decisão minha, alinhada à regra do usuário)*
- Renda+ / Educa+: fluxo de pagamentos mensais após a data de conversão; parcelas recebidas até a data
  alvo ficam paradas; restante tratado como saída antecipada estimada. Rotulado "modelo simplificado".
- Saída antecipada estimada: PU na data alvo descontado à **taxa de venda atual** do mesmo título
  (hipótese: taxa de mercado inalterada).
- Custódia B3: 0,20% a.a. sobre o valor (config), com isenção do Tesouro Selic até R$ 10.000 (config);
  cobrada semestralmente/no resgate — modelada pro rata diária.

### 7.6 Tributos (todos configuráveis)
- IR regressivo sobre o rendimento: até 180 d 22,5% · 181–360 d 20% · 361–720 d 17,5% · > 720 d 15%.
- IOF regressivo sobre o rendimento nos primeiros 29 dias (tabela 96% → 3%), zero a partir do 30º dia.
- Come-cotas: último dia útil de maio e novembro; 15% (fundo de longo prazo) ou 20% (curto prazo);
  no resgate, complemento até a alíquota regressiva.
- Taxa de administração do fundo: descontada diariamente da rentabilidade (pro rata 252).

### 7.7 Alertas no card
Depende de projeção · valor > limite FGC (R$ 250 mil, config) · sem cobertura FGC (CRI/CRA/fundos) ·
estimativa de mercado (Tesouro antecipado) · fundo sem rentabilidade garantida · dinheiro parado N dias ·
produto fictício (selo "exemplo").

## 8. Telas

1. **Comparador** (home): barra "MEUS INPUTS" (valor, data alvo, Calcular), faixa de índices com data
   de atualização, filtros (tipo, plataforma, só com FGC, só isentos), seção ✅ ranqueada, seção 🔴,
   faixa cinza de indisponíveis. Inputs lembrados entre sessões.
   ```
   #1  LCA BTG · 95% CDI           Vence 10/03/2029 · Isento
       Líquido R$ 71.840 (+43,7%)  ≈ 13,1% a.a. líquido
       ⚠ Depende de projeção do CDI   ⏸ Parado 97 dias
   ```
2. **Detalhe do produto** (gaveta/modal ao tocar no card): decomposição bruto → IR → IOF → custódia
   → taxas → líquido; gráfico da evolução do valor no tempo; premissas de projeção usadas.
3. **Produtos**: lista com ativar/desativar, criar, editar, duplicar, excluir; formulário dinâmico
   por tipo, com validações (carência mínima LCI/LCA, vencimento futuro, taxa plausível). Tesouro
   aparece como somente leitura (vem da internet).
4. **Configurações**: tributação (tabelas IR/IOF, come-cotas, isenções por tipo), custos (custódia
   B3, isenção Tesouro Selic), projeções (Focus vs manual por ano; spread CDI–Selic), dados (validade
   do cache, botão atualizar, última atualização por fonte), alertas (limite FGC). Botão "restaurar padrões".
5. **Mercado** (opcional, simples): valores atuais e projeções usadas (tabela/gráfico).

UI em pt-BR, formatação BRL e datas brasileiras, tema claro/escuro, responsiva (cards em grade no PC,
lista no iPhone), PWA (manifest + service worker, ícone na tela inicial).

## 9. Produtos fictícios (seed)

Emissores fictícios, plataformas reais, selo "exemplo". Taxas coerentes com Selic 13,75% / CDI ~13,65%.

| # | Produto | Plataforma | Indexação | Vencimento | Liquidez |
|---|---|---|---|---|---|
| 1 | CDB Banco Alfa | XP | 112% CDI | 2028-11 | no vencimento |
| 2 | CDB Banco Liquidez | BTG | 100% CDI | 2030-11 | diária |
| 3 | CDB Banco Beta | XP | PRE 14,20% | 2027-11 | no vencimento |
| 4 | CDB Banco Gama | BTG | IPCA + 7,00% | 2029-05 | no vencimento |
| 5 | LCI Banco Delta | XP | 92% CDI | 2027-12 | no vencimento |
| 6 | LCA Banco Épsilon | BTG | 94% CDI | 2028-06 | no vencimento |
| 7 | LCA Banco Zeta | XP | PRE 12,10% | 2027-12 | no vencimento |
| 8 | LCI Banco Eta | BTG | 90% CDI | 2029-01 | diária após 12 meses |
| 9 | CRI Securitizadora Ômega | XP | IPCA + 7,80% | 2031-10 | no vencimento |
| 10 | CRA Agro Sigma | BTG | CDI + 1,20% | 2029-08 | no vencimento |
| 11 | CRA Agro Teta | XP | 97% CDI | 2028-09 | no vencimento |
| 12 | Fundo RF Referenciado DI | XP | alvo 99% CDI, adm 0,30%, D+0, LP | — | D+0 |
| 13 | Fundo RF Crédito Privado | BTG | alvo CDI + 1,5%, adm 0,80%, D+30, LP | — | D+30 |

Valores mínimos variados (R$ 1.000 a R$ 25.000) para exercitar a faixa "indisponível".

## 10. Qualidade e testes

- **Backend (pytest)**: testes de unidade do calendário, IR/IOF, come-cotas, cada indexador e cada classe
  de produto contra **valores de referência calculados à mão/planilha** e contra exemplos públicos
  (ex.: PU de LTN a partir da taxa do CSV deve bater com o PU publicado, tolerância de centavos).
  Testes das regras de seção (vence antes/depois/indisponível/não resgatável). Clientes HTTP testados
  com respostas gravadas (sem rede nos testes).
- **Frontend**: Vitest para formatação/componentes; Playwright para um fluxo ponta a ponta (inputs →
  cards → detalhe → configurações).
- Toda aritmética monetária em `Decimal`; arredondamento só na apresentação (e no IR, em centavos).

## 11. Implantação (servidor caseiro)

- Python gerenciado com `uv` (venv em `backend/.venv`); Node só para `npm run build`.
- `deploy/liquido.service` (systemd): `uvicorn app.main:app --host 127.0.0.1 --port 8000`, usuário
  dedicado/sem privilégios, `Restart=on-failure`.
- `deploy/install.sh`: cria venv, instala dependências, compila o frontend, instala e habilita o serviço,
  configura `tailscale serve --bg 8000`.
- `deploy/update.sh`: `git pull` → `uv sync` → `npm ci && npm run build` → `systemctl restart liquido`.
- Backup: o arquivo `data/liquido.db` (instrução no README).

## 12. Deixado para o implementador

Biblioteca de ORM (SQLModel vs SQLAlchemy puro), componentes de UI (ex.: shadcn/ui), biblioteca de gráficos
(ex.: Recharts), detalhes visuais, estrutura interna de rotas — desde que respeitem este documento.
