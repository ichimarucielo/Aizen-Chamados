import pandas as pd
import pytest

from root_cause_engine import load_dictionary
from uncovered_analysis import (
    _extract_concept_groups,
    _has_suggestion_results,
    analyze_uncovered,
)


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


@pytest.mark.parametrize("reason", ["NO_PATTERN", "CONTRACT_NOT_FOUND"])
def test_uncovered_analysis_groups_current_and_legacy_unmatched_concepts(reason):
    dataframe = pd.DataFrame([
        {
            "Número do Chamado": ticket,
            "Descrição": "Descrição do problema: consultar contrato pelo banco",
            "Assunto": "Contrato",
            "Status da Sugestão": "Sem correspondência",
            "Motivo da Decisão": reason,
            "Classificação Validada": "",
        }
        for ticket in ("N2-11", "N2-12")
    ])

    report = analyze_uncovered(dataframe)

    assert report["motivos_da_decisao"] == {reason: 2}
    assert len(report["lacunas_de_contrato"]) == 1
    gap = report["lacunas_de_contrato"][0]
    assert gap["assinatura"] == "OBJETO:CONTRATO + ACAO:CONSULTAR + CANAL:BANCO"
    assert gap["quantidade"] == 2
    assert gap["numeros_chamado"] == ["N2-11", "N2-12"]
    assert gap["classes_validadas_n2"] == {}


def test_concept_groups_preserve_categories_with_the_same_concept_name():
    objects, actions, contexts = _extract_concept_groups("PO", load_dictionary())

    assert objects == ["OBJETO:PO"]
    assert actions == ["ACAO:PO"]
    assert contexts == ["CANAL:PO"]


def test_unmatched_text_without_known_concepts_has_no_contract_gap():
    dataframe = pd.DataFrame([{
        "Número do Chamado": "N2-13",
        "Descrição": "Descrição do problema: outros",
        "Assunto": "Outros",
        "Status da Sugestão": "Sem correspondência",
        "Motivo da Decisão": "NO_PATTERN",
        "Classificação Validada": "",
    }])

    report = analyze_uncovered(dataframe)

    assert report["chamados_sem_correspondencia"] == 1
    assert report["lacunas_de_contrato"] == []
