import pandas as pd

from main import build_n2_dataframe


def test_build_n2_dataframe_classifies_full_description_to_canonical_cause():
    description = (
        "Olá,\n"
        "Para este faturamento de junho notificamos a necessidade da aplicação "
        "de um desconto referente ao retroativo do mês de abril R$37,55\n\n"
        "Chamado de Abril:\nAntigo: 216094\nAtual: 2512611299293\n"
        "Faturamento Braspag | Abril 2024 | 1018 | ticket.id\n\n"
        "Por favor seguir com cancelamento da NF"
    )
    monitoramento = pd.DataFrame([{
        "Descrição": description,
        "Número do Chamado": "251261",
        "Número de Chamado Pai": "",
        "Número Protocolo": "",
        "Status": "Novo",
        "Assunto": "Faturamento",
        "Data de abertura": "2026-10-01",
        "Data da última modificação do chamado": "2026-10-01",
        "Proprietário do Chamado": "",
        "Email da Web": "",
        "Nome Fantasia": "",
    }])
    references = pd.DataFrame([{
        "CNPJ": "",
        "Cliente": "",
        "Tema": "",
        "Macro Classificação": "",
    }])
    history = pd.DataFrame([{
        "Causa raiz": "Cancelamento de NF",
        "Classificação": "Cancelamento e Reemissão de Nota Fiscal",
        "Descrição detalhada": "cancelamento de nf",
    }])

    result = build_n2_dataframe(
        monitoramento,
        references,
        history,
    ).iloc[0]

    assert result["Causa Identificada"] == "cancelamento da nf"
    assert result["Intenção Identificada"] == "Cancelar, substituir ou reemitir nota fiscal."
    assert result["Causa Raiz Padrão"] == "Cancelamento/Reemissão de Nota Fiscal"
    assert result["Causa raiz"] == "Cancelamento/Reemissão de Nota Fiscal"
    assert result["Classificação"] == "Cancelamento e Reemissão de Nota Fiscal"