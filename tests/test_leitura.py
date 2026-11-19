from datetime import date

import pytest

from conciliacao.leitura import ArquivoInvalido, ler_extrato, ler_ofx, ler_titulos

OFX = """
<OFX><BANKTRANLIST>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20261110120000
<TRNAMT>1500.50
<FITID>A1
<MEMO>PIX RECEBIDO LOJA TESTE
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20261111
<TRNAMT>-9.90
<FITID>A2
<MEMO>TARIFA
</STMTTRN>
</BANKTRANLIST></OFX>
"""


def test_le_ofx():
    df = ler_ofx(OFX)
    assert list(df["id"]) == ["A1", "A2"]
    assert df.loc[0, "data"] == date(2026, 11, 10)
    assert df.loc[0, "valor"] == 1500.50 and df.loc[1, "valor"] == -9.90
    assert df.loc[0, "descricao"] == "PIX RECEBIDO LOJA TESTE"


def test_le_extrato_csv_com_valor_brasileiro():
    df = ler_extrato("extrato.csv", "data;descricao;valor\n10/11/2026;PIX LOJA;1.234,56\n")
    assert df.loc[0, "valor"] == 1234.56
    assert df.loc[0, "data"] == date(2026, 11, 10)


def test_ofx_vazio_da_erro():
    with pytest.raises(ArquivoInvalido):
        ler_ofx("<OFX></OFX>")


def test_le_titulos_e_limpa_cnpj():
    texto = "titulo;cliente;cnpj;emissao;vencimento;valor\n100;Loja A;00.111.222/0001-01;01/11/2026;15/11/2026;500,00\n"
    df = ler_titulos(texto)
    assert df.loc[0, "cnpj"] == "00111222000101"
    assert df.loc[0, "vencimento"] == date(2026, 11, 15)


def test_titulos_sem_coluna_obrigatoria_da_erro():
    with pytest.raises(ArquivoInvalido, match="vencimento"):
        ler_titulos("titulo;cliente;valor\n1;A;10\n")
