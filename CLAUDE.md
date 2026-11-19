# Liquido — Comparador de Renda Fixa

Ferramenta pessoal (um usuário) que compara produtos de renda fixa brasileiros (CDB, LCI, LCA, CRI,
CRA, Tesouro Direto, Fundos RF) pelo **valor líquido na data alvo** informada pelo usuário.

- Design (fonte da verdade do "o quê"): `docs/superpowers/specs/2026-11-19-comparador-renda-fixa-design.md`
- Plano (fonte da verdade do "como", tarefa a tarefa): `docs/superpowers/plans/2026-11-19-comparador-renda-fixa.md`

Leia os dois antes de alterar qualquer coisa. Se o código e o design divergirem, pare e pergunte.

## Estrutura

```
backend/    FastAPI + domínio financeiro (Python 3.12+, uv)
frontend/   React + Vite + TypeScript + Tailwind (PWA)
deploy/     systemd + scripts de instalação/atualização (sem Docker)
docs/       design e planos
```

## Comandos

```bash
cd backend && uv sync && uv run pytest -q          # testes do backend
cd backend && uv run uvicorn app.main:app --reload # API em :8000
cd frontend && npm ci && npm run dev               # UI em :5173 (proxy /api -> :8000)
cd frontend && npm test && npm run build           # testes e build da UI
cd frontend && npx playwright test --trace off     # e2e (offline, com fixtures)
```

## Regras inegociáveis

1. **Dinheiro e taxas em `Decimal`** no backend. Nunca `float` em cálculo. Arredonde só na
   apresentação (frontend) e no valor de imposto (centavos, `ROUND_HALF_EVEN`).
2. **Taxas como fração**: 13,75% a.a. = `Decimal("0.1375")`. Nunca em "pontos percentuais" no domínio.
   A conversão de % acontece só nas bordas (parsing de fontes externas e formulários).
3. **Dias úteis ANBIMA, base 252** para acumular índices e taxas. **IR e IOF usam dias corridos.**
4. **Na API, valores Decimal trafegam como string** (`"71840.12"`). O frontend formata em pt-BR.
5. **Alíquotas, isenções e custos vêm de `Settings`**, nunca de constantes espalhadas.
6. **Testes não acessam a rede.** Clientes HTTP são testados com fixtures em `backend/tests/fixtures/`.
7. **TDD**: escreva o teste, veja falhar, implemente, veja passar, commit.
8. Valor que depende de projeção **sempre** carrega o alerta `PROJECAO`. Estimativa de saída antecipada
   do Tesouro **sempre** carrega `ESTIMATIVA_MERCADO`.

## Convenções

- Código (módulos, classes, funções) em inglês; **campos e termos do domínio em português**, como no
  design (`valor_liquido`, `data_vencimento`, `come_cotas`, `LCI`). Não traduza termos do mercado.
- UI 100% em pt-BR. Moeda `R$ 1.234,56`, datas `dd/mm/aaaa`, percentuais `13,65%`.
- Commits pequenos, mensagem no padrão `tipo(escopo): descrição` (feat, fix, test, docs, chore, refactor).
- Branch de trabalho: `claude/epic-einstein-30gtug`.

## Fluxo com agentes

- Diretivas e arquivos `.md`: escritos pelo orquestrador (Opus).
- Implementação de cada tarefa do plano: subagente **Sonnet**, que recebe a tarefa inteira do plano,
  as seções "Global Constraints" e "Review Focus", e este arquivo.
- Revisão de cada tarefa: subagente **Haiku**, comparando o diff com a tarefa do plano e com o design.
  Reprovação volta para o implementador com os pontos concretos.
