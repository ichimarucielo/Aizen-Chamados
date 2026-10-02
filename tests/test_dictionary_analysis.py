import pandas as pd

from dictionary_analysis import analyze_dictionary
from root_cause_engine import load_dictionary


def test_analysis_reports_missing_values_and_literal_class_conflicts():
    history = pd.DataFrame([
        {
            "Número do Chamado": "N2-1",
            "Classificação": "Cancelamento e Reemissão de Nota Fiscal",
            "Causa raiz": "Cancelamento de NF",
            "Descrição detalhada": "cancelar a NF",
            "Descrição": "cancelar a NF",
            "Assunto": "Cancelamento",
        },
        {
            "Número do Chamado": "N2-2",
            "Classificação": "Cobrança e Contestação",
            "Causa raiz": "Cancelamento de NF",
            "Descrição detalhada": "cancelamento de NF por cobrança divergente",
            "Descrição": "cancelamento de NF por cobrança divergente",
            "Assunto": "Cobrança",
        },
        {
            "Número do Chamado": "N2-3",
            "Classificação": "",
            "Causa raiz": "#N/A",
            "Descrição detalhada": "",
            "Descrição": "",
            "Assunto": "Sem classificação",
        },
        {
            "Número do Chamado": "N2-4",
            "Classificação": "Atendimento Administrativo e Suporte",
            "Causa raiz": "",
            "Descrição detalhada": "Informação geral",
            "Descrição": "Informação geral",
            "Assunto": "Atendimento",
        },
    ])
    references = pd.DataFrame({"Tema": ["tema-a", "tema-a", ""]})

    report = analyze_dictionary(history, references, load_dictionary())
    summary = report["resumo_historico"]

    assert summary["chamados_analisados"] == 4
    assert summary["causas_historicas_unicas_nao_vazias"] == 1
    assert summary["temas_unicos_na_aba_referencias"] == 1
    assert summary["causa_vazia"] == 1
    assert summary["classificacao_vazia"] == 1
    assert summary["rotulos_literal_na"] == 1
    assert summary["descricao_detalhada_vazia"] == 1
    assert report["conflitos_causa_literal_em_multiplas_classes"]["Cancelamento de NF"] == [
        "Cancelamento e Reemissão de Nota Fiscal",
        "Cobrança e Contestação",
    ]
    na_row = next(
        item
        for item in report["causa_historica_para_padrao"]
        if item["causa_historica"] == "#N/A"
    )
    assert na_row["status_consolidacao"] == "rotulo_na"
