from datetime import date

import pandas as pd

from conciliacao.regua import etapa_para, montar_regua

HOJE = date(2026, 11, 19)


def titulos(*linhas):
    return pd.DataFrame([{"titulo": t, "cliente": c, "vencimento": v, "valor": valor} for t, c, v, valor in linhas])


def test_etapa_pelo_numero_de_dias():
    assert etapa_para(-10) is None  # cedo demais para cobrar
    assert etapa_para(-2).nome == "Lembrete"
    assert etapa_para(0).nome == "Vence hoje"
    assert etapa_para(5).nome == "Cobrança amigável"
    assert etapa_para(12).nome == "Cobrança firme"
    assert etapa_para(45).nome == "Último aviso"


def test_uma_mensagem_por_cliente_com_todos_os_titulos():
    acoes = montar_regua(titulos(
        ("10", "Loja A", date(2026, 11, 14), 100.0),
        ("11", "Loja A", date(2026, 11, 7), 50.0),
        ("20", "Loja B", date(2026, 12, 30), 999.0),  # vence daqui a 41 dias: ainda não entra
    ), HOJE)
    assert len(acoes) == 1
    acao = acoes[0]
    assert acao["etapa"] == "Cobrança firme"  # o título mais atrasado (12 dias) define o tom
    assert acao["titulos"] == "10, 11" and acao["total"] == 150.0
    assert "R$ 150,00" in acao["mensagem"] and "12 dias" in acao["mensagem"]
    assert acao["link_whatsapp"].startswith("https://wa.me/?text=")


def test_mais_atrasado_vem_primeiro():
    acoes = montar_regua(titulos(
        ("1", "Recente", date(2026, 11, 16), 10.0),
        ("2", "Antigo", date(2026, 10, 1), 10.0),
    ), HOJE)
    assert [a["cliente"] for a in acoes] == ["Antigo", "Recente"]


def test_tela_da_regua(tmp_path):
    from app import criar_app

    cliente = criar_app(str(tmp_path / "t.db")).test_client()
    cliente.post("/conciliar", data={"exemplos": "1"})
    html = cliente.get("/execucoes/1/regua").get_data(as_text=True)
    assert "Régua de cobrança" in html and "wa.me" in html
