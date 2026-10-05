"""Regressão do lote de 157 chamados: extract_problem, normalização, G1/G4/G5/G6 e precedência."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parse_description import extract_problem  # noqa: E402
from root_cause_engine import classify, load_dictionary, normalize_text  # noqa: E402

DICTIONARY = load_dictionary()


def intent_of(raw):
    return classify(extract_problem(raw), DICTIONARY)["intencao_id"]


# ---------- extract_problem ----------

def test_extract_problem_html_uses_only_problem_description():
    raw = (
        "<p><strong>Assunto:</strong> Cobrança de setup</p>"
        "<p><strong>Descrição do problema:</strong> Preciso prorrogar o boleto</p>"
    )
    assert extract_problem(raw) == "Preciso prorrogar o boleto"


def test_extract_problem_plain_text_label():
    assert (
        extract_problem("Descrição do problema: segunda via de boleto em atraso")
        == "segunda via de boleto em atraso"
    )


def test_extract_problem_plain_text_stops_at_next_field():
    raw = "Descrição do problema: pedido de prorrogação\nAssunto: Boleto"
    assert extract_problem(raw) == "pedido de prorrogação"


@pytest.mark.parametrize("raw", ["Substituição de NF", "<p>Carta de quitação</p>"])
def test_extract_problem_without_structured_description_uses_whole_text(raw):
    assert extract_problem(raw) in {"Substituição de NF", "Carta de quitação"}


def test_extract_problem_nan_is_empty():
    assert extract_problem(float("nan")) == ""


# ---------- G1: texto sem formulário (só o conceito no Assunto) ----------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Substituição de NF", "INT_NF_CANCEL_REEMISSAO"),
        ("Substituição de nota", "INT_NF_CANCEL_REEMISSAO"),
        ("Substituição de NFS", "INT_NF_CANCEL_REEMISSAO"),
        ("Carta de quitação", "INT_ADM_DOCUMENTOS"),
        ("Cobrança de chave de loja", "INT_COB_SETUP"),
        ("Notas cobradas em duplicidade", "INT_COB_DUPLICIDADE"),
        ("Valores indevidos", "INT_COB_CONTESTACAO"),
    ],
)
def test_g1_label_only_emails_are_classified(raw, expected):
    assert intent_of(raw) == expected


# ---------- G5: data de emissão da NF ----------

@pytest.mark.parametrize(
    "text",
    [
        "Estamos recebendo NFs para lançamento com emissão no final no mês, o que impossibilita o lançamento dentro do mês de vigência.",
        "O cliente entrou em contato solicitando a alteração na data de emissão das notas fiscais.",
        "Precisamos alterar a data de emissão da NF para o mês correto.",
    ],
)
def test_g5_invoice_issue_date(text):
    assert classify(text, DICTIONARY)["intencao_id"] == "INT_NF_DATA_EMISSAO"


# ---------- G6: vencimento ----------

def test_g6_due_date_not_blocked_by_incidental_issue_date():
    text = (
        "Olá, preciso de um boleto com data de vencimento atualizada. "
        "Todos os boletos devem ter vencimento pelo menos 20 dias após a data de emissão da NF."
    )
    assert classify(text, DICTIONARY)["intencao_id"] == "INT_PAG_VENCIMENTO"


def test_g6_prorrogar_vencimento():
    text = (
        "Gostaria de verificar se é possível prorrogar o vencimento do boleto "
        "referente ao setup por mais 15 dias."
    )
    assert classify(text, DICTIONARY)["intencao_id"] == "INT_PAG_VENCIMENTO"


def test_g6_issue_date_change_still_excludes_due_date_intent():
    result = classify("Solicito alterar a data de emissão da NF para o mês seguinte.", DICTIONARY)
    assert result["intencao_id"] == "INT_NF_DATA_EMISSAO"
    assert "INT_PAG_VENCIMENTO" not in result["candidatas"]


# ---------- G4: código diferente / cancelamento + das nf ----------

def test_g4_invoice_code_different():
    text = "As notas fiscais estão sendo emitidas com um código diferente do que era realizado anteriormente."
    assert classify(text, DICTIONARY)["intencao_id"] == "INT_NF_CORRECAO_CODIGO"


def test_g4_cancellation_of_products_and_invoices():
    text = "Segue o DA para o cancelamento dos produtos e das notas."
    assert classify(text, DICTIONARY)["intencao_id"] == "INT_NF_CANCEL_REEMISSAO"


# ---------- normalização ----------

def test_email_address_becomes_email_concept():
    assert normalize_text("enviar para joao.silva@empresa.com.br") == "enviar para email"


def test_email_address_matches_email_patterns():
    text = "Favor encaminhar as faturas referentes a estes dados para contasacadastrar@lider.design"
    assert classify(text, DICTIONARY)["intencao_id"] == "INT_CON_CADASTRO"


@pytest.mark.parametrize("a, b", [
    ("Recebemos 2 notas fiscais", "Recebemos duas notas fiscais"),
    ("2 boletos", "dois boletos"),
    ("3 notas", "tres notas"),
])
def test_relevant_numerals_are_normalized(a, b):
    assert normalize_text(a) == normalize_text(b)


def test_numerals_outside_relevant_nouns_are_untouched():
    assert normalize_text("nota 2 do contrato") == "nf 2 do contrato"


def test_two_invoices_question_uses_numeral_normalization():
    text = (
        "Recebemos 2 notas fiscais emitidas em 14/08/2026 com os mesmos serviços, períodos e valores. "
        "Gostaríamos de saber se estão corretas e o porquê."
    )
    assert classify(text, DICTIONARY)["intencao_id"] == "INT_FAT_DUVIDA"


# ---------- precedência ----------

def test_contract_over_nf_cancellation_precedence_removed():
    precedence = DICTIONARY["precedencia"]
    assert not any(
        r["preferir"] == "INT_CON_CANCELAMENTO" and "INT_NF_CANCEL_REEMISSAO" in r["sobre"]
        for r in precedence
    )


def test_cancel_nf_and_cancel_contract_is_ambiguous():
    result = classify("Cancelar NF e cancelar contrato", DICTIONARY)
    assert result["ambiguo"] is True
    assert {"INT_NF_CANCEL_REEMISSAO", "INT_CON_CANCELAMENTO"} <= set(result["candidatas"])


@pytest.mark.parametrize(
    "text, expected",
    [
        ("cancelar/substituir NF com PO", "INT_NF_REEMISSAO_PO"),
        ("Erro no descritivo dos serviços; a cobrança retroativa está correta", "INT_FAT_CORRECAO_PO"),
        ("congelar o contrato; cancelamento de notas é só contexto", "INT_CON_CONGELAMENTO"),
        ("Cancelar a NF por cobrança indevida e erro no contrato", "INT_NF_CANCEL_REEMISSAO"),
        ("Cancelar a NF porque houve cobrança duplicada", "INT_NF_CANCEL_REEMISSAO"),
        ("favor cancelar e emitir uma nova NF", "INT_NF_CANCEL_REEMISSAO"),
    ],
)
def test_existing_precedence_behaviour_is_preserved(text, expected):
    assert classify(text, DICTIONARY)["intencao_id"] == expected


# ---------- fora do escopo: continua sem correspondência ----------

@pytest.mark.parametrize("raw", ["Outros", "", "financeiro"])
def test_empty_or_generic_text_stays_unclassified(raw):
    assert intent_of(raw) is None
