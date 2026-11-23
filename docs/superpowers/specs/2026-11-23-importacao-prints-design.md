# Importação de ofertas por print (LLM local com visão) — Design

Data: 2026-11-23 · Status: aprovado (2026-11-23)
Complementa: `2026-11-19-comparador-renda-fixa-design.md` (que listava "importação por colagem" como
etapa futura — esta é essa etapa, por imagem em vez de texto).

## 1. Intenção

O usuário coleciona ofertas de renda fixa vendo os apps da **XP, BTG e Nubank** no celular. Cadastrar
cada uma à mão no formulário é lento. Ele quer **tirar prints e subir muitos de uma vez**; um LLM com visão
rodando no servidor caseiro (Unsloth Studio, API compatível com OpenAI) lê os prints, extrai as ofertas e
**cadastra direto** — sem revisão item a item.

Ofertas bancárias somem ou mudam de taxa em poucos dias. Por isso cada produto passa a registrar **o dia
em que foi cadastrado**, e o sistema usa isso para sinalizar ofertas velhas e tirá-las do ranking.

Troca consciente do usuário: **volume acima de precisão absoluta.** "Prefiro arcar com um produto errado
de vez em quando a revisar todos." O sistema compensa com rastreabilidade (o print fica guardado e
vinculado ao produto) e com regras determinísticas onde o erro mais provável mora.

## 2. Objetivos, não-objetivos e anti-objetivos

### Objetivos
- Página **Importar**: enviar vários prints de uma vez (PC e iPhone), acompanhar o processamento por
  arquivo, ver as falhas.
- Processamento **em segundo plano no servidor**, um print por vez, sobrevivendo a reinício do serviço
  e a aba fechada / iPhone bloqueado.
- Cada print pode conter **várias ofertas** (lista do app) ou uma (tela de detalhe).
- Detecção da **plataforma** (XP / BTG / Nubank) pelo layout/logotipo — o usuário não informa.
- **Cadastro automático** de toda oferta extraída que passe na validação existente.
- **Data de registro** em todo produto cadastrável (manual ou importado).
- **Envelhecimento**: alerta a partir de 14 dias; fora do ranking a partir de 28 dias (ambos
  configuráveis). Se o print mostrar "disponível até", a oferta sai do ranking nessa data, se for antes.
- **Reenvio renova**: print de uma oferta já cadastrada atualiza a data de registro em vez de duplicar.
- **Print guardado** e vinculado ao produto, visível no detalhe, para conferência e correção futura.
- Proteção específica contra a **"taxa equivalente CDB"** (gross-up) em LCI/LCA/CRI/CRA.

### Não-objetivos
- Revisão obrigatória antes de salvar (o usuário dispensou explicitamente).
- Oferta partida entre dois prints (o usuário garante prints completos; não há fusão entre imagens).
- Importar Tesouro Direto por print (já vem do CSV oficial, diariamente). Ofertas de Tesouro num print
  são ignoradas.
- **Fundos RF por print** (decisão do usuário: fora por ora, **entra numa fase seguinte**). Fundos num
  print são ignorados como o Tesouro e contados como "ignorado". O esquema e o parser não devem fechar a
  porta: a fase de fundos acrescentará `classe_tributaria`, prazo de resgate "D+N" e chave de renovação
  sem vencimento.
- Outras plataformas além de XP, BTG e Nubank (o prompt é escrito para essas três; outras podem até
  funcionar, mas não são alvo).
- Escolha de modelo pela UI; processamento paralelo de vários prints; OCR clássico como fallback.

### Anti-objetivos (falharia mesmo "funcionando")
- **Taxa equivalente gravada como taxa do produto** — LCA de 95% CDI cadastrada como 111,8% CDI e
  subindo para o topo do ranking. É o erro mais provável e o mais caro.
- **Chute silencioso**: campo que o modelo não viu sendo preenchido com valor plausível. Campo ausente
  vira falha visível, nunca um palpite.
- **Oferta perdida em silêncio**: print que falhou, ou oferta que não passou na validação, sem aparecer
  na lista de falhas.
- Ofertas velhas competindo no ranking como se estivessem vigentes.
- Token da API no repositório.

## 3. Restrições

- Todas as regras inegociáveis do `CLAUDE.md` valem: `Decimal`, taxas como fração, conversão de % só na
  borda, `Settings` para limites, testes sem rede, TDD, alertas `PROJECAO`/`ESTIMATIVA_MERCADO`.
- Continua **um único processo** (uvicorn/systemd). Sem serviço extra, sem Redis, sem Celery.
- Servidor LLM: Unsloth Studio, OpenAI-compatível, na rede local. Configuração **por variável de
  ambiente** (é infraestrutura, não parâmetro financeiro — por isso não vai para `Settings`):
  - `LLM_BASE_URL` — ex.: `http://192.168.0.33:8889/v1`
  - `CASA_LLM_MODEL` — ex.: `unsloth/Qwen3.5-9B-GGUF`
  - `LLM_API_KEY` — token Bearer. Nunca commitado; vai no `EnvironmentFile` do systemd.
  - Sem essas variáveis, a página Importar mostra "importação não configurada" e a API recusa uploads (503).
- Em 2026-11-23 o servidor responde em `/v1/models`; o modelo está instalado mas **descarregado** (o
  primeiro pedido o carrega — pode demorar). **Ainda não verificado**: se o GGUF foi carregado com o
  projetor de visão (mmproj) e se o servidor honra `response_format` com JSON Schema. A primeira tarefa
  do plano verifica as duas coisas com uma chamada real (ver §10).
- Tempo esperado: dezenas de segundos por print num 9B. Um lote de 30 prints pode levar 15+ minutos.
- Testes automatizados nunca chamam o LLM: cliente falso com respostas gravadas em `backend/tests/fixtures/`.

## 4. Abordagens consideradas

| Abordagem | Trade-off | Decisão |
|---|---|---|
| **A) Fila em segundo plano no próprio processo** (tabela SQLite + thread worker) | Sobrevive a reinício e a aba fechada; mantém processo único; um pouco mais de código (fila, estados) | **Escolhida pelo usuário** |
| B) Navegador orquestra, um print por requisição | Mais simples, sem fila; para quando o Safari suspende a aba (iPhone bloqueado) — inviável em lote | Descartada |
| C) Serviço worker separado (outro systemd) | Mesmo resultado de A com mais implantação; fere "processo único" | Descartada |

Sobre o LLM: **sem agente, sem ferramentas.** É uma tarefa de leitura de uma passada. Confiabilidade vem
de prompt de sistema dedicado + saída estruturada + decisões determinísticas no nosso código (§6).

## 5. Fluxo

```
Importar (UI) ──POST /api/imports (multipart, N arquivos)──▶ cria lote + N itens "NA_FILA", grava prints
                                                              responde na hora com o id do lote
worker (thread, 1 por vez) ──▶ pega próximo item NA_FILA ──▶ LENDO
     ├─ chama LLM (imagem + prompt) ─▶ JSON bruto (guardado no item)
     ├─ para cada oferta extraída:
     │     interpreta textos → ProductData (borda: % → fração, dd/mm/aaaa → date)
     │     escolhe a taxa (§6.3) → valida (validate_product existente)
     │     ├─ já existe oferta igual (§7.3)? → renova data_registro
     │     ├─ válida → cria produto (origem IA, vínculo ao print)
     │     └─ inválida/ambígua → registra FALHA (com erros e dados parciais)
     └─ item → CONCLUIDO (com contagens) ou ERRO (LLM falhou / resposta ilegível)
UI consulta GET /api/imports/{lote} periodicamente enquanto houver itens pendentes
```

## 6. Extração com o LLM

### 6.1 Chamada
- `POST {LLM_BASE_URL}/chat/completions`, mensagem de sistema (§6.2) + mensagem do usuário com a imagem
  em `image_url` (data URL base64). Temperatura 0.
- Saída estruturada: `response_format` `json_schema` se o servidor suportar (verificado na tarefa 1);
  senão, "responda só com JSON" + parse + **uma** nova tentativa com o erro de parse no prompt.
- Qwen3.5 pode "pensar" antes de responder: desligar o modo de raciocínio se o servidor permitir
  (ex.: `chat_template_kwargs: {"enable_thinking": false}`) e, em todo caso, descartar qualquer bloco
  `<think>` antes do parse.
- Timeout generoso (configurável por env, padrão 300 s — o primeiro pedido carrega o modelo).

### 6.2 Prompt de sistema (em português, versionado em arquivo no repositório)
Conteúdo obrigatório:
- Papel: transcrever ofertas de renda fixa de prints de apps brasileiros. **Transcrever, não calcular.**
- Vocabulário fechado: `tipo` ∈ CDB, LCI, LCA, LCD, CRI, CRA, FUNDO_RF, TESOURO, OUTRO (os três últimos só
  para o código ignorar — LF, CDCA, CPR etc. caem em OUTRO), `plataforma` ∈ XP, BTG, NUBANK, DESCONHECIDA; `liquidez` ∈ NO_VENCIMENTO, DIARIA,
  DIARIA_APOS_CARENCIA, DESCONHECIDA. "A mercado" (venda no secundário antes do vencimento) e
  "No Vencimento" → NO_VENCIMENTO.
- **Cartão cortado** na borda do print (ex.: só o título visível): marcar `"cortada": true` e não inventar
  o resto. O código conta como "ignorado (cortado)", não como falha.
- Linhas repetidas numa tabela (mesma oferta com quantidade/preço diferentes) são transcritas como vierem;
  a renovação da §7.3 colapsa as iguais (no mesmo lote, fica o **menor** `valor_minimo` — decisão minha).
- Telas de **posição/carteira** ("Meu saldo", "Resgatar", rendimento acumulado) não são ofertas: resposta
  com lista vazia.
- Campos extras por oferta: `codigo` (código do papel, se visível), `juros` ("Mensal", "No vencimento"…),
  `amortizacao` (texto como veio, ex.: "Anual a partir de 15/03/2032"). O botão "Investir" cinza é
  irrelevante (mercado fechado).
- Números e datas **exatamente como aparecem** ("95% do CDI", "IPCA + 7,00%", "15/03/2029",
  "R$ 1.000,00"). Nada de converter, arredondar ou completar.
- **Todas** as taxas visíveis de cada oferta, cada uma com o rótulo que a acompanha na tela.
- Campo não visível → `null`. Nunca inferir.
- Notas por plataforma: como reconhecer XP, BTG e Nubank (logotipo, cores, cabeçalho), onde cada uma
  mostra taxa, vencimento, aplicação mínima, liquidez e "disponível até", e como cada uma rotula a taxa
  equivalente. *(Estas notas são o ponto de calibração: escritas a partir de prints reais — §10.)*
  O que os prints de calibração de 2026-11-23 já mostram:
  - **XP app (celular)**: tema escuro, botões amarelos "Saiba mais"/"Investir"; cartão com título
    "CDB BANCO XP S.A. - NOV/2028", linhas "Rentabilidade" (ex.: "102,5% CDI", em verde), "Aplicação
    mínima", "Resgate" ("A mercado"), "Vencimento"; selos "Risco Baixo", "Cobertura FGC", "Primário".
  - **XP site (desktop)**: tabela com cabeçalho preto e colunas "Vencimento", "Rentabilidade (a.a)",
    "Liquidez", "Juros", "Amortização", "Rating (BR)", "Risco", "Aplicação Mínima", "Quantidade
    Disponível" e botão amarelo "Investir". O nome vem **truncado** ("CDB BANCO COOPERATIVO SIC...") e
    traz tipo + emissor + mês/ano. Ícones: $ = isento de IR, bandeira = oferta primária, ✓ = FGC.
    Rentabilidade sem indexador ("15,100%") é **prefixada** (o cabeçalho diz a.a.). IPCA aparece como
    **"IPC-A + 7,800%"**. A "Aplicação Mínima" é o PU de uma unidade (ex.: R$ 1.093,03) — gravar como veio.
  - **BTG app (celular)**: tema claro; abas "CDB, LC, LCA, LCI e LF" / "CRA, CRI, CDCA e CPR"; cartão
    "LCI - Pós-fixado" + emissor ("Banco BTG Pactual"); linhas "Aplicação mínima", "Taxa" ("90,00% do
    CDI"), **"Taxa eq. CDB"** ("108,46% do CDI") e "Prazo | Venc." ("365 dias | 23/11/2027" — usar a data).
  - **XP site — carteira** ("Meu saldo", "Rendimento bruto/líquido", botão "Resgatar"): é **posição do
    usuário, não oferta** → nenhuma oferta extraída. Contém dados pessoais; fica só local.
  - **XP site — faixas por aplicação mínima**: a mesma LCI (ex.: "LCI CEF - NOV/2028") aparece em várias
    linhas com taxas diferentes conforme o mínimo (R$ 250 mil → 85,5%, R$ 1 milhão → 89%, R$ 5 milhões →
    89,5%). Cada linha é uma oferta própria (taxa diferente ⇒ produto diferente); o mínimo importa para a
    faixa "indisponível" do comparador.
  - **XP site — LCD** (Letra de Crédito do Desenvolvimento: BNDES, BRDE, BANDES): tipo novo criado na
    fase 1 (§14); o vocabulário do prompt inclui `LCD`.
  - **BTG site (desktop)**: abas "Destaque", "CDB, LC, LCA, LCI e LF", "CRA/CRI/CDCA", "Debêntures",
    "Títulos Públicos"; filtros "Indexador", "Limpar filtros"; tabela "Produto e risco", "Vencimento"
    (com "Prazo: 365 dias" embaixo), "Taxa" ("90,00% do CDI", "18,26% a.a.", "IPCA + 12,04%"), **coluna
    "Taxa Eq. do CDB"**, "Juros", "Amortização", "Aplicação mínima", botão "Investir" com contorno azul
    (às vezes desabilitado/cinza). Nome "CRA - FS FLORESTAL - FS BIO" = tipo + emissor; abaixo vem o
    código do papel ("CRA0240066D", "22L2288690") — guardar em `observacoes`.
  - **Em tabelas, o rótulo de uma taxa é o cabeçalho da coluna** ("Taxa", "Taxa Eq. do CDB",
    "Rentabilidade (a.a)"). O prompt precisa dizer isso explicitamente.
  - **Juros periódicos / amortização** (CRI/CRA do BTG: "Juros: Mensal/Semestral/Anual",
    "Amortização: Anual a partir de 15/03/2032"; LCI BTG com selo "Juros mensais"): o domínio modela
    esses produtos como bullet. Ver §14.
  - **BTG site — CDB**: "Taxa" e "Taxa Eq. do CDB" trazem o **mesmo valor** (103,75% / 103,75%). Após
    descartar a coluna "Eq.", sobra uma — correto. Cabeçalho azul no topo.
  - **BTG site — LCA de 181 dias** (vencimento 24/05/2027, "Prazo: 181 dias"): com a carência mínima de
    LCA hoje em `Settings` (9 meses), essa oferta real **cai em falhas**. Ver §14.
  - **Nubank (só app; não há versão desktop)**: tema escuro com roxo; aba "Investimentos Ultravioleta"
    com abas "CDB", "LCI/LCA", "Fundos"; cartão com selo "CDI (Pós-fixado)" e "Exclusivo Ultravioleta",
    nome "CDB Ultravioleta", linha principal **"109% do CDI · 18 NOV 2031"** (taxa e vencimento juntos,
    **mês abreviado por extenso**), selos "Risco baixo", "Proteção FGC", **"IR · 15%"**, e linhas
    "Emissor" (o emissor real: "Banco Original", "Neon Financeira") e "Valor mínimo".
    - **Taxa riscada**: o Nubank mostra a taxa anterior **riscada** acima da nova ("~~107% do CDI~~" →
      "108% do CDI"). O modelo deve rotular `"rotulo": "riscada"`; o código descarta como descarta "eq.".
    - **"IR · 15%" não é taxa de rentabilidade**: o prompt manda não transcrevê-la, e o código descarta
      qualquer taxa com rótulo/texto contendo "IR" isolado (defesa dupla — senão vira um PRE de 15%).
    - "Exclusivo Ultravioleta" vai para `observacoes` (o usuário vê a tela, então tem acesso).
    - Fundos do Nubank ("Nu Reserva Planejada", "Últimos 12 meses 14,13%", "Resgate 11 dias úteis") →
      ignorados (fundos fora desta fase).

### 6.3 Esquema da resposta (por print)
```json
{
  "plataforma": "XP | BTG | NUBANK | DESCONHECIDA",
  "ofertas": [
    {
      "tipo": "LCA",
      "emissor": "Banco Exemplo",
      "nome_exibido": "LCA Banco Exemplo - Mai/2028",
      "taxas": [
        {"texto": "95% do CDI", "rotulo": "Rentabilidade"},
        {"texto": "111,76% do CDI", "rotulo": "Equivalente CDB"}
      ],
      "vencimento": "15/05/2028",
      "aplicacao_minima": "R$ 1.000,00",
      "liquidez": "NO_VENCIMENTO",
      "carencia": null,
      "disponivel_ate": "28/11/2026",
      "taxa_adm": null,
      "prazo_resgate": null
    }
  ]
}
```

### 6.4 Interpretação determinística (nosso código, testável sem LLM)
- **Parser de taxa** (`texto` → `indexador` + `taxa` fração): "95% do CDI"/"95% CDI"/"102,5% CDI" →
  PCT_CDI; "CDI + 1,20%"/"CDI+1,900%" → CDI_MAIS; "IPCA + 7,00%"/"IPC-A + 7,800%"/"IPCA+ 7%" →
  IPCA_MAIS; "14,20% a.a."/"Pré 14,2%"/"15,100%" (número puro) → PRE. Vírgula decimal, quantidade
  variável de casas. Texto não reconhecido → taxa descartada.
- **Escolha da taxa**:
  1. Descarta taxas cujo rótulo (ou texto) contenha, sem diferenciar acento/caixa: "equivalente",
     "equiv", "eq." / "eq " (o BTG usa "Taxa eq. CDB"), "bruto", "gross", "sem ir"/"com ir" no sentido
     de comparação. **Esta é a defesa principal.** *(Lista em constante do módulo
     de importação — são termos de interface, não parâmetros financeiros.)*
  2. Para tipos isentos de IR (conforme `Settings.ir_exempt_types`), se sobrarem duas taxas de mesmo
     indexador e a maior ≈ menor / (1 − alíquota de IR para o prazo até o vencimento, pela tabela de
     `Settings`), com tolerância de **±3% relativo**, descarta a maior. É defesa secundária: cada
     plataforma calcula o gross-up do seu jeito (no print do BTG, 90% CDI com 547 dias aparece como
     107,93%, enquanto 90/(1−0,175) = 109,09% — 1,1% de diferença).
  3. Sobrou **exatamente uma** → é a taxa. Zero ou mais de uma → **falha** "taxa ambígua", listando os
     textos vistos.
  4. Quando o passo 1 ou 2 descartou algo, o produto guarda em `observacoes` uma linha
     "Importado: ignorei 111,76% do CDI (Equivalente CDB)".
- Datas `dd/mm/aaaa`, `dd/mm/aa` e `dd MMM aaaa` com mês abreviado em português ("18 NOV 2031",
  maiúsculas ou não). Data sem dia ("mai/2028") → falha (não se inventa o dia).
  Valores `R$ 1.234,56` → `Decimal`.
- `plataforma` DESCONHECIDA ou `tipo`/`emissor`/vencimento ausentes → falha.
- `plataforma` gravada como `"XP"`, `"BTG"` ou `"Nubank"` (mesma grafia do seed). *(Decisão minha.)*
- `aplicacao_minima` ausente → `valor_minimo = 0` e linha em `observacoes` "mínimo não visível no print".
  *(Decisão minha: o mínimo só afeta a faixa "indisponível"; falhar por ele lotaria as falhas.)*
- `carencia`: data `dd/mm/aaaa` → `data_carencia`; "N dias" / "D+N" → `data_registro + N` dias
  corridos (conversão na borda); qualquer outra grafia → falha. *(Decisão minha.)*
- `liquidez` DESCONHECIDA → assume NO_VENCIMENTO e anota em `observacoes` *(decisão minha: é o caso
  mais comum e o mais conservador para o cálculo)*.
- Tipo TESOURO → ignorado sem falha (contado como "ignorado" no item).
- `nome`: `nome_exibido` se houver; senão "{tipo} {emissor}".

## 7. Modelo de dados

### 7.1 Novos campos em `ProductData` (todos opcionais, compatíveis com o JSON já gravado)
| Campo | Tipo | Uso |
|---|---|---|
| `data_registro` | `date \| None` | dia do cadastro ou da última renovação |
| `disponivel_ate` | `date \| None` | prazo da oferta visto no print (ou informado à mão) |
| `origem` | `"MANUAL" \| "IA"` (padrão MANUAL) | selo "importado por IA" |
| `print_id` | `str \| None` | print de onde a oferta veio (último, em caso de renovação) |
| `juros_periodicos` | `"MENSAL" \| "TRIMESTRAL" \| "SEMESTRAL" \| "ANUAL" \| None` | cupom visto no print; preenchido ⇒ alerta `MODELO_SIMPLIFICADO` até a fase 3 (§14) |
| `amortizacao` | `{periodicidade, inicio: date} \| None` | cronograma visto no print ("Anual a partir de 15/03/2032"); idem |

- Criação manual (`POST /api/products`) e duplicação carimbam `data_registro = hoje`. Edição **não**
  renova a data *(decisão minha: editar não prova que a oferta continua de pé)*. O formulário ganha
  `disponivel_ate` opcional e mostra `data_registro` como somente leitura.
- **Migração**: produtos existentes não-exemplo sem `data_registro` recebem a data do dia da migração
  (na inicialização, idempotente). Assim nada expira de surpresa no dia da atualização.
- Exemplos (`exemplo=True`) e Tesouro não envelhecem.

### 7.2 Envelhecimento (calculado na leitura, nada é gravado)
- Novos `Settings`: `oferta_alerta_dias = 14`, `oferta_expira_dias = 28` (validação: 1 ≤ alerta <
  expira). Editáveis em Configurações, seção nova "Ofertas".
- `idade = hoje − data_registro` (dias corridos).
- **Expirada** se `idade ≥ oferta_expira_dias` ou `hoje > disponivel_ate`. `ManualSource` pula
  expiradas como já pula inativas. `ativo` continua sendo só do usuário — expirar não mexe nele, e uma
  renovação traz a oferta de volta automaticamente.
  *(Decisão minha: derivar em vez de gravar dispensa agendador e faz mudança de configuração valer na hora.)*
- **Alerta** `OFERTA_ANTIGA` (novo `AlertCode`) quando `idade ≥ oferta_alerta_dias`:
  "Oferta registrada há N dias — confira se ainda está disponível".
- Selo `IMPORTADO_IA` (novo `AlertCode`, informativo) nos produtos com `origem = IA`.
- Página Produtos: mostra a idade ("há 3 dias"), selo "expirada" e um filtro "mostrar expiradas"
  (padrão: mostrar, em cinza, no fim da lista).

### 7.3 Renovação (deduplicação)
Mesma oferta = mesmos `tipo`, `plataforma`, `indexador`, `taxa`, `data_vencimento` e `emissor`
normalizado (sem acento, caixa, espaços extras e sufixos "S.A."/"SA"/"Banco"). `plataforma` também é
normalizada (caixa/acento, e "BTG Pactual" ≡ "BTG", já que o formulário sugere "BTG Pactual" e o seed
usa "BTG"). Vale contra qualquer
produto não-exemplo, manual ou importado, inclusive expirado. Na renovação: `data_registro = hoje`,
`print_id` = novo print, `disponivel_ate` = o novo (se o print trouxer). Demais campos ficam como estão
(se o usuário corrigiu algo à mão, a correção sobrevive). Taxa diferente = oferta nova (a antiga expira
sozinha).

### 7.4 Novas tabelas SQLite
- `import_batches(id, criado_em)`
- `import_items(id, batch_id, print_id, nome_arquivo, status, tentativas, erro, resposta_bruta,
  criados, renovados, ignorados, falhas, iniciado_em, concluido_em)` — `status` ∈ NA_FILA, LENDO,
  CONCLUIDO, ERRO.
- `import_failures(id, item_id, dados_parciais JSON, erros JSON, status)` — `status` ∈ ABERTA,
  RESOLVIDA, DESCARTADA.
- `prints(id, sha256, mime, caminho, criado_em)`. Arquivos em `data/prints/<sha256>.<ext>` (mesmo
  diretório do banco; entra no backup). O mesmo arquivo enviado duas vezes reaproveita o registro de
  print, mas é processado de novo (o objetivo pode ser justamente renovar).

## 8. Worker

- Thread daemon iniciada no `lifespan` do FastAPI; desligável por env (testes e2e usam LLM falso).
- Laço: pega o item NA_FILA mais antigo → LENDO → processa → estado final. Sem item, espera
  (evento acordado pelo upload, com timeout de segurança).
- **Nunca segura `Container.lock` durante a chamada ao LLM**; só para ler/gravar no banco.
- Na inicialização, itens LENDO (processo morreu no meio) voltam para NA_FILA.
- Falha de rede/timeout/5xx do LLM: até 3 tentativas com espera crescente; esgotou → ERRO com a
  mensagem. Resposta não-JSON após a nova tentativa → ERRO. Botão "tentar de novo" na UI recoloca na fila.
- Um print com 5 ofertas onde 1 falha: 4 cadastradas, 1 em falhas, item CONCLUIDO.

## 9. API e telas

### API (estrutura interna livre, desde que cubra)
- `POST /api/imports` (multipart, vários arquivos; aceita PNG, JPEG, WEBP, HEIC*) → lote.
- `GET /api/imports` (lotes recentes com contagens) · `GET /api/imports/{lote}` (itens e status).
- `POST /api/imports/items/{id}/retry`.
- `GET /api/imports/failures?status=ABERTA` · `POST /api/imports/failures/{id}/discard` ·
  `POST /api/imports/failures/{id}/resolve` (corpo: `ProductData` corrigido pelo formulário). Resolver
  valida como o cadastro normal, carimba `origem = IA`, `print_id` da falha e `data_registro = hoje`,
  passa pela renovação da §7.3 (pode renovar em vez de criar) e marca a falha RESOLVIDA.
  *(Decisão minha: o produto corrigido continua rastreável ao print.)*
- `GET /api/prints/{id}` (a imagem).
- `GET /api/imports/status` → configurado? servidor LLM alcançável?

\* HEIC: prints do iPhone saem em PNG, então HEIC só se for barato; senão rejeitar com mensagem clara.

### Telas
1. **Importar** (nova, no menu): área de soltar/selecionar arquivos (no iPhone abre a galeria, seleção
   múltipla); lista do lote atual com cada arquivo e seu estado (na fila · lendo · ✓ 3 cadastradas,
   1 renovada · ⚠ 1 falha · ✕ erro [tentar de novo]); histórico curto de lotes.
   ```
   Lote de 23/11 14:02 — 12 prints · 9 concluídos · 1 lendo · 2 na fila
     IMG_0412.png   ✓ 4 cadastradas · 1 renovada
     IMG_0413.png   ⚠ 2 cadastradas · 1 falha
     IMG_0414.png   ⟳ lendo…
   ```
2. **Falhas** (seção da página Importar): cada falha com a miniatura do print, os erros e os dados
   parciais; "Corrigir" abre o `ProductForm` preenchido, com o print ao lado; "Descartar".
3. **Detalhe do produto**: "Registrado em dd/mm/aaaa (há N dias)", "Disponível até", selo "importado
   por IA" e link "ver print" (abre a imagem).
4. **Configurações**: seção "Ofertas" com os dois prazos.

## 10. Verificação com o modelo real (fora do pytest)

- **Tarefa 1 do plano (spike):** chamada real ao servidor com um print — confirma visão, saída
  estruturada, desligamento do raciocínio e tempo por print. Resultado registrado no plano. Se o modelo
  não enxergar imagens, **parar e perguntar** (há outros modelos instalados: Qwen3.8-27B, gemma-4-12b).
- **Conjunto de calibração**: prints reais em `backend/calibration/prints/` — **só na máquina local,
  ignorado pelo git** (decisão do usuário). Ao lado de cada print, um `<nome>.esperado.json` escrito à
  mão (também local). Um script manual (`uv run python -m app.imports.eval`) roda o modelo real contra
  eles e mostra acertos por campo; sem a pasta, avisa e sai.
  Em 2026-11-23 existem: `xp-app-cdb-lista.png`, `btg-app-lci-eq-cdb.png`, `xp-web-tabela-cdb-a.png`,
  `xp-web-tabela-cdb-b.png`, `xp-web-tabela-lca.png`. Faltam prints do Nubank (o usuário vai enviar).
- Os testes automatizados (commitados) usam só **JSON**: respostas do modelo no formato da §6.3,
  transcritas desses prints (dados de ofertas públicas, sem imagem nem dado pessoal), em
  `backend/tests/fixtures/imports/`. Nenhuma imagem real entra no git; o e2e usa uma imagem sintética
  qualquer com o LLM falso.

## 11. Qualidade e testes

- pytest: parser de taxas (todas as grafias da §6.4), escolha da taxa (rótulo, gross-up, ambígua),
  datas/valores, dedup/renovação, envelhecimento (limites 13/14/27/28 dias, `disponivel_ate`),
  migração de `data_registro`, worker com LLM falso (sucesso, erro com tentativas, JSON ruim, LENDO
  órfão volta à fila), API de upload/status/falhas.
- Vitest: página Importar (estados), falhas, selos e idade no detalhe/lista, seção de Configurações.
- Playwright: subir 2 prints com LLM falso → produtos aparecem no comparador com selo; uma falha
  corrigida pelo formulário.

## 12. Implantação

- `deploy/` ganha um `EnvironmentFile` (ex.: `/etc/liquido/liquido.env`, permissão 600) com as três
  variáveis; `install.sh` cria o arquivo-modelo sem o token e avisa para preenchê-lo.
- `data/prints/` criado na instalação; README cita no backup.

## 13. Fluxo de trabalho

Orquestrador (Opus) escreve design e plano; cada tarefa do plano é implementada por subagente **Sonnet**
e revisada por subagente **Haiku** contra a tarefa e este design (conforme `CLAUDE.md`). Branch:
`claude/importacao-prints`.

## 14. Decisões do usuário sobre os casos encontrados nos prints (2026-11-23) e fases

1. **Prazo mínimo de LCI/LCA** — corrigir as regras, não contornar. Pesquisa (2026-11-23): a Resolução
   CMN 5.215/2025 fixou **6 meses** para LCI e LCA sem atualização por índice de preços; atreladas a
   índice de preços: **LCA 12 meses, LCI 36 meses**. Hoje `Settings` tem um só número por tipo (LCI 12,
   LCA 9) → passa a ter prazo por tipo **e** por indexação (IPCA vs demais), com esses padrões.
   *(Fontes de blogs/corretoras; conferir o texto da resolução no BCB na implementação.)*
2. **LCD** — **novo tipo de produto**. Pesquisa (2026-11-23): Lei 14.937/2024; emitida só por bancos de
   desenvolvimento (BNDES, BRDE, BANDES, BDMG…); **isenta de IR para pessoa física** (logo entra em
   `ir_exempt_types`/`iof_exempt_types` por padrão); prazo mínimo **12 meses**. Cobertura FGC: as
   fontes divergem e a tabela da XP mostra o selo FGC nas LCDs — **verificar na lei** antes de fixar o
   padrão de `cobertura`. Configurável como as demais.
3. **Juros periódicos e amortização** — **modelar de verdade** (não só alertar). É mudança no motor de
   cálculo, com decisões próprias (o que acontece com o cupom recebido: fica parado, é reinvestido a quê?
   IR retido a cada cupom nos tributados), então vira **fase própria** com design próprio. Até lá, a
   importação já **captura** periodicidade de juros, cronograma de amortização (texto e data de início)
   em campos estruturados, e o produto recebe o alerta `MODELO_SIMPLIFICADO`.
4. **"Investir" desabilitado** (BTG) — é mercado fechado no horário do print. **Importar normalmente**,
   sem nota.
5. **Prints reais** — ao final da fase de importação, o orquestrador sobe os prints de
   `backend/calibration/prints/` pela API real (modelo real) e relata o resultado.

### Fases (cada uma com seu plano; 1 e 2 neste ciclo)
1. **Regras**: prazos mínimos por indexação (item 1) + tipo LCD (item 2). Pequena, no domínio.
2. **Importação por print** (este documento). Depende de 1 para cadastrar LCD e LCA de 6 meses.
3. **Cupons e amortização** (item 3): design novo.
4. **Fundos por print**: design novo.

## 15. Deixado para o implementador

Biblioteca de upload no frontend, intervalo de polling, layout fino das telas, nomes internos de módulos
(sugestão: `backend/app/imports/`), formato exato das mensagens, limite de tamanho de arquivo (sensato:
20 MB), redimensionamento da imagem antes de enviar ao LLM (se ajudar no tempo sem perder leitura).
