"""Concilia: conciliação bancária automática.

Rodar:  python app.py   e abrir http://localhost:5000
"""

from __future__ import annotations

import io
import os
from datetime import date
from pathlib import Path

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, send_file, url_for

from conciliacao import historico
from conciliacao.leitura import ArquivoInvalido, ler_extrato, ler_titulos
from conciliacao.motor import conciliar
from conciliacao.relatorio import ROTULO_RESUMO, gerar_excel

PASTA = Path(__file__).parent
EXEMPLO_EXTRATO = PASTA / "data" / "extrato_exemplo.ofx"
EXEMPLO_TITULOS = PASTA / "data" / "titulos_exemplo.csv"
DATA_DOS_EXEMPLOS = date(2026, 11, 19)  # os dados fictícios foram gerados para esta data


def criar_app(caminho_banco: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "troque-esta-chave")
    app.config["BANCO"] = caminho_banco or os.environ.get("BANCO", str(PASTA / "concilia.db"))
    app.jinja_env.filters["moeda"] = moeda
    app.jinja_env.filters["data_br"] = data_br

    def con():
        if "con" not in g:
            g.con = historico.conectar(app.config["BANCO"])
        return g.con

    @app.teardown_appcontext
    def fechar(_erro):
        conexao = g.pop("con", None)
        if conexao is not None:
            conexao.close()

    @app.get("/")
    def inicio():
        return render_template("inicio.html", hoje=date.today().isoformat())

    @app.post("/conciliar")
    def executar():
        usar_exemplos = request.form.get("exemplos") == "1"
        try:
            if usar_exemplos:
                nome_extrato, texto_extrato = EXEMPLO_EXTRATO.name, EXEMPLO_EXTRATO.read_text(encoding="utf-8")
                nome_titulos, texto_titulos = EXEMPLO_TITULOS.name, EXEMPLO_TITULOS.read_text(encoding="utf-8")
                hoje = DATA_DOS_EXEMPLOS
            else:
                arq_extrato, arq_titulos = request.files.get("extrato"), request.files.get("titulos")
                if not (arq_extrato and arq_extrato.filename and arq_titulos and arq_titulos.filename):
                    flash("Envie o extrato e o arquivo de títulos, ou use os dados de exemplo.")
                    return redirect(url_for("inicio"))
                nome_extrato, texto_extrato = arq_extrato.filename, ler_texto(arq_extrato.read())
                nome_titulos, texto_titulos = arq_titulos.filename, ler_texto(arq_titulos.read())
                hoje = date.fromisoformat(request.form.get("data_referencia") or date.today().isoformat())

            extrato = ler_extrato(nome_extrato, texto_extrato)
            titulos = ler_titulos(texto_titulos)
        except (ArquivoInvalido, ValueError) as erro:
            flash(f"Não consegui ler os arquivos: {erro}")
            return redirect(url_for("inicio"))

        resultado = conciliar(extrato, titulos, hoje)
        execucao_id = historico.salvar(con(), resultado, nome_extrato, nome_titulos)
        return redirect(url_for("ver_execucao", execucao_id=execucao_id))

    @app.get("/execucoes/<int:execucao_id>")
    def ver_execucao(execucao_id: int):
        achado = historico.carregar(con(), execucao_id)
        if achado is None:
            abort(404)
        execucao, resultado = achado
        conciliados = resultado.conciliados
        return render_template(
            "resultado.html",
            execucao=execucao,
            r=resultado.resumo,
            exatos=registros(conciliados, conciliados["status"].isin(["conciliado", "agrupado"])) if not conciliados.empty else [],
            divergentes=registros(conciliados, conciliados["status"] == "divergente") if not conciliados.empty else [],
            nao_identificados=resultado.nao_identificados.to_dict("records"),
            em_aberto=resultado.em_aberto.to_dict("records"),
        )

    @app.get("/execucoes/<int:execucao_id>/excel")
    def baixar_excel(execucao_id: int):
        achado = historico.carregar(con(), execucao_id)
        if achado is None:
            abort(404)
        return send_file(
            io.BytesIO(gerar_excel(achado[1])),
            as_attachment=True,
            download_name=f"conciliacao_{execucao_id}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.get("/historico")
    def ver_historico():
        return render_template("historico.html", execucoes=historico.listar(con()))

    @app.get("/api/execucoes/<int:execucao_id>")
    def api_execucao(execucao_id: int):
        achado = historico.carregar(con(), execucao_id)
        if achado is None:
            abort(404)
        resultado = achado[1]
        return jsonify(
            resumo=resultado.resumo,
            conciliados=resultado.conciliados.astype(str).to_dict("records"),
            nao_identificados=resultado.nao_identificados.astype(str).to_dict("records"),
            em_aberto=resultado.em_aberto.astype(str).to_dict("records"),
        )

    @app.context_processor
    def rotulos():
        return {"ROTULO_RESUMO": ROTULO_RESUMO}

    return app


def registros(df, filtro) -> list[dict]:
    return df[filtro].to_dict("records")


def ler_texto(conteudo: bytes) -> str:
    """Bancos ainda exportam em Latin-1; tenta UTF-8 primeiro."""
    try:
        return conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return conteudo.decode("latin-1")


def moeda(valor) -> str:
    texto = f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def data_br(valor) -> str:
    return valor.strftime("%d/%m/%Y") if hasattr(valor, "strftime") else str(valor or "")


app = criar_app()

if __name__ == "__main__":
    app.run(debug=True)
