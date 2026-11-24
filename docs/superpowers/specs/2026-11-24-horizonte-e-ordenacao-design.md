# Horizonte da simulação e modos de ordenação — design

Complementa `2026-11-19-comparador-renda-fixa-design.md`. Onde este documento muda algo de lá, este vale.

## Por quê

O usuário quer avaliar **custo × benefício**: "vale prender o dinheiro por mais N anos por mais X% a.a.?".
Hoje o Comparador exige uma data alvo e ordena sempre por valor líquido nessa data. Isso responde "qual rende
mais até a minha data", mas não permite comparar as taxas por si só nem enxergar o custo do prazo.

## Objetivos

1. **Horizonte** escolhido no Comparador, com quatro modos:
   - `SEM_DATA`: cada produto simulado até o seu próprio horizonte natural (abaixo); ranking pela taxa.
   - `UM_ANO`: data alvo = hoje + 1 ano (mesmo dia/mês do ano seguinte), ajustada para o próximo dia útil.
     Garante > 360 dias corridos (IR 17,5%) com folga.
   - `DOIS_ANOS`: idem com + 2 anos. Garante > 720 dias (IR 15%).
   - `DATA`: data informada pelo usuário — comportamento atual.
2. **Ordenação** escolhida pelo usuário: valor líquido, taxa líquida a.a., custo-benefício, menor prazo de
   saída, segurança.
3. Novo fato de domínio: **prazo de saída** de cada resultado.

## Não objetivos

- Gráfico prazo × taxa com a fronteira desenhada (ideia registrada para depois).
- Mudar regras de cálculo de IR/IOF/rendimento de qualquer produto.
- Ordenação da seção "Indisponíveis" (continua por nome).

## Anti-objetivos

- Ranking sem data que compare **valores em R$** de produtos com prazos diferentes como se fossem comparáveis.
- Dominância calculada sobre produtos que o usuário escondeu com filtros.
- Tratar como "livre para sair" algo que só sai com risco de marcação (Tesouro prefixado/IPCA+).

## Definições

**Prazo de saída** (`prazo_saida_dias: int | None`, dias corridos a partir de hoje): quanto tempo até o
usuário poder ter o dinheiro de volta sem perder o contratado.

| Caso | prazo_saida_dias |
|---|---|
| Bancário `liquidez = DIARIA` | 0 |
| Bancário `DIARIA_APOS_CARENCIA` | dias até `data_carencia` (0 se já passou) |
| Bancário `NO_VENCIMENTO` (inclui CRI/CRA) | dias até o vencimento (ajustado a dia útil) |
| Fundo RF | `prazo_resgate_dias` (0 se nulo) |
| `TESOURO_SELIC` | 0 |
| Demais Tesouros | dias até o vencimento |
| Resultado indisponível | `None` |

**Horizonte natural** (só no modo `SEM_DATA`) — a data até a qual cada produto é simulado:

| Caso | Horizonte |
|---|---|
| Prazo de saída = vencimento (sem liquidez, Tesouro não-Selic) | vencimento |
| Liquidez diária, fundos, `TESOURO_SELIC` | min(vencimento, hoje + 1 ano) — fundos sem vencimento: hoje + 1 ano |
| Liquidez diária após carência | min(vencimento, max(data_carencia, hoje + 1 ano)) |

"hoje + 1 ano" usa a mesma regra do modo `UM_ANO` (mesmo dia do ano seguinte, próximo dia útil).
Tesouro Selic simulado por 1 ano é venda antecipada → carrega `ESTIMATIVA_MERCADO` (regra 8), como já
acontece hoje. Pós-fixados seguem com `PROJECAO`.

**Dominância**: entre resultados resgatáveis com `taxa_liquida_aa` e `prazo_saida_dias` não nulos, A domina B
se `taxa(A) ≥ taxa(B)` e `prazo(A) ≤ prazo(B)`, com pelo menos uma desigualdade estrita. Empate exato nos dois
não domina. Calculada **sobre a lista visível** (após filtros) e **dentro de cada seção**.

## Abordagens consideradas

- **A. Backend ordena e marca dominados** (parâmetro `ordenacao` na API). Cada troca de ordenação refaz a
  chamada; a dominância ignora os filtros do frontend e pode marcar uma LCI como dominada por um CDB escondido.
- **B. Backend entrega os fatos, frontend ordena e calcula a dominância sobre o visível.** Troca instantânea,
  coerente com os filtros, que já são aplicados no frontend. O frontend apenas **compara** valores (sem
  aritmética com dinheiro), então a regra 1 (Decimal no backend) se mantém.

**Escolhida: B** (decisão do usuário).

## Como fica

### Backend

- `SimulationResult` ganha `prazo_saida_dias: int | None`, preenchido por cada produto (função pura no
  domínio, testada por caso da tabela).
- `SimulationRequest`: `{ valor, horizonte: "SEM_DATA" | "UM_ANO" | "DOIS_ANOS" | "DATA", data_alvo?: date }`.
  `data_alvo` é obrigatória e > hoje só em `DATA`; ignorada nos demais. Default de `horizonte`: `DATA`
  (compatível com o cliente atual).
- O backend resolve a data de `UM_ANO`/`DOIS_ANOS` com o calendário ANBIMA e devolve
  `SimulationResponse.data_alvo: date | None` (nula em `SEM_DATA`) e `horizonte`, para a UI exibir.
- `SEM_DATA`: cada produto é simulado com `data_alvo = horizonte natural` dele. Todos os resultados
  resgatáveis vão para `vence_ate_data`; `vence_depois` vem vazia; `indisponiveis` como hoje. Ordem padrão
  do backend: taxa líquida a.a. desc.
- Ordenação padrão do backend nos modos com data: inalterada.

### Frontend

- Seletor de horizonte no `InputsBar` (quatro opções, segmentado). O campo de data só aparece em `DATA`.
  Em `UM_ANO`/`DOIS_ANOS` mostra a data resolvida pelo backend ("Resgate em 25/11/2027").
- Seletor de ordenação junto aos filtros:
  - **Valor líquido** (padrão nos modos com data; não oferecido em `SEM_DATA`)
  - **Taxa líquida a.a.** (padrão em `SEM_DATA`)
  - **Custo-benefício**: não dominados primeiro, por prazo de saída crescente (lê-se como uma escada:
    "quanto mais prendo, quanto mais ganho"); depois os dominados, por taxa desc.
  - **Menor prazo de saída**: prazo asc, desempate por taxa desc.
  - **Segurança**: cobertura `TESOURO` > `FGC` > `NENHUMA`, desempate por taxa desc.
  - Em todas: desempate final por nome; na seção "vencem depois", os não resgatáveis continuam no fim.
- Card: mostra o prazo de saída ("Liquidez diária", "Carência até dd/mm/aaaa", "Preso até dd/mm/aaaa",
  "D+30"). Dominado ganha selo discreto "Há opção melhor e mais curta" (em qualquer ordenação).
- `SEM_DATA`: uma seção única ("Todos os produtos — até o vencimento ou 1 ano"), destaque da taxa
  líquida a.a. e do prazo; valor líquido aparece como secundário com a data do horizonte natural.
- Horizonte e ordenação persistidos em `localStorage`, como valor e data. Ao mudar para `SEM_DATA`, se a
  ordenação salva for "valor líquido", troca para "taxa líquida a.a.".

## Restrições

Todas as do `CLAUDE.md`: Decimal no backend, taxas como fração, IR/IOF por dias corridos, Decimal como
string na API, alíquotas em `Settings`, TDD, sem rede nos testes, UI em pt-BR.

## Decisões deixadas ao implementador

- Nomes exatos de componentes e chaves de `localStorage`.
- Visual do seletor segmentado e do selo de dominado, seguindo o estilo de `Filters.tsx`.
- Comparação de strings decimais no frontend (helper em `lib/`), desde que sem aritmética de dinheiro.

## Chamadas que fiz (para o usuário conferir)

- 1 ano = mesmo dia do ano seguinte + próximo dia útil (não "hoje + 361").
- Tesouro Selic conta como liquidez diária (prazo 0) e é simulado por 1 ano no modo sem data.
- Demais Tesouros contam como presos até o vencimento.
- Em `SEM_DATA` não há seção "vencem depois"; "valor líquido" não é ordenação oferecida.
- Dominância calculada dentro de cada seção, sobre o que está visível.
