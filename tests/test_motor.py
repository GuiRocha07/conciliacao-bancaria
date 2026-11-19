from datetime import date

import pandas as pd

from conciliacao.motor import conciliar, semelhanca_nome

HOJE = date(2026, 11, 19)


def extrato(*linhas):
    return pd.DataFrame(
        [{"id": f"T{i}", "data": d, "descricao": desc, "documento": doc, "valor": v} for i, (d, desc, doc, v) in enumerate(linhas)]
    )


def titulos(*linhas):
    return pd.DataFrame(
        [{"titulo": t, "cliente": c, "cnpj": cnpj, "emissao": date(2026, 10, 1), "vencimento": venc, "valor": v}
         for t, c, cnpj, venc, v in linhas]
    )


TITULOS = titulos(
    ("1001", "Mercearia Bom Preço Ltda", "00111222000101", date(2026, 11, 10), 500.00),
    ("1002", "Mercearia Bom Preço Ltda", "00111222000101", date(2026, 11, 12), 300.00),
    ("1003", "Padaria Pão Dourado", "00111222000303", date(2026, 11, 5), 1000.00),
    ("1004", "Empório Vila Verde", "00111222000202", date(2026, 11, 30), 250.00),
    ("1005", "Café Recanto", "00111222000404", date(2026, 11, 1), 90.00),
)


def test_nome_parecido_ignora_acentos_e_ltda():
    assert semelhanca_nome("PIX RECEBIDO MERCEARIA BOM PRECO", "Mercearia Bom Preço Ltda") == 1.0
    assert semelhanca_nome("PIX RECEBIDO JOAO", "Mercearia Bom Preço Ltda") < 0.6


def test_pix_com_nome_e_valor_exato_e_conciliado():
    r = conciliar(extrato((date(2026, 11, 10), "PIX RECEBIDO PADARIA PAO DOURADO", "", 1000.00)), TITULOS, HOJE)
    linha = r.conciliados.iloc[0]
    assert (linha["status"], linha["titulos"]) == ("conciliado", "1003")


def test_boleto_que_cita_o_titulo_com_juros_vira_divergente():
    r = conciliar(extrato((date(2026, 11, 14), "LIQUIDACAO BOLETO 1003", "1003", 1020.00)), TITULOS, HOJE)
    linha = r.conciliados.iloc[0]
    assert linha["status"] == "divergente"
    assert linha["diferenca"] == 20.00
    assert linha["dias_atraso"] == 9


def test_um_pix_que_quita_dois_titulos_do_mesmo_cliente():
    r = conciliar(extrato((date(2026, 11, 12), "PIX RECEBIDO MERCEARIA BOM PRECO", "", 800.00)), TITULOS, HOJE)
    linha = r.conciliados.iloc[0]
    assert linha["status"] == "agrupado"
    assert set(linha["titulos"].split(", ")) == {"1001", "1002"}


def test_credito_sem_pistas_fica_nao_identificado():
    r = conciliar(extrato((date(2026, 11, 15), "DEPOSITO EM DINHEIRO", "", 777.00)), TITULOS, HOJE)
    assert r.conciliados.empty
    assert r.nao_identificados.iloc[0]["valor"] == 777.00


def test_mesmo_valor_mas_outro_cliente_nao_concilia():
    r = conciliar(extrato((date(2026, 11, 15), "PIX RECEBIDO JOAO DA SILVA", "", 250.00)), TITULOS, HOJE)
    assert r.conciliados.empty  # só o valor bater não basta


def test_saidas_nao_entram_na_conciliacao():
    r = conciliar(extrato((date(2026, 11, 15), "TARIFA", "", -9.90)), TITULOS, HOJE)
    assert len(r.saidas) == 1 and r.resumo["creditos"] == 0


def test_titulos_nao_pagos_viram_atraso_ou_a_vencer():
    r = conciliar(extrato((date(2026, 11, 10), "PIX RECEBIDO PADARIA PAO DOURADO", "", 1000.00)), TITULOS, HOJE)
    situacao = dict(zip(r.em_aberto["titulo"], r.em_aberto["situacao"]))
    assert situacao["1005"] == "em atraso"
    assert situacao["1004"] == "a vencer"
    assert r.resumo["titulos_em_atraso"] == 3  # 1001, 1002 e 1005
