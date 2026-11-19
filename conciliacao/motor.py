"""Motor de conciliação: cruza os créditos do extrato com os títulos a receber.

Para cada crédito do extrato, o motor dá uma pontuação a cada título em aberto,
usando as pistas que um analista financeiro usaria:

- o número do título aparece na descrição do PIX/boleto;
- o CNPJ do cliente aparece na descrição;
- o nome de quem pagou parece com o nome do cliente;
- o valor bate (ou fica perto, por causa de juros ou desconto);
- a data do pagamento faz sentido perto do vencimento.

O título com maior pontuação, acima de um mínimo, é o par do crédito.
Depois o motor tenta casar pagamentos que quitam vários títulos de uma vez.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
from itertools import combinations

import pandas as pd

from .leitura import so_digitos

PALAVRAS_IGNORADAS = {
    "LTDA", "ME", "EPP", "EIRELI", "SA", "S/A", "COMERCIO", "COM", "DE", "DA", "DO", "DOS", "DAS", "E",
    "PIX", "RECEBIDO", "TED", "DOC", "CRED", "CREDITO", "BOLETO", "LIQUIDACAO", "TRANSF", "TRANSFERENCIA",
}


@dataclass
class Regras:
    pontuacao_minima: int = 60
    tolerancia_percentual: float = 0.05  # juros ou desconto de até 5% contam como "valor parecido"
    dias_antes_vencimento: int = 45
    dias_depois_vencimento: int = 60
    max_titulos_agrupados: int = 4


@dataclass
class Resultado:
    conciliados: pd.DataFrame
    nao_identificados: pd.DataFrame
    em_aberto: pd.DataFrame
    saidas: pd.DataFrame
    resumo: dict = field(default_factory=dict)


# ------------------------------------------------------------------ texto

def normalizar(texto: object) -> str:
    texto = unicodedata.normalize("NFD", str(texto or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn").upper()
    return re.sub(r"[^A-Z0-9 ]", " ", texto)


def palavras_relevantes(texto: object) -> set[str]:
    return {p for p in normalizar(texto).split() if p not in PALAVRAS_IGNORADAS and not p.isdigit() and len(p) > 1}


def semelhanca_nome(descricao: str, cliente: str) -> float:
    """0 a 1: quanto o nome na descrição do extrato parece com o nome do cliente."""
    a, b = palavras_relevantes(descricao), palavras_relevantes(cliente)
    if not a or not b:
        return 0.0
    em_comum = len(a & b) / len(b)
    sequencia = SequenceMatcher(None, " ".join(sorted(a)), " ".join(sorted(b))).ratio()
    return round(max(em_comum, sequencia), 2)


def cita_titulo(descricao: str, documento: str, titulo: str) -> bool:
    """O número do título aparece como palavra inteira na descrição ou no documento."""
    alvo = so_digitos(titulo)
    if not alvo:
        return False
    numeros = re.findall(r"\d+", f"{descricao} {documento}")
    return any(n.lstrip("0") == alvo.lstrip("0") for n in numeros)


# ------------------------------------------------------------------ pontuação

def pontuar(credito: pd.Series, titulo: pd.Series, regras: Regras) -> tuple[int, list[str]]:
    """Pontua o quanto um crédito parece ser o pagamento de um título. Devolve (pontos, motivos)."""
    pontos, motivos = 0, []
    descricao, documento = str(credito["descricao"]), str(credito["documento"])

    if cita_titulo(descricao, documento, titulo["titulo"]):
        pontos += 60
        motivos.append("cita o nº do título")
    cnpj = str(titulo["cnpj"])
    if cnpj and cnpj in so_digitos(f"{descricao} {documento}"):
        pontos += 50
        motivos.append("CNPJ na descrição")

    nome = semelhanca_nome(descricao, titulo["cliente"])
    if nome >= 0.6:
        pontos += int(30 * nome)
        motivos.append(f"nome {int(nome * 100)}% parecido")

    diferenca = abs(credito["valor"] - titulo["valor"])
    if diferenca < 0.01:
        pontos += 40
        motivos.append("valor exato")
    elif diferenca <= titulo["valor"] * regras.tolerancia_percentual:
        pontos += 15
        motivos.append("valor próximo")

    dias = (credito["data"] - titulo["vencimento"]).days
    if -regras.dias_antes_vencimento <= dias <= regras.dias_depois_vencimento:
        pontos += 10
    else:
        pontos -= 30
        motivos.append("data longe do vencimento")
    return pontos, motivos


def _linha(credito: pd.Series, titulos: list[pd.Series], status: str, motivos: list[str], pontos: int) -> dict:
    total_titulos = round(sum(t["valor"] for t in titulos), 2)
    return {
        "status": status,
        "confianca": "alta" if pontos >= 100 else "média",
        "data_pagamento": credito["data"],
        "descricao": credito["descricao"],
        "valor_pago": credito["valor"],
        "titulos": ", ".join(t["titulo"] for t in titulos),
        "cliente": titulos[0]["cliente"],
        "vencimento": min(t["vencimento"] for t in titulos),
        "valor_titulos": total_titulos,
        "diferenca": round(credito["valor"] - total_titulos, 2),
        "dias_atraso": max(0, (credito["data"] - min(t["vencimento"] for t in titulos)).days),
        "motivos": "; ".join(motivos),
        "id_extrato": credito["id"],
    }


# ------------------------------------------------------------------ conciliação

def conciliar(extrato: pd.DataFrame, titulos: pd.DataFrame, hoje: date, regras: Regras | None = None) -> Resultado:
    regras = regras or Regras()
    creditos = extrato[extrato["valor"] > 0].copy()
    saidas = extrato[extrato["valor"] <= 0].copy()

    abertos = {i: t for i, t in titulos.iterrows()}
    conciliados: list[dict] = []
    sem_par: list[pd.Series] = []

    # 1ª passada: um crédito para um título
    for _, credito in creditos.sort_values("data").iterrows():
        melhor, melhor_pontos, melhor_motivos = None, -999, []
        for i, titulo in abertos.items():
            pontos, motivos = pontuar(credito, titulo, regras)
            if pontos > melhor_pontos:
                melhor, melhor_pontos, melhor_motivos = i, pontos, motivos
        if melhor is not None and melhor_pontos >= regras.pontuacao_minima:
            titulo = abertos.pop(melhor)
            exato = abs(credito["valor"] - titulo["valor"]) < 0.01
            status = "conciliado" if exato else "divergente"
            conciliados.append(_linha(credito, [titulo], status, melhor_motivos, melhor_pontos))
        else:
            sem_par.append(credito)

    # 2ª passada: um crédito que quita vários títulos do mesmo cliente
    nao_identificados = []
    for credito in sem_par:
        achou = _procurar_agrupado(credito, abertos, regras)
        if achou:
            indices, motivos = achou
            grupo = [abertos.pop(i) for i in indices]
            conciliados.append(_linha(credito, grupo, "agrupado", motivos, 100))
        else:
            nao_identificados.append(credito)

    em_aberto = pd.DataFrame(list(abertos.values()), columns=titulos.columns)
    if not em_aberto.empty:
        em_aberto["situacao"] = em_aberto["vencimento"].map(lambda v: "em atraso" if v < hoje else "a vencer")
        em_aberto["dias_atraso"] = em_aberto["vencimento"].map(lambda v: max(0, (hoje - v).days))
        em_aberto = em_aberto.sort_values(["dias_atraso", "valor"], ascending=False)
    else:
        em_aberto = em_aberto.assign(situacao=[], dias_atraso=[])

    df_conciliados = pd.DataFrame(conciliados)
    df_nao = pd.DataFrame(nao_identificados, columns=extrato.columns)
    return Resultado(
        conciliados=df_conciliados,
        nao_identificados=df_nao,
        em_aberto=em_aberto,
        saidas=saidas,
        resumo=_resumo(df_conciliados, df_nao, em_aberto, creditos),
    )


def _procurar_agrupado(credito: pd.Series, abertos: dict, regras: Regras):
    """Procura de 2 a N títulos do mesmo cliente cuja soma dá exatamente o valor pago."""
    candidatos = [
        i for i, t in abertos.items()
        if semelhanca_nome(credito["descricao"], t["cliente"]) >= 0.6
        or (t["cnpj"] and t["cnpj"] in so_digitos(f"{credito['descricao']} {credito['documento']}"))
    ]
    for tamanho in range(2, min(regras.max_titulos_agrupados, len(candidatos)) + 1):
        for combo in combinations(candidatos, tamanho):
            clientes = {abertos[i]["cliente"] for i in combo}
            soma = sum(abertos[i]["valor"] for i in combo)
            if len(clientes) == 1 and abs(soma - credito["valor"]) < 0.01:
                return list(combo), [f"um pagamento para {tamanho} títulos do mesmo cliente"]
    return None


def _resumo(conciliados: pd.DataFrame, nao: pd.DataFrame, em_aberto: pd.DataFrame, creditos: pd.DataFrame) -> dict:
    def soma(df: pd.DataFrame, coluna: str) -> float:
        return round(float(df[coluna].sum()), 2) if not df.empty else 0.0

    def contar(status: str) -> int:
        return int((conciliados["status"] == status).sum()) if not conciliados.empty else 0

    atrasados = em_aberto[em_aberto["situacao"] == "em atraso"] if not em_aberto.empty else em_aberto
    total_creditos = soma(creditos, "valor")
    valor_conciliado = soma(conciliados, "valor_pago")
    return {
        "creditos": len(creditos),
        "total_creditos": total_creditos,
        "conciliados": contar("conciliado"),
        "agrupados": contar("agrupado"),
        "divergentes": contar("divergente"),
        "nao_identificados": len(nao),
        "valor_nao_identificado": soma(nao, "valor"),
        "valor_conciliado": valor_conciliado,
        "percentual_conciliado": round(100 * valor_conciliado / total_creditos, 1) if total_creditos else 0.0,
        "titulos_em_atraso": len(atrasados),
        "valor_em_atraso": soma(atrasados, "valor"),
        "titulos_a_vencer": len(em_aberto) - len(atrasados),
    }
