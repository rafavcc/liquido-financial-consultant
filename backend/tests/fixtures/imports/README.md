# Respostas transcritas dos prints de calibração

Cada `<nome>.json` é uma `RawExtraction` (formato de `app/imports/schema.py`) transcrita **à mão** do
print real de mesmo nome em `backend/calibration/prints/` — pasta local, ignorada pelo git (decisão do
usuário: imagens reais não entram no repositório). Aqui só há texto de ofertas públicas.

Casos que cada arquivo cobre:

| Arquivo | Plataforma | O que exercita |
|---|---|---|
| `btg-app-lci-eq-cdb` | BTG app | "Taxa eq. CDB" ao lado da taxa real; cartão cortado no fim |
| `xp-app-cdb-lista` | XP app | "102,5% CDI"; "Resgate: A mercado"; cartão cortado |
| `xp-web-carteira-fundos` | XP site | tela de carteira (posição do usuário) → nenhuma oferta |
| `nubank-app-fundos` | Nubank app | fundo RF e multimercado → ignorados |
| `nubank-app-cdb-ultravioleta` | Nubank app | taxa + data no mesmo texto ("109% do CDI · 18 NOV 2031"), taxa riscada, "IR · 15%" |
| `xp-web-tabela-lcd` | XP site | LCD; mesma oferta (BNDES 15/03/2030 87%) 4 vezes |
| `btg-web-cri-cra-ipca` | BTG site | CRI/CRA IPCA+, código do papel, juros periódicos, amortização |
| `btg-web-lca-eq-cdb-a` | BTG site | coluna "Taxa Eq. do CDB"; LCA de 181 dias (prazo mínimo de 6 meses) |

Os prints foram tirados em 2026-11-23; testes que validam prazos usam essa data como "hoje".
