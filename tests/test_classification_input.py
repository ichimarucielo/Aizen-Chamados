import pandas as pd
import pytest

from backfill_suggestions import build_backfill_dataframe
from classification_input import build_classification_input, prepare_descriptions
from dictionary_analysis import analyze_dictionary
from main import build_n2_dataframe
from root_cause_engine import evaluate


@pytest.mark.parametrize("record, expected", [
    ({"Descrição": "Assunto: Cancelamento da NF\nDescrição do problema: Favor proceder"}, "Cancelamento da NF. Favor proceder"),
    ({"Descrição": None, "Descrição detalhada": "cancelar contrato", "Assunto": "Financeiro"}, "cancelar contrato"),
    ({"Assunto": "Reenvio de boleto"}, "Reenvio de boleto"),
    ({}, ""),
])
def test_input_uses_internal_subject_then_problem_and_legacy_fallbacks(record, expected):
    frame = pd.DataFrame([record], index=[17])
    result = build_classification_input(frame)
    assert result.index.tolist() == [17]
    assert result.iloc[0] == expected


def test_empty_input_preserves_empty_index():
    result = prepare_descriptions(pd.DataFrame())
    assert result.empty
    assert result.columns.tolist() == ["Descrição detalhada", "Entrada de Classificação"]


def test_processing_backfill_and_evaluations_classify_the_same_internal_subject():
    classification = "Cancelamento e Reemissão de Nota Fiscal"
    record = {
        "Número do Chamado": "N2-INPUT",
        "Descrição": "Assunto: Cancelamento da NF\nDescrição do problema: Favor proceder",
        "Descrição detalhada": "Favor proceder",
        "Assunto": "Financeiro",
        "Classificação": classification,
        "Causa raiz": "Cancelamento de NF",
        "Número de Chamado Pai": "",
        "Número Protocolo": "",
        "Status": "Novo",
        "Data de abertura": "2026-10-01",
        "Data da última modificação do chamado": "2026-10-01",
        "Proprietário do Chamado": "",
        "Email da Web": "",
        "Nome Fantasia": "",
    }
    frame = pd.DataFrame([record], index=[17])
    references = pd.DataFrame([{"CNPJ": "", "Cliente": "", "Tema": "", "Macro Classificação": ""}])
    processed = build_n2_dataframe(frame, references, frame)
    backfilled = build_backfill_dataframe(frame)

    assert processed.iloc[0]["Descrição detalhada"] == "Favor proceder"
    for name in ("ID Causa Padrão", "Causa Raiz Padrão", "Classificação Sugerida", "Motivo da Decisão"):
        assert processed.iloc[0][name] == backfilled.iloc[0][name]
    assert backfilled.iloc[0]["ID Causa Padrão"] == "CANCELAMENTO_NF"
    assert evaluate(frame)["acertos"] == 1
    audit = analyze_dictionary(frame, references)["avaliacao_deterministica_no_historico"]
    assert audit["acertos_entre_respostas"] == 1
