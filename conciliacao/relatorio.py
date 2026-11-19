"""Relatório em Excel da conciliação, pronto para o financeiro."""

from __future__ import annotations

import io

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from .motor import Resultado

FORMATO_MOEDA = '"R$" #,##0.00;[Red]-"R$" #,##0.00'

ROTULOS = {
    "status": "Status", "confianca": "Confiança", "data_pagamento": "Pago em", "descricao": "Descrição no extrato",
    "valor_pago": "Valor pago", "titulos": "Título(s)", "cliente": "Cliente", "vencimento": "Vencimento",
    "valor_titulos": "Valor do(s) título(s)", "diferenca": "Diferença", "dias_atraso": "Dias de atraso",
    "motivos": "Por que casou", "id_extrato": "ID no extrato", "id": "ID", "data": "Data",
    "documento": "Documento", "valor": "Valor", "titulo": "Título", "cnpj": "CNPJ", "emissao": "Emissão",
    "situacao": "Situação",
}
COLUNAS_MOEDA = {"Valor pago", "Valor do(s) título(s)", "Diferença", "Valor"}


def gerar_excel(resultado: Resultado) -> bytes:
    resumo = pd.DataFrame(
        [(ROTULO_RESUMO.get(k, k), v) for k, v in resultado.resumo.items()], columns=["Indicador", "Valor"]
    )
    abas = {
        "Resumo": resumo,
        "Conciliados": resultado.conciliados,
        "Não identificados": resultado.nao_identificados,
        "Títulos em aberto": resultado.em_aberto,
    }
    saida = io.BytesIO()
    with pd.ExcelWriter(saida, engine="openpyxl") as escritor:
        for nome, df in abas.items():
            df.rename(columns=ROTULOS).to_excel(escritor, sheet_name=nome, index=False)
            _formatar(escritor.sheets[nome])
    return saida.getvalue()


def _formatar(aba) -> None:
    cabecalho = PatternFill("solid", fgColor="1E3A8A")
    for celula in aba[1]:
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = cabecalho
    for coluna in aba.columns:
        titulo = coluna[0].value
        largura = max(len(str(c.value or "")) for c in coluna) + 2
        aba.column_dimensions[get_column_letter(coluna[0].column)].width = min(max(largura, 10), 60)
        if titulo in COLUNAS_MOEDA:
            for c in coluna[1:]:
                c.number_format = FORMATO_MOEDA
        if titulo in {"Pago em", "Vencimento", "Data", "Emissão"}:
            for c in coluna[1:]:
                c.number_format = "DD/MM/YYYY"
    aba.freeze_panes = "A2"


ROTULO_RESUMO = {
    "creditos": "Créditos no extrato",
    "total_creditos": "Total recebido (R$)",
    "conciliados": "Conciliados (valor exato)",
    "agrupados": "Pagamentos de vários títulos",
    "divergentes": "Conciliados com diferença de valor",
    "nao_identificados": "Créditos não identificados",
    "valor_nao_identificado": "Valor não identificado (R$)",
    "valor_conciliado": "Valor conciliado (R$)",
    "percentual_conciliado": "% do valor conciliado",
    "titulos_em_atraso": "Títulos em atraso",
    "valor_em_atraso": "Valor em atraso (R$)",
    "titulos_a_vencer": "Títulos a vencer",
}
