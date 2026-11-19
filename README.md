# Liquido — Comparador de Renda Fixa

Ferramenta pessoal que compara produtos de renda fixa brasileiros (CDB, LCI, LCA, CRI, CRA, Tesouro Direto e fundos de renda fixa) pelo **valor líquido na data em que você precisa do dinheiro**: já descontados IR, IOF, come-cotas e custódia.

Você informa quanto quer investir e para quando precisa do dinheiro. O Liquido mostra, do melhor para o pior, o que rende mais, o que não vence a tempo e o que não está disponível para aquele valor.

Funciona no computador e no iPhone, e roda no seu próprio servidor (sem Docker, sem nuvem de terceiros). Seus dados ficam em um único arquivo no servidor.

## O que você precisa

- Um computador Linux sempre ligado (o "servidor"), com `systemd`.
- [uv](https://docs.astral.sh/uv/) (gerencia o Python do backend).
- [Node.js](https://nodejs.org/) 20 ou mais novo.
- [Tailscale](https://tailscale.com/download) instalado e conectado no servidor e nos aparelhos que vão usar o app. É ele que dá o endereço `https` privado.
- `git` e `curl`.

## Instalação

No servidor:

```bash
git clone <endereço-deste-repositório> liquido
cd liquido
./deploy/install.sh
```

O script confere as ferramentas, instala o que falta do projeto, gera a tela, cria o serviço `liquido` no systemd e publica o app no Tailscale. Ele pede a senha de administrador (`sudo`) só para instalar o serviço e configurar o Tailscale. No fim mostra o endereço, algo como `https://meu-servidor.minha-rede.ts.net`. Pode rodar de novo sem medo.

O serviço escuta só localmente na porta **8456** (`127.0.0.1:8456`). Se ela estiver ocupada, escolha outra:

```bash
LIQUIDO_PORT=9000 ./deploy/install.sh
```

Se o endereço https padrão do servidor no Tailscale já publica outro serviço, o instalador não mexe nele: o Liquido fica em `https://meu-servidor.minha-rede.ts.net:8456` (a mesma porta do serviço).

## Atualização

```bash
cd liquido
./deploy/update.sh
```

Baixa a versão nova, reconstrói e reinicia o serviço. No final o script confirma que o app respondeu.

## Backup

Tudo o que você cadastrou (produtos, configurações e o cache de dados de mercado) está em um único arquivo:

```
backend/data/liquido.db
```

Para fazer backup, copie esse arquivo (de preferência com o serviço parado: `sudo systemctl stop liquido`, copiar, `sudo systemctl start liquido`). Para restaurar, coloque o arquivo de volta no mesmo lugar.

## Adicionar à tela de início do iPhone

1. No iPhone, conectado ao Tailscale, abra o endereço do Liquido no **Safari**.
2. Toque em **Compartilhar** (o quadrado com a seta para cima).
3. Escolha **Adicionar à Tela de Início** e confirme.

O Liquido abre em tela cheia, como um app. A comparação sempre precisa de conexão com o servidor: sem rede, o app avisa o erro em vez de mostrar um resultado antigo.

## Onde ficam as configurações

Na própria tela **Configurações**: alíquotas e isenções de imposto, custódia da B3, spread do CDI, limite do FGC e fonte das projeções (Focus automático ou tabela manual). O botão "Restaurar padrões" volta tudo ao original. Nada é fixo no código: o que você salva ali vale para todas as comparações. Os produtos ficam na tela **Produtos** e os dados de mercado (Selic, CDI, IPCA, Focus, Tesouro) na tela **Mercado**.

## Como os cálculos funcionam

- **IR regressivo** (renda fixa tributada): a alíquota cai com o prazo, contada em dias corridos desde a aplicação: 22,5% até 180 dias, 20% de 181 a 360, 17,5% de 361 a 720 e 15% acima de 720. Incide só sobre o rendimento. LCI, LCA, CRI e CRA são isentos para pessoa física.
- **IOF**: cobrado apenas nos primeiros 30 dias, sobre o rendimento, com alíquota que cai a cada dia. Por isso, resgates em menos de 30 dias sofrem IOF, e LCI/LCA/CRI/CRA (que não têm liquidez nesse período) aparecem como "vencem depois".
- **Come-cotas** (fundos de renda fixa): em maio e novembro o fundo desconta uma parte do IR, adiantando o imposto. O Liquido simula essas datas e o IR restante no resgate.
- **Custódia**: taxa anual da B3 sobre o valor em Tesouro Direto (com a isenção para Tesouro Selic até o limite configurado).
- **Dias úteis**: os rendimentos são acumulados por dias úteis do calendário ANBIMA (base 252). IR e IOF usam dias corridos.
- **Projeções (Focus)**: para produtos atrelados a CDI, Selic ou IPCA, o futuro desses índices é estimado com as expectativas de mercado do Boletim Focus (Banco Central) ou com a tabela manual que você preencher. Quando o resultado depende disso, o produto recebe o aviso **Projeção**.
- **Tesouro antes do vencimento**: se você precisar do dinheiro antes do vencimento, o valor é uma estimativa de venda a preço de mercado (aviso **Estimativa de mercado**).

**Importante:** projeções são estimativas, não promessas. Taxas reais, impostos e regras de cada instituição podem diferir. Use o Liquido como apoio à decisão e confira o resultado final com a instituição antes de investir.

## Desenvolvimento local

```bash
cd backend && uv sync && uv run pytest -q          # testes do backend
cd backend && uv run uvicorn app.main:app --reload # API em :8000
cd frontend && npm ci && npm run dev               # interface em :5173 (proxy /api -> :8000)
cd frontend && npm test && npm run build           # testes e build da interface
cd frontend && npx playwright test --trace off     # testes de ponta a ponta (offline, com dados de teste)
```

Os testes de ponta a ponta precisam do build feito antes (`npm run build`) e usam um banco temporário, nunca o seu `liquido.db`. Para desenvolver sem internet, aponte `LIQUIDO_MARKET_FIXTURES=backend/tests/fixtures/market` ao subir o backend.

Variáveis de ambiente do backend: `LIQUIDO_DB` (arquivo do banco), `LIQUIDO_STATIC_DIR` (pasta da interface gerada, padrão `frontend/dist`) e `LIQUIDO_MARKET_FIXTURES` (usa dados de mercado de arquivo em vez da internet).
