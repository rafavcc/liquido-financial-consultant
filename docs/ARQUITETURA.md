# Liquido — Arquitetura

Resumo de como a aplicação está organizada hoje. Para o "porquê" de cada decisão, veja o design em `docs/superpowers/specs/2026-11-19-comparador-renda-fixa-design.md`; para o histórico de tarefas, `docs/superpowers/plans/2026-11-19-comparador-renda-fixa.md`.

---

## 1. Visão geral

O Liquido é uma ferramenta pessoal (um usuário, sem login) que compara produtos de renda fixa brasileiros pelo **valor líquido na data de resgate informada**. Tudo roda num único processo no seu servidor, sem Docker.

```mermaid
flowchart LR
    U1[PC - navegador] -->|Tailscale HTTPS :8456| S
    U2[iPhone - PWA] -->|Tailscale HTTPS :8456| S
    U3[Rede local] -->|http 192.168.0.33:8456| S
    S[[Servidor w11<br/>uvicorn + FastAPI]] --> DB[(SQLite<br/>backend/data/liquido.db)]
    S --> F[[Frontend React<br/>frontend/dist]]
    S -->|HTTP| BCB[BCB SGS / Focus]
    S -->|HTTP| TD[Tesouro Transparente CSV]
```

---

## 2. Estrutura de pastas

```mermaid
flowchart TB
    R[liquido-financial-consultant/]
    R --> B[backend/ — Python]
    R --> FE[frontend/ — React]
    R --> D[deploy/ — systemd e scripts]
    R --> DOC[docs/ — design e plano]
    R --> C[CLAUDE.md — regras do projeto]

    B --> BA[app/ — código]
    B --> BT[tests/ — testes]
    BA --> API[api/ — rotas HTTP]
    BA --> DOM[domain/ — cálculos financeiros]
    BA --> DATA[data/ — banco e fontes externas]
    BA --> DEP[deps.py — montagem]
    BA --> MAIN[main.py — app FastAPI]

    FE --> SRC[src/]
    SRC --> PAGES[pages/ — 4 telas]
    SRC --> COMP[components/ — peças de tela]
    SRC --> LIB[lib/ — formatação e regras]
    SRC --> APIC[api/ — cliente HTTP e tipos]
```

---

## 3. Backend

### 3.1 Camadas

O backend é dividido em três camadas com dependências em um só sentido: a API usa o domínio e os dados; o domínio não conhece HTTP nem banco.

```mermaid
flowchart TB
    subgraph API["api/ — HTTP (FastAPI)"]
        RS[simulate.py]
        RP[products.py]
        RC[settings.py]
        RM[market.py]
    end
    subgraph DOM["domain/ — regras financeiras (sem I/O)"]
        SIM[simulation.py]
        SRC2[sources.py]
        PRD[products/<br/>bank · treasury · fund · factory]
        IDX[indexes.py — Selic, CDI, IPCA]
        TAX[taxes.py — IR, IOF]
        CAL[calendar.py — dias úteis ANBIMA]
        SET[settings.py — parâmetros]
    end
    subgraph DATA["data/ — persistência e fontes"]
        REPO[repositories.py]
        DB2[db.py — SQLite]
        MKT[market.py — cache e serviço]
        BCB2[bcb.py · focus.py · tesouro.py]
    end

    API --> DOM
    API --> DATA
    SRC2 --> PRD
    SIM --> SRC2
    SIM --> PRD
    PRD --> IDX
    PRD --> TAX
    PRD --> CAL
    IDX --> CAL
    DATA --> DOM
```

### 3.2 Rotas da API

Todas ficam sob `/api`. Valores monetários e taxas trafegam como **string** (ex.: `"71840.12"`, taxa `"0.1375"`).

```mermaid
flowchart LR
    CL[Frontend] --> A1["POST /api/simulate"]
    CL --> A2["GET /api/products"]
    CL --> A3["POST /api/products — 201"]
    CL --> A4["PUT /api/products/{id}"]
    CL --> A5["DELETE /api/products/{id}"]
    CL --> A6["POST /api/products/{id}/duplicate"]
    CL --> A7["GET /api/products/tesouro"]
    CL --> A8["GET /api/settings"]
    CL --> A9["PUT /api/settings"]
    CL --> A10["POST /api/settings/reset"]
    CL --> A11["GET /api/market"]
    CL --> A12["POST /api/market/refresh"]
    CL --> A13["GET /api/health"]
```

Erros de validação voltam com `422` e `{"detail": ["campo: mensagem", ...]}` em português. Rotas inexistentes em `/api` voltam como JSON `404`.

### 3.3 Fluxo de uma simulação

Este é o caminho que roda toda vez que você muda o valor ou a data.

```mermaid
sequenceDiagram
    autonumber
    participant UI as Comparador (React)
    participant API as POST /api/simulate
    participant V as Validação
    participant M as Mercado (cache)
    participant S as simulate_all
    participant P as Produto (CDB, LCI, Tesouro, Fundo…)

    UI->>API: {valor, data_alvo}
    API->>V: valor > 0 e data_alvo > hoje?
    alt inválido
        V-->>UI: 422 em português
    else válido
        API->>M: snapshot (Selic, CDI, IPCA, Tesouro)
        M-->>API: snapshot (cache de 6 h; falha mantém o último)
        API->>S: produtos ativos + contexto
        loop cada produto
            S->>P: simulate(valor, data_alvo)
            P-->>S: resultado (seção, líquido, alertas, série)
        end
        S-->>API: três listas ordenadas
        API-->>UI: vence_ate_data · vence_depois · indisponiveis · mercado
    end
```

### 3.4 Seções do resultado

Cada produto cai em uma das três seções, conforme a data de vencimento em relação à sua data de resgate:

```mermaid
flowchart TD
    P[Produto] --> Q1{Valor ≥ mínimo<br/>e dados de mercado ok?}
    Q1 -- não --> IND[indisponiveis<br/>cinza]
    Q1 -- sim --> Q2{Vence até a data de resgate?}
    Q2 -- sim --> VA[vence_ate_data<br/>verde · ranking por líquido]
    Q2 -- não --> Q3{É resgatável antes do vencimento?}
    Q3 -- sim --> VD[vence_depois<br/>vermelho · estimativa de saída]
    Q3 -- não --> VD2[vence_depois<br/>vermelho · não resgatável<br/>ao fim da seção]
    VA -. dinheiro parado .-> NOTE[depois do vencimento não rende]
```

### 3.5 Tipos de produto

Uma classe base (`Product`) define a interface `simulate()`. Cada tipo implementa as regras próprias.

```mermaid
classDiagram
    class Product {
        <<abstract>>
        +data: ProductData
        +simulate(valor, data_alvo, ctx) SimulationResult
        #_unavailable()
        #_common_alerts()
        #_series_dates()
    }
    class BankProduct {
        +simulate()
    }
    class CDB
    class LCI
    class LCA
    class CRI
    class CRA
    class TreasuryProduct {
        +simulate()
        -flows()
        -pv_factor()
    }
    class FundoRendaFixa {
        +simulate()
        come_cotas_dates()
    }
    Product <|-- BankProduct
    BankProduct <|-- CDB
    BankProduct <|-- LCI
    BankProduct <|-- LCA
    BankProduct <|-- CRI
    BankProduct <|-- CRA
    Product <|-- TreasuryProduct
    Product <|-- FundoRendaFixa
```

A fábrica `build_product()` escolhe a classe pelo campo `tipo`. Títulos do Tesouro vêm de `TesouroSource`; produtos cadastrados à mão vêm de `ManualSource`.

### 3.6 Motor de cálculo

```mermaid
flowchart LR
    subgraph Entrada
        SN[Snapshot de mercado<br/>SGS 432 e 13522<br/>Focus anual e mensal<br/>CSV do Tesouro]
        ST[Settings<br/>IR, IOF, come-cotas,<br/>custódia, spread CDI-Selic]
    end
    SN --> IX[IndexPath<br/>Selic diária interpolada<br/>CDI = Selic − spread<br/>IPCA mensal]
    IX --> ACC[accrual_factor<br/>PRE · % CDI · CDI+ · IPCA+ · Selic]
    CAL2[BusinessCalendar<br/>ANBIMA, base 252<br/>índice O1 para contagens] --> ACC
    ACC --> TX[apply_taxes<br/>IR e IOF em dias corridos]
    ST --> TX
    TX --> OUT[valor líquido]
```

Regras que valem em todo o cálculo:
- **Decimal em todo lugar.** Nenhum `float` nos cálculos.
- **Dias úteis** (base 252) para juros; **dias corridos** para IR e IOF.
- **Taxas como fração**: `0.1375` = 13,75%.
- **Projeção sempre sinalizada**: produto que depende de Selic, CDI ou IPCA recebe o alerta `PROJECAO`.

### 3.7 Dados externos e cache

```mermaid
flowchart LR
    subgraph Fontes
        A[BCB SGS<br/>432 Selic meta<br/>13522 IPCA 12m]
        B[BCB Focus<br/>Selic e IPCA]
        C[Tesouro Transparente<br/>CSV de preços]
    end
    A & B & C --> FET[HttpFetchers<br/>timeouts por fonte]
    FET --> MS[MarketService]
    MS -->|TTL 6 h| CACHE[(market_cache<br/>SQLite)]
    MS -->|falha| CD[cooldown 15 min<br/>mantém o último dado]
    CACHE --> MS
    MS --> SNAP[MarketSnapshot]
```

Se uma fonte falhar, o sistema continua com o último dado salvo e mostra o aviso com a data. Testes nunca acessam a rede: usam fixtures em `backend/tests/fixtures/market/`.

### 3.8 Banco de dados

SQLite, em um arquivo só: `backend/data/liquido.db`.

```mermaid
erDiagram
    PRODUCTS {
        TEXT id PK
        TEXT payload "JSON do ProductData"
    }
    KV {
        TEXT key PK "settings · seeded"
        TEXT value "JSON"
    }
    MARKET_CACHE {
        TEXT source PK "bcb · focus · tesouro"
        TEXT payload
        TEXT fetched_at
        TEXT error
        TEXT failed_at
    }
```

Na primeira execução, `seed/products_example.json` cria os 13 produtos fictícios (marcados como `exemplo`).

### 3.9 Concorrência

Uma única conexão SQLite é compartilhada, protegida por um lock (`Container` em `deps.py`). Há um segundo lock só para a atualização do mercado, para que duas atualizações não rodem ao mesmo tempo. Nenhuma chamada de rede acontece dentro do lock do banco.

---

## 4. Frontend

### 4.1 Telas e componentes

```mermaid
flowchart TB
    APP[App.tsx — rotas] --> LAY[Layout<br/>cabeçalho e navegação<br/>barra inferior no celular]
    LAY --> P1[/ Comparador /]
    LAY --> P2[/produtos /]
    LAY --> P3[/configuracoes /]
    LAY --> P4[/mercado /]

    P1 --> IB[InputsBar<br/>valor e data]
    P1 --> MSTRIP[MarketStrip<br/>Selic · CDI · IPCA]
    P1 --> FIL[Filters]
    P1 --> PC[ProductCard]
    P1 --> PD[ProductDetail<br/>gaveta / folha]
    PD --> EC[EvolutionChart]
    PC --> AB[AlertBadge]

    P2 --> PF[ProductForm<br/>formulário dinâmico]
    P3 --> IRT[Tabelas IR e IOF]
    P3 --> PROJ[Projeções Focus / manual]
    P4 --> MCH[Gráfico de projeção]
```

### 4.2 Camadas do frontend

```mermaid
flowchart TB
    PG[pages/] --> CP[components/]
    PG --> TQ[TanStack Query<br/>cache, cancelamento, invalidação]
    CP --> LB[lib/<br/>format · parse · percent · money<br/>labels · settingsForm · market]
    TQ --> CL[api/client.ts<br/>fetch + ApiError]
    CL -->|/api| BE[(Backend)]
```

- **`lib/percent.ts` e `lib/money.ts`** fazem a conversão de % e de dinheiro com strings exatas, sem `float`.
- **`lib/format.ts`** só formata para exibição (pt-BR).
- **`api/client.ts`** guarda o `AbortSignal` das consultas, então uma simulação antiga é cancelada quando você digita de novo.

### 4.3 Como o Comparador reage a você

```mermaid
stateDiagram-v2
    [*] --> Ocioso
    Ocioso --> Digitando: muda valor ou data
    Digitando --> Digitando: nova tecla (cancela a anterior)
    Digitando --> Consultando: 400 ms sem digitar
    Consultando --> Mostrando: resposta ok
    Consultando --> Erro: 422 ou falha de rede
    Consultando --> Digitando: nova entrada cancela
    Mostrando --> Digitando: muda de novo
    Erro --> Digitando: corrige a entrada
```

Com entrada inválida, as seções de resultado somem e aparece só a mensagem de validação.

### 4.4 Instalável (PWA)

```mermaid
flowchart LR
    MAN[manifest.webmanifest<br/>nome, ícones, cores] --> IOS[iPhone: Compartilhar →<br/>Adicionar à Tela de Início]
    SW[service worker<br/>vite-plugin-pwa] --> SHELL[cache da casca do app]
    SW -->|/api/ sempre na rede| NET[nunca usa resposta antiga]
    META[index.html<br/>apple-touch-icon, theme-color,<br/>viewport-fit=cover] --> IOS
```

---

## 5. Entrega no servidor

### 5.1 Processo e portas

```mermaid
flowchart LR
    subgraph Servidor["PC w11 (WSL)"]
        UV[uvicorn app.main:app<br/>192.168.0.33:8456]
        TS[tailscale serve<br/>100.67.15.85:8456 HTTPS]
    end
    TS -->|proxy| UV
    LAN[Rede local] -->|http| UV
    TAIL[Tailnet] -->|https| TS
    NOTE["127.0.0.1:8456 — não usado<br/>(o serviço não escuta mais aí)"]
```

Antes de publicar, o `install.sh` confere se a porta já está ocupada e não sobrescreve um `tailscale serve` de outro serviço na porta 443.

### 5.2 Serviço e scripts

```mermaid
flowchart TB
    INST[deploy/install.sh] --> VENV[uv sync --frozen]
    INST --> FRONT[npm ci && npm run build]
    INST --> UNIT[renderiza liquido.service<br/>APP_DIR · USER · PORT · HOST]
    UNIT --> SYS[systemd: liquido.service<br/>Restart=on-failure]
    INST --> HC[verifica /api/health]
    INST --> TSS[tailscale serve --bg]

    UPD[deploy/update.sh] --> PULL[git pull --ff-only]
    PULL --> VENV
    PULL --> FRONT
    UPD --> RST[systemctl restart liquido]
    RST --> HC2[verifica /api/health<br/>lê HOST e PORT da unidade]
```

### 5.3 Como o FastAPI serve o frontend

Uma única aplicação atende tudo. `main.py` monta as rotas `/api` e, para o resto, devolve os arquivos de `frontend/dist`.

```mermaid
flowchart TD
    REQ[Requisição GET] --> Q1{Começa com /api ?}
    Q1 -- sim --> API[rota da API<br/>ou JSON 404]
    Q1 -- não --> Q2{Arquivo existe<br/>em dist/ ?}
    Q2 -- sim --> FILE[serve o arquivo<br/>assets/ com cache longo]
    Q2 -- não --> Q3{Caminho começa com assets/ ?}
    Q3 -- sim --> NF[404]
    Q3 -- não --> IDX[index.html<br/>SPA]
    REQ2[Caminho com ../ ou NUL] --> NF2[404 — sem sair de dist/]
```

Cabeçalhos: `index.html` e `sw.js` com `no-cache`; `assets/*` com cache imutável.

---

## 6. Testes

```mermaid
flowchart LR
    subgraph Backend["pytest — 136 testes"]
        T1[domain/ — cálculos,<br/>impostos, calendário]
        T2[data/ — fontes com fixtures]
        T3[api/ — rotas, 422, estáticos,<br/>regressão de valores]
    end
    subgraph Frontend["vitest — 128 testes"]
        T4[lib/ — formatação e conversão]
        T5[components/ e pages/]
    end
    subgraph E2E["Playwright — 3 testes"]
        T6[Comparador no desktop]
        T7[Barra inferior no iPhone 13]
    end
```

O teste de regressão (`test_simulate_regression.py`) compara valores de referência com tolerância de 1e-12. Se algum cálculo mudar sem querer, ele falha.

---

## 7. Regras do projeto (resumo do CLAUDE.md)

1. `Decimal` nos cálculos; arredondar só na apresentação.
2. Taxas como fração no domínio; `%` só nas bordas.
3. Dias úteis ANBIMA (base 252) para juros; dias corridos para IR e IOF.
4. Decimal trafega como string na API.
5. Alíquotas e custos vêm de `Settings`, nunca de constantes espalhadas.
6. Testes sem rede.
7. TDD: teste primeiro, vê-lo falhar, depois implementar.
8. Projeção e estimativa de mercado sempre sinalizadas.

---

## 8. Limitações conhecidas

- Ofertas de bancos (XP, BTG, etc.) são cadastradas à mão ou importadas; não há busca automática.
- Projeções são estimativas.
- Simulação do Tesouro leva alguns segundos com muitos títulos (otimizada, mas ainda a parte mais pesada).
- Renda+ e Educa+ usam modelo simplificado.
- Sem login: a proteção é a rede Tailscale e a rede local.
- Bind em `192.168.0.33` depende do WSL estar em modo espelhado ou com redirecionamento de porta.
