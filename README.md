# 🏦 Concilia: conciliação bancária automática

[![Testes](https://github.com/GuiRocha07/conciliacao-bancaria/actions/workflows/tests.yml/badge.svg)](https://github.com/GuiRocha07/conciliacao-bancaria/actions/workflows/tests.yml)

Aplicação web em Python que cruza o **extrato do banco** com as **contas a receber** e descobre sozinha quem pagou o quê: pagamentos exatos, pagamentos com juros ou desconto, um PIX que quita vários títulos, créditos sem dono e títulos em atraso. O resultado sai num painel e num **relatório em Excel** pronto para o financeiro.

> Projeto de portfólio inspirado em processos financeiros reais de uma distribuidora onde trabalho com automação. O código foi escrito do zero, e todos os clientes, CNPJs e valores são fictícios.

## O problema

Todo dia o financeiro abre o extrato e tenta descobrir, linha por linha, de qual cliente e de qual boleto é cada PIX ou depósito. O nome no extrato vem cortado e sem acento ("PIX RECEBIDO MERCEARIA BOM PRECO LT"), clientes pagam com juros, alguns pagam três boletos num PIX só, e sempre sobra crédito que ninguém sabe de quem é. É um trabalho manual, demorado e fácil de errar.

## Como o motor decide

Para cada crédito do extrato, o motor dá pontos a cada título em aberto, com as mesmas pistas que um analista usaria:

| Pista | Pontos |
| --- | --- |
| O número do título aparece na descrição ou no documento | +60 |
| O CNPJ do cliente aparece na descrição | +50 |
| O valor é exatamente igual | +40 |
| O nome de quem pagou parece com o do cliente (sem acentos, "LTDA", "ME"...) | até +30 |
| O valor fica perto (juros ou desconto de até 5%) | +15 |
| A data do pagamento faz sentido perto do vencimento | +10 (ou −30 se estiver longe) |

O título com mais pontos, acima de 60, vira o par do crédito. Só o valor bater **não basta**: precisa de uma pista de identidade. Depois, os créditos que sobraram passam por uma segunda etapa, que procura **combinações de títulos do mesmo cliente** cuja soma dá exatamente o valor pago.

Cada linha conciliada mostra o **porquê** ("cita o nº do título; valor exato"), para o financeiro conferir em segundos.

## O que o sistema entrega

- **Painel** com valor conciliado, % do recebido, diferenças de valor, créditos não identificados e títulos em atraso.
- **Abas** para conciliados, com diferença, não identificados e títulos em aberto (em atraso ou a vencer).
- **Relatório em Excel** com quatro abas, cabeçalhos formatados, moeda e datas no padrão brasileiro.
- **Régua de cobrança** para os títulos em aberto (detalhes abaixo).
- **Histórico** de todas as conciliações em SQLite, para consultar e baixar de novo.
- **API JSON** (`/api/execucoes/<id>`) para integrar com outros sistemas.
- Leitura de **OFX** (o formato que os bancos exportam) e de **CSV**, em UTF-8 ou Latin-1.

## Régua de cobrança

Depois da conciliação, o que sobrou em aberto vira uma lista de quem contatar e como. Cada cliente recebe **uma única mensagem** com todos os seus títulos, no tom da etapa do título mais atrasado:

| Etapa | Quando | Tom |
| --- | --- | --- |
| Lembrete | 3 dias antes do vencimento | leve |
| Vence hoje | no dia | leve |
| Cobrança amigável | 3 dias de atraso | amigável |
| Cobrança firme | 10 dias de atraso | firme |
| Último aviso | 30 dias de atraso | formal |

A tela mostra os clientes do mais atrasado para o menos atrasado, com a mensagem pronta, um botão de copiar e um link para enviar pelo WhatsApp. As etapas e os textos ficam em `conciliacao/regua.py` e são fáceis de ajustar.

## Tecnologias

Python 3 · Flask · pandas · SQLite · openpyxl · Jinja2 · JavaScript · CSS · pytest

## Como rodar

```bash
python -m venv .venv
source .venv/bin/activate      # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abra http://localhost:5000 e clique em **Usar dados de exemplo**, ou envie o seu extrato (OFX/CSV) e o seu CSV de títulos:

```
titulo;cliente;cnpj;emissao;vencimento;valor
1201;Mercearia Bom Preço Ltda;00111222000101;05/10/2026;19/10/2026;3605,96
```

Para gerar de novo os dados fictícios: `python scripts/gerar_exemplos.py`.

## Testes

```bash
pytest
```

23 testes cobrem a leitura de OFX e CSV, as regras do motor (exato, com juros, agrupado, não identificado, cliente diferente com o mesmo valor), a régua de cobrança, o relatório em Excel e o fluxo completo pela aplicação.

## Estrutura

```
app.py                      rotas da aplicação Flask
conciliacao/leitura.py      leitura de OFX, CSV de extrato e CSV de títulos
conciliacao/motor.py        motor de conciliação (pontuação e agrupamento)
conciliacao/regua.py        régua de cobrança
conciliacao/relatorio.py    relatório em Excel
conciliacao/historico.py    histórico em SQLite
scripts/gerar_exemplos.py   gera os dados fictícios
templates/ e static/        telas
tests/                      testes automatizados
```

## Próximos passos

- Buscar o extrato direto pela API do banco, em vez de importar o arquivo.
- Tela para o financeiro confirmar ou corrigir um par sugerido, e o motor aprender com isso.
- Disparar as mensagens da régua automaticamente pela API do WhatsApp.

## Autor

Feito por **Gui Rocha**: [LinkedIn](https://www.linkedin.com/in/guilherme-rochaaa) · [GitHub](https://github.com/GuiRocha07)
