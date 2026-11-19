"""Histórico das conciliações em SQLite, para consultar e baixar de novo depois."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime

import pandas as pd

from .motor import Resultado

ESQUEMA = """
CREATE TABLE IF NOT EXISTS execucoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    criada_em TEXT NOT NULL,
    arquivo_extrato TEXT NOT NULL,
    arquivo_titulos TEXT NOT NULL,
    resumo TEXT NOT NULL,
    resultado TEXT NOT NULL
);
"""


def conectar(caminho: str) -> sqlite3.Connection:
    con = sqlite3.connect(caminho)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def _para_json(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso", force_ascii=False))


def salvar(con: sqlite3.Connection, resultado: Resultado, arquivo_extrato: str, arquivo_titulos: str) -> int:
    dados = {
        "conciliados": _para_json(resultado.conciliados),
        "nao_identificados": _para_json(resultado.nao_identificados),
        "em_aberto": _para_json(resultado.em_aberto),
        "saidas": _para_json(resultado.saidas),
    }
    cur = con.execute(
        "INSERT INTO execucoes (criada_em, arquivo_extrato, arquivo_titulos, resumo, resultado) VALUES (?, ?, ?, ?, ?)",
        (
            datetime.now().isoformat(timespec="seconds"),
            arquivo_extrato,
            arquivo_titulos,
            json.dumps(resultado.resumo),
            json.dumps(dados, ensure_ascii=False),
        ),
    )
    con.commit()
    return cur.lastrowid


def listar(con: sqlite3.Connection) -> list[dict]:
    linhas = con.execute("SELECT id, criada_em, arquivo_extrato, arquivo_titulos, resumo FROM execucoes ORDER BY id DESC")
    return [{**dict(r), "resumo": json.loads(r["resumo"])} for r in linhas]


def carregar(con: sqlite3.Connection, execucao_id: int) -> tuple[dict, Resultado] | None:
    r = con.execute("SELECT * FROM execucoes WHERE id = ?", (execucao_id,)).fetchone()
    if r is None:
        return None
    dados = json.loads(r["resultado"])

    def df(nome: str) -> pd.DataFrame:
        tabela = pd.DataFrame(dados[nome])
        for coluna in ("data", "data_pagamento", "vencimento", "emissao"):
            if coluna in tabela:
                tabela[coluna] = tabela[coluna].map(lambda v: date.fromisoformat(v[:10]) if v else v)
        return tabela

    resultado = Resultado(
        conciliados=df("conciliados"),
        nao_identificados=df("nao_identificados"),
        em_aberto=df("em_aberto"),
        saidas=df("saidas"),
        resumo=json.loads(r["resumo"]),
    )
    return dict(r), resultado
