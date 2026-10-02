import pandas as pd

from uncovered_analysis import analyze_uncovered, _has_suggestion_results


def test_uncovered_analysis_clusters_shared_patterns_without_suggestion():
    dataframe = pd.DataFrame([
        {
            "Número do Chamado": "N2-1",
            "Descrição": "Descrição do problema: segunda via de boleto em atraso",
            "Assunto": "Boleto",
            "Status da Sugestão": "Sem correspondência",
            "Classificação Validada": "Título Financeiro",
        },
        {
            "Número do Chamado": "N2-2",
            "Descrição": "Descrição do problema: segunda via de boleto vencido",
            "Assunto": "Boleto vencido",
            "Status da Sugestão": "Sem correspondência",
            "Classificação Validada": "Título Financeiro",
        },
        {
            "Número do Chamado": "N2-3",
            "Descrição": "Descrição do problema: assunto sem padrão conhecido",
            "Assunto": "Outro assunto",
            "Status da Sugestão": "Sem correspondência",
            "Classificação Validada": None,
        },
        {
            "Número do Chamado": "N2-4",
            "Descrição": "Descrição do problema: solicitação já classificada",
            "Assunto": "Classificado",
            "Status da Sugestão": "Sugerida",
            "Classificação Validada": "Informação/Atendimento",
        },
    ])

    report = analyze_uncovered(dataframe, min_cluster_size=2)

    assert report["chamados_sem_correspondencia"] == 3
    assert report["chamados_ambiguos"] == 0
    assert "N2-4" not in [
        ticket
        for cluster in report["clusters"]
        for ticket in cluster["numeros_chamado"]
    ]
    assert any(
        cluster["padrao"] == "segunda via boleto"
        and cluster["chamados"] == 2
        and cluster["classes_validadas_n2"] == {"Título Financeiro": 2}
        for cluster in report["clusters"]
    )


def test_uncovered_analysis_reports_short_and_missing_problem_text():
    dataframe = pd.DataFrame([
        {
            "Número do Chamado": "N2-5",
            "Descrição": "Descrição do problema: não",
            "Assunto": "Um assunto",
            "Status da Sugestão": "Sem correspondência",
            "Classificação Validada": "",
        },
        {
            "Número do Chamado": "N2-6",
            "Descrição": "Descrição sem campo de problema",
            "Assunto": "Outro assunto",
            "Status da Sugestão": "Sem correspondência",
            "Classificação Validada": "",
        },
    ])

    report = analyze_uncovered(dataframe)

    assert report["diagnosticos_de_texto"]["descricao_do_problema_curta"] == 1
    assert report["diagnosticos_de_texto"]["descricao_do_problema_ausente"] == 1


def test_uncovered_analysis_does_not_report_nan_as_validated_class():
    dataframe = pd.DataFrame([
        {
            "Número do Chamado": "N2-7",
            "Descrição": "Descrição do problema: boleto vencido para pagamento",
            "Assunto": "Boleto",
            "Status da Sugestão": "Sem correspondência",
            "Classificação Validada": None,
        },
        {
            "Número do Chamado": "N2-8",
            "Descrição": "Descrição do problema: boleto pago em atraso",
            "Assunto": "Boleto em atraso",
            "Status da Sugestão": "Sem correspondência",
            "Classificação Validada": float("nan"),
        },
    ])

    report = analyze_uncovered(dataframe)

    assert report["clusters"]
    assert all(
        "nan" not in cluster["classes_validadas_n2"]
        for cluster in report["clusters"]
    )


def test_empty_legacy_workbook_is_not_used_as_analysis_source():
    dataframe = pd.DataFrame({
        "Número do Chamado": ["N2-9"],
        "Descrição": ["descrição"],
        "Assunto": ["assunto"],
        "Status da Sugestão": [None],
        "Classificação Validada": [""],
    })

    assert not _has_suggestion_results(dataframe)


def test_workbook_with_suggestion_status_is_usable_as_analysis_source():
    dataframe = pd.DataFrame({
        "Número do Chamado": ["N2-10"],
        "Descrição": ["descrição"],
        "Assunto": ["assunto"],
        "Status da Sugestão": ["Sugerida"],
        "Classificação Validada": [""],
    })

    assert _has_suggestion_results(dataframe)