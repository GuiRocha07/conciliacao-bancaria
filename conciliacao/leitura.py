"""Leitura dos arquivos de entrada: extrato (OFX ou CSV) e títulos a receber (CSV)."""

from __future__ import annotations

import io
import re
from datetime import date, datetime

import pandas as pd

COLUNAS_EXTRATO = ["id", "data", "descricao", "documento", "valor"]
COLUNAS_TITULOS = ["titulo", "cliente", "cnpj", "emissao", "vencimento", "valor"]


class ArquivoInvalido(ValueError):
    """O arquivo não está no formato esperado."""


def _valor_brasileiro(texto: object) -> float:
    """"1.234,56" -> 1234.56 ; "1234.56" -> 1234.56 ; "-50,00" -> -50.0"""
    if isinstance(texto, (int, float)):
        return float(texto)
    s = str(texto).strip().replace("R$", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s)


def _data(texto: object) -> date:
    if isinstance(texto, date):
        return texto
    s = str(texto).strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, formato).date()
        except ValueError:
            continue
    raise ArquivoInvalido(f"Data inválida: {texto}")


def so_digitos(texto: object) -> str:
    return re.sub(r"\D", "", str(texto or ""))


# ------------------------------------------------------------------ extrato

def ler_ofx(texto: str) -> pd.DataFrame:
    """Lê as transações de um arquivo OFX (formato que os bancos exportam)."""
    blocos = re.findall(r"<STMTTRN>(.*?)</STMTTRN>", texto, flags=re.S | re.I)
    if not blocos:
        raise ArquivoInvalido("Nenhuma transação encontrada no OFX.")

    def campo(bloco: str, nome: str) -> str:
        achado = re.search(rf"<{nome}>([^<\r\n]*)", bloco, flags=re.I)
        return achado.group(1).strip() if achado else ""

    linhas = []
    for i, bloco in enumerate(blocos, start=1):
        linhas.append({
            "id": campo(bloco, "FITID") or f"T{i:04d}",
            "data": _data(campo(bloco, "DTPOSTED")[:8]),
            "descricao": campo(bloco, "MEMO") or campo(bloco, "NAME"),
            "documento": campo(bloco, "CHECKNUM") or campo(bloco, "REFNUM"),
            "valor": _valor_brasileiro(campo(bloco, "TRNAMT")),
        })
    return pd.DataFrame(linhas, columns=COLUNAS_EXTRATO)


def ler_extrato_csv(texto: str) -> pd.DataFrame:
    """CSV com as colunas data, descricao, valor e, opcionalmente, documento e id."""
    df = pd.read_csv(io.StringIO(texto), sep=None, engine="python", dtype=str).fillna("")
    df.columns = [c.strip().lower() for c in df.columns]
    faltando = {"data", "descricao", "valor"} - set(df.columns)
    if faltando:
        raise ArquivoInvalido(f"O extrato precisa das colunas: {', '.join(sorted(faltando))}.")
    df["data"] = df["data"].map(_data)
    df["valor"] = df["valor"].map(_valor_brasileiro)
    if "documento" not in df:
        df["documento"] = ""
    if "id" not in df:
        df["id"] = [f"T{i:04d}" for i in range(1, len(df) + 1)]
    return df[COLUNAS_EXTRATO]


def ler_extrato(nome_arquivo: str, texto: str) -> pd.DataFrame:
    if nome_arquivo.lower().endswith(".ofx") or "<OFX>" in texto.upper():
        return ler_ofx(texto)
    return ler_extrato_csv(texto)


# ------------------------------------------------------------------ títulos

def ler_titulos(texto: str) -> pd.DataFrame:
    """CSV de contas a receber: titulo, cliente, cnpj, emissao, vencimento, valor."""
    df = pd.read_csv(io.StringIO(texto), sep=None, engine="python", dtype=str).fillna("")
    df.columns = [c.strip().lower() for c in df.columns]
    faltando = {"titulo", "cliente", "vencimento", "valor"} - set(df.columns)
    if faltando:
        raise ArquivoInvalido(f"O arquivo de títulos precisa das colunas: {', '.join(sorted(faltando))}.")
    df["vencimento"] = df["vencimento"].map(_data)
    df["emissao"] = df["emissao"].map(_data) if "emissao" in df else df["vencimento"]
    df["valor"] = df["valor"].map(_valor_brasileiro)
    df["cnpj"] = df["cnpj"].map(so_digitos) if "cnpj" in df else ""
    df["titulo"] = df["titulo"].str.strip()
    return df[COLUNAS_TITULOS]
