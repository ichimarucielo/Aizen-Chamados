import pandas as pd
import pytest

from validation_analysis import evaluate_validations


def test_metrics_exclude_historical_rows_without_suggestion_status():
    dataframe = pd.DataFrame([
        {
            "Classificação Sugerida": "",
            "Classificação Validada": "",
            "Score Confiança": None,
            "Regra Sugerida": "",
            "Status da Sugestão": "",
        },
        {
            "Classificação Sugerida": "Fiscal",
            "Classificação Validada": "Fiscal",
            "Score Confiança": 0.95,
            "Regra Sugerida": "regra_fiscal",
            "Status da Sugestão": "Sugerida",
        },
        {
            "Classificação Sugerida": "",
            "Classificação Validada": "",
            "Score Confiança": None,
            "Regra Sugerida": "",
            "Status da Sugestão": "Ambígua",
        },
        {
            "Classificação Sugerida": "",
            "Classificação Validada": "",
            "Score Confiança": None,
            "Regra Sugerida": "",
            "Status da Sugestão": "Sem correspondência",
        },
    ])

    metrics = evaluate_validations(dataframe)

    assert metrics["total_chamados"] == 3
    assert metrics["linhas_nao_avaliadas"] == 1
    assert metrics["sugestoes"] == 1
    assert metrics["cobertura"] == pytest.approx(1 / 3, abs=0.0001)
    assert metrics["ambiguos"] == 1
    assert metrics["concordancias"] == 1
    assert metrics["concordancia_classificacao"] == 1.0


def test_metrics_report_missing_validation_rates_as_none():
    dataframe = pd.DataFrame([
        {
            "Classificação Sugerida": "Fiscal",
            "Classificação Validada": "",
            "Score Confiança": 0.95,
            "Regra Sugerida": "regra_fiscal",
            "Status da Sugestão": "Sugerida",
        },
    ])

    metrics = evaluate_validations(dataframe)

    assert metrics["cobertura"] == 1.0
    assert metrics["validacoes"] == 0
    assert metrics["concordancia_classificacao"] is None
    assert metrics["precisao_por_classificacao"]["Fiscal"]["concordancia"] is None
    assert metrics["confianca_por_faixa"]["0.90-1.00"]["concordancia"] is None


def test_coverage_by_validated_class_includes_labeled_uncovered_calls():
    dataframe = pd.DataFrame([
        {
            "Classificação Sugerida": "Fiscal",
            "Classificação Validada": "Fiscal",
            "Score Confiança": 0.9,
            "Regra Sugerida": "regra_fiscal",
            "Status da Sugestão": "Sugerida",
        },
        {
            "Classificação Sugerida": "Financeiro",
            "Classificação Validada": "Fiscal",
            "Score Confiança": 0.8,
            "Regra Sugerida": "regra_financeiro",
            "Status da Sugestão": "Sugerida",
        },
        {
            "Classificação Sugerida": "",
            "Classificação Validada": "Título Financeiro",
            "Score Confiança": None,
            "Regra Sugerida": "",
            "Status da Sugestão": "Sem correspondência",
        },
    ])

    metrics = evaluate_validations(dataframe)

    assert metrics["cobertura_por_classificacao_validada"]["Fiscal"] == {
        "rotulados_pelo_n2": 2,
        "com_sugestao": 2,
        "cobertura": 1.0,
        "concordancias": 1,
        "concordancia_das_sugestoes": 0.5,
    }
    assert metrics["cobertura_por_classificacao_validada"]["Título Financeiro"] == {
        "rotulados_pelo_n2": 1,
        "com_sugestao": 0,
        "cobertura": 0.0,
        "concordancias": 0,
        "concordancia_das_sugestoes": None,
    }