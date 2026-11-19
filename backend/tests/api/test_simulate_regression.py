import json
import time
from decimal import Decimal as D
from pathlib import Path

import pytest

GOLDEN = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "golden_simulate.json").read_text())
TOL = D("1e-12")


def _values(client, alvo):
    body = client.post("/api/simulate", json={"valor": "50000", "data_alvo": alvo}).json()
    return {
        r["product"]["id"]: r
        for sec in ("vence_ate_data", "vence_depois")
        for r in body[sec]
        if r["valor_liquido"] is not None
    }


@pytest.mark.parametrize("alvo", sorted(GOLDEN))
def test_valores_identicos_ao_baseline(client_fixtures, alvo):
    atual = _values(client_fixtures, alvo)
    assert set(atual) == set(GOLDEN[alvo])
    for pid, esperado in GOLDEN[alvo].items():
        r = atual[pid]
        # o baseline é anterior à "sobra" do Tesouro, que passou a compor o valor líquido
        assert abs(D(r["valor_liquido"]) - D(esperado["valor_liquido"]) - D(r["sobra"])) <= TOL, pid
        assert abs(D(r["valor_bruto"]) - D(esperado["valor_bruto"])) <= TOL, pid
        assert abs(D(r["serie"][-1]["valor_bruto"]) - D(esperado["serie_last"])) <= TOL, pid


def test_simulate_2055_rapido_e_serie_limitada(client_fixtures):
    inicio = time.perf_counter()
    body = client_fixtures.post("/api/simulate", json={"valor": "50000", "data_alvo": "2055-01-01"}).json()
    assert time.perf_counter() - inicio < 5
    todos = body["vence_ate_data"] + body["vence_depois"]
    assert todos and all(len(r["serie"]) <= 61 for r in todos)
