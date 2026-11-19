"""Régua de cobrança: decide quando e como lembrar cada cliente dos títulos em aberto.

Cada etapa da régua vale a partir de um número de dias em relação ao vencimento
(negativo = antes de vencer). O cliente recebe UMA mensagem com todos os seus
títulos, no tom da etapa do título mais atrasado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from urllib.parse import quote

import pandas as pd


@dataclass(frozen=True)
class Etapa:
    nome: str
    a_partir_de_dias: int
    tom: str
    modelo: str


ETAPAS = [
    Etapa("Lembrete", -3, "leve",
          "Olá, {cliente}! Passando para lembrar que {titulos_texto} vence(m) em breve. "
          "Total: {total}. Se já pagou, desconsidere. Obrigado!"),
    Etapa("Vence hoje", 0, "leve",
          "Olá, {cliente}! Hoje é o vencimento de {titulos_texto}. Total: {total}. "
          "Qualquer dúvida sobre o boleto, é só responder esta mensagem."),
    Etapa("Cobrança amigável", 3, "amigável",
          "Olá, {cliente}! Não identificamos o pagamento de {titulos_texto}, vencido(s) há {dias} dia(s). "
          "Total: {total}. Pode nos enviar o comprovante ou combinar uma nova data?"),
    Etapa("Cobrança firme", 10, "firme",
          "{cliente}, {titulos_texto} está(ão) em aberto há {dias} dias, total de {total}. "
          "Precisamos regularizar para manter seu cadastro ativo. Podemos negociar hoje?"),
    Etapa("Último aviso", 30, "formal",
          "{cliente}, este é o último aviso antes de encaminharmos {titulos_texto} ({total}, "
          "{dias} dias de atraso) para o setor jurídico. Entre em contato para negociar."),
]


def moeda(valor: float) -> str:
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def etapa_para(dias: int, etapas: list[Etapa] = ETAPAS) -> Etapa | None:
    """A etapa mais avançada cujo prazo já chegou. None = ainda é cedo para cobrar."""
    validas = [e for e in etapas if dias >= e.a_partir_de_dias]
    return max(validas, key=lambda e: e.a_partir_de_dias) if validas else None


def montar_regua(em_aberto: pd.DataFrame, hoje: date, etapas: list[Etapa] = ETAPAS) -> list[dict]:
    """Uma ação por cliente, ordenada da mais urgente para a menos urgente."""
    if em_aberto.empty:
        return []
    acoes = []
    for cliente, grupo in em_aberto.groupby("cliente"):
        dias_por_titulo = [(hoje - v).days for v in grupo["vencimento"]]
        dias = max(dias_por_titulo)  # o título mais atrasado define o tom
        etapa = etapa_para(dias, etapas)
        if etapa is None:
            continue
        titulos = list(grupo["titulo"])
        titulos_texto = f"o título {titulos[0]}" if len(titulos) == 1 else "os títulos " + ", ".join(titulos)
        total = float(grupo["valor"].sum())
        mensagem = etapa.modelo.format(
            cliente=cliente, titulos_texto=titulos_texto, total=moeda(total), dias=max(dias, 0)
        )
        acoes.append({
            "cliente": cliente,
            "etapa": etapa.nome,
            "tom": etapa.tom,
            "dias": dias,
            "titulos": ", ".join(titulos),
            "total": round(total, 2),
            "mensagem": mensagem,
            "link_whatsapp": f"https://wa.me/?text={quote(mensagem)}",
        })
    return sorted(acoes, key=lambda a: (-a["dias"], -a["total"]))
