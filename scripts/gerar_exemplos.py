"""Gera os arquivos de exemplo (dados 100% fictícios) usados na demonstração.

    python scripts/gerar_exemplos.py

Cria data/titulos_exemplo.csv (contas a receber) e data/extrato_exemplo.ofx (extrato do banco)
com situações reais de conciliação: pagamentos exatos, com juros, de vários títulos de uma vez,
créditos sem identificação, tarifas e títulos que ninguém pagou.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

PASTA = Path(__file__).resolve().parents[1] / "data"
HOJE = date(2026, 11, 19)
sorteio = random.Random(42)

CLIENTES = [
    ("Mercearia Bom Preço Ltda", "00111222000101"),
    ("Empório Vila Verde ME", "00111222000202"),
    ("Padaria Pão Dourado Ltda", "00111222000303"),
    ("Supermercado Ponto Certo SA", "00111222000404"),
    ("Armazém do Bairro Comércio de Alimentos", "00111222000505"),
    ("Café Recanto Mineiro EPP", "00111222000606"),
    ("Mercado Estrela do Sul Ltda", "00111222000707"),
    ("Empório Sabor da Terra", "00111222000808"),
    ("Quitanda da Praça ME", "00111222000909"),
    ("Atacarejo Litoral Ltda", "00111222001010"),
    ("Doceria Açúcar Mascavo", "00111222001111"),
    ("Hortifruti Sol Nascente", "00111222001212"),
]


def gerar_titulos() -> list[dict]:
    titulos, numero = [], 1200
    for cliente, cnpj in CLIENTES:
        for _ in range(sorteio.randint(2, 4)):
            numero += 1
            emissao = HOJE - timedelta(days=sorteio.randint(10, 55))
            vencimento = emissao + timedelta(days=sorteio.choice([14, 21, 28]))
            valor = round(sorteio.uniform(180, 4800), 2)
            titulos.append({"titulo": str(numero), "cliente": cliente, "cnpj": cnpj,
                            "emissao": emissao, "vencimento": vencimento, "valor": valor})
    return titulos


def nome_curto(cliente: str) -> str:
    """Como o nome costuma aparecer no extrato: maiúsculo, cortado e sem acento."""
    trocas = str.maketrans("ÁÂÃÇÉÊÍÓÔÕÚ", "AAACEEIOOOU")
    return cliente.upper().translate(trocas)[:26]


def gerar_extrato(titulos: list[dict]) -> list[dict]:
    transacoes = []
    cliente_agrupado = CLIENTES[3][0]  # este cliente paga vários títulos num PIX só
    pagos = [t for t in titulos if t["vencimento"] <= HOJE + timedelta(days=5) and t["cliente"] != cliente_agrupado]
    sorteio.shuffle(pagos)

    def credito(data, descricao, valor, documento=""):
        transacoes.append({"data": min(data, HOJE), "descricao": descricao, "valor": round(valor, 2),
                           "documento": documento})

    usados = set()
    # PIX com o nome do cliente e valor exato
    for t in pagos[:14]:
        credito(t["vencimento"] + timedelta(days=sorteio.randint(-3, 2)), f"PIX RECEBIDO {nome_curto(t['cliente'])}", t["valor"])
        usados.add(t["titulo"])
    # Boletos: a descrição cita o número do título
    for t in pagos[14:19]:
        credito(t["vencimento"], f"LIQUIDACAO BOLETO {t['titulo']}", t["valor"], documento=t["titulo"])
        usados.add(t["titulo"])
    # Pagos com atraso e juros (2%), citando o título
    for t in pagos[19:21]:
        credito(t["vencimento"] + timedelta(days=sorteio.randint(4, 9)), f"LIQUIDACAO BOLETO {t['titulo']} C/ JUROS",
                t["valor"] * 1.02, documento=t["titulo"])
        usados.add(t["titulo"])
    # Um cliente paga três títulos num PIX só
    do_cliente = [t for t in titulos if t["cliente"] == cliente_agrupado][:3]
    credito(max(t["vencimento"] for t in do_cliente), f"PIX RECEBIDO {nome_curto(cliente_agrupado)}",
            sum(t["valor"] for t in do_cliente))
    usados.update(t["titulo"] for t in do_cliente)
    # Créditos que ninguém sabe de quem são
    credito(HOJE - timedelta(days=6), "TED RECEBIDA 00999888000177", 1250.00)
    credito(HOJE - timedelta(days=3), "PIX RECEBIDO MARIA S", 389.90)
    credito(HOJE - timedelta(days=1), "DEPOSITO EM DINHEIRO", 600.00)
    # Saídas: tarifas e fornecedores (não entram na conciliação de recebimentos)
    for dias, descricao, valor in [(20, "TARIFA PACOTE SERVICOS", -89.90), (15, "PAGTO FORNECEDOR EMBALAGENS SUL", -3420.00),
                                   (8, "TARIFA PIX", -12.50), (2, "PAGTO ENERGIA ELETRICA", -1180.33)]:
        transacoes.append({"data": HOJE - timedelta(days=dias), "descricao": descricao, "valor": valor, "documento": ""})

    transacoes.sort(key=lambda t: t["data"])
    for i, t in enumerate(transacoes, start=1):
        t["id"] = f"2026{i:06d}"
    return transacoes


def escrever_csv(titulos: list[dict]) -> None:
    linhas = ["titulo;cliente;cnpj;emissao;vencimento;valor"]
    for t in titulos:
        valor = f"{t['valor']:.2f}".replace(".", ",")
        linhas.append(f"{t['titulo']};{t['cliente']};{t['cnpj']};{t['emissao']:%d/%m/%Y};{t['vencimento']:%d/%m/%Y};{valor}")
    (PASTA / "titulos_exemplo.csv").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def escrever_ofx(transacoes: list[dict]) -> None:
    blocos = []
    for t in transacoes:
        tipo = "CREDIT" if t["valor"] > 0 else "DEBIT"
        blocos.append(
            "<STMTTRN>\n"
            f"<TRNTYPE>{tipo}\n<DTPOSTED>{t['data']:%Y%m%d}120000\n<TRNAMT>{t['valor']:.2f}\n"
            f"<FITID>{t['id']}\n<CHECKNUM>{t['documento']}\n<MEMO>{t['descricao']}\n"
            "</STMTTRN>"
        )
    conteudo = (
        "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nENCODING:UTF-8\n\n"
        "<OFX>\n<BANKMSGSRSV1>\n<STMTTRNRS>\n<STMTRS>\n<CURDEF>BRL\n"
        "<BANKACCTFROM>\n<BANKID>000\n<ACCTID>00000-0\n</BANKACCTFROM>\n<BANKTRANLIST>\n"
        + "\n".join(blocos)
        + "\n</BANKTRANLIST>\n</STMTRS>\n</STMTTRNRS>\n</BANKMSGSRSV1>\n</OFX>\n"
    )
    (PASTA / "extrato_exemplo.ofx").write_text(conteudo, encoding="utf-8")


if __name__ == "__main__":
    PASTA.mkdir(exist_ok=True)
    titulos = gerar_titulos()
    transacoes = gerar_extrato(titulos)
    escrever_csv(titulos)
    escrever_ofx(transacoes)
    print(f"{len(titulos)} títulos e {len(transacoes)} lançamentos gerados em {PASTA}")
