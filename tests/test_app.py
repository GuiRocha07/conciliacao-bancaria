import io

import pytest
from openpyxl import load_workbook

from app import criar_app


@pytest.fixture
def cliente(tmp_path):
    app = criar_app(str(tmp_path / "teste.db"))
    app.config["TESTING"] = True
    return app.test_client()


def test_conciliacao_com_dados_de_exemplo(cliente):
    resposta = cliente.post("/conciliar", data={"exemplos": "1"})
    assert resposta.status_code == 302
    html = cliente.get(resposta.headers["Location"]).get_data(as_text=True)
    assert "Conciliação #1" in html
    assert "LIQUIDACAO BOLETO" in html
    assert "DEPOSITO EM DINHEIRO" in html  # crédito não identificado


def test_api_mostra_os_numeros_da_conciliacao(cliente):
    cliente.post("/conciliar", data={"exemplos": "1"})
    dados = cliente.get("/api/execucoes/1").get_json()
    r = dados["resumo"]
    assert r["agrupados"] == 1 and r["divergentes"] == 2 and r["nao_identificados"] == 3
    assert r["percentual_conciliado"] > 90


def test_excel_tem_as_quatro_abas(cliente):
    cliente.post("/conciliar", data={"exemplos": "1"})
    resposta = cliente.get("/execucoes/1/excel")
    planilha = load_workbook(io.BytesIO(resposta.data))
    assert planilha.sheetnames == ["Resumo", "Conciliados", "Não identificados", "Títulos em aberto"]


def test_envio_de_arquivos(cliente):
    extrato = "data;descricao;valor\n10/11/2026;PIX RECEBIDO LOJA AZUL;150,00\n"
    titulos = "titulo;cliente;cnpj;emissao;vencimento;valor\n7;Loja Azul;;01/11/2026;10/11/2026;150,00\n"
    resposta = cliente.post(
        "/conciliar",
        data={
            "extrato": (io.BytesIO(extrato.encode("latin-1")), "extrato.csv"),
            "titulos": (io.BytesIO(titulos.encode()), "titulos.csv"),
            "data_referencia": "2026-11-19",
        },
        content_type="multipart/form-data",
    )
    assert resposta.status_code == 302
    assert cliente.get("/api/execucoes/1").get_json()["resumo"]["conciliados"] == 1


def test_historico_lista_as_execucoes(cliente):
    cliente.post("/conciliar", data={"exemplos": "1"})
    assert "extrato_exemplo.ofx" in cliente.get("/historico").get_data(as_text=True)


def test_arquivo_errado_mostra_aviso(cliente):
    resposta = cliente.post(
        "/conciliar",
        data={"extrato": (io.BytesIO(b"x;y\n1;2\n"), "e.csv"), "titulos": (io.BytesIO(b"a\n"), "t.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert "Não consegui ler os arquivos" in resposta.get_data(as_text=True)
