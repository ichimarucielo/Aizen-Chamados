import pytest

from root_cause_engine import (
    classify,
    load_dictionary,
    load_objects,
    suggest,
    validate_dictionary,
)


DICTIONARY = load_dictionary()
OBJECTS = load_objects()


CASES = [
    ("cancelamento da NF", "INT_NF_CANCEL_REEMISSAO", "Cancelamento e Reemissão de Nota Fiscal"),
    ("cancelar notas fiscais", "INT_NF_CANCEL_REEMISSAO", "Cancelamento e Reemissão de Nota Fiscal"),
    ("substituição das NFs", "INT_NF_CANCEL_REEMISSAO", "Cancelamento e Reemissão de Nota Fiscal"),
    ("reemissão de NF", "INT_NF_CANCEL_REEMISSAO", "Cancelamento e Reemissão de Nota Fiscal"),
    ("cancelar contrato", "INT_CON_CANCELAMENTO", "Contratos, Comercial e Cadastro"),
    ("prorrogar boleto", "INT_PAG_VENCIMENTO", "Pagamentos, Boletos e Recebimentos"),
    ("reenvio de boleto", "INT_PAG_BOLETO_REENVIO", "Pagamentos, Boletos e Recebimentos"),
    ("contestar cobrança", "INT_COB_CONTESTACAO", "Cobrança e Contestação"),
    ("alterar e-mail cadastrado", "INT_CON_CADASTRO", "Contratos, Comercial e Cadastro"),
    ("dúvida sobre faturamento", "INT_FAT_DUVIDA", "Faturamento e Obrigações Fiscais"),
    ("reenvio de NF", "INT_FAT_REENVIO_NF", "Faturamento e Obrigações Fiscais"),
    ("alterar data de emissão da NF", "INT_NF_DATA_EMISSAO", "Cancelamento e Reemissão de Nota Fiscal"),
    ("alterar data de vencimento do boleto", "INT_PAG_VENCIMENTO", "Pagamentos, Boletos e Recebimentos"),
    ("boleto em aberto e não recebi a NF", "INT_PAG_NF_VINCULADA", "Pagamentos, Boletos e Recebimentos"),
    ("encaminhar a nota fiscal que não recebi", "INT_FAT_REENVIO_NF", "Faturamento e Obrigações Fiscais"),
    ("carta de correção com PO", "INT_FAT_CORRECAO_PO", "Faturamento e Obrigações Fiscais"),
    ("cancelar/substituir NF com PO", "INT_NF_REEMISSAO_PO", "Cancelamento e Reemissão de Nota Fiscal"),
    ("cancelar todas notas", "INT_NF_CANCEL_REEMISSAO", "Cancelamento e Reemissão de Nota Fiscal"),
    ("cancelamento de todas as notas", "INT_NF_CANCEL_REEMISSAO", "Cancelamento e Reemissão de Nota Fiscal"),
    ("solicito cancelamento das notas", "INT_NF_CANCEL_REEMISSAO", "Cancelamento e Reemissão de Nota Fiscal"),
    ("favor cancelar notas", "INT_NF_CANCEL_REEMISSAO", "Cancelamento e Reemissão de Nota Fiscal"),
    ("Dois boletos no banco; excluir o duplicado", "INT_PAG_BOLETO_CANCELAMENTO", "Pagamentos, Boletos e Recebimentos"),
    ("Erro no descritivo dos serviços; a cobrança retroativa está correta", "INT_FAT_CORRECAO_PO", "Faturamento e Obrigações Fiscais"),
    ("dúvida sobre cobrança com valor mensal diferente", "INT_COB_CONTESTACAO", "Cobrança e Contestação"),
    ("cobrado apenas pelo mínimo apesar de 3000 transações", "INT_COB_CONTESTACAO", "Cobrança e Contestação"),
    ("enviar novo boleto", "INT_PAG_BOLETO_REENVIO", "Pagamentos, Boletos e Recebimentos"),
    ("congelar o contrato; cancelamento de notas é só contexto", "INT_CON_CONGELAMENTO", "Contratos, Comercial e Cadastro"),
    ("alteração de e-mail para receber faturas", "INT_CON_CADASTRO", "Contratos, Comercial e Cadastro"),
    ("alterar data de emissão das NFs para o mesmo mês do vencimento", "INT_PAG_VENCIMENTO", "Pagamentos, Boletos e Recebimentos"),
    ("boleto em aberto e não recebi a NF", "INT_PAG_NF_VINCULADA", "Pagamentos, Boletos e Recebimentos"),
    ("esclarecer o que foi feito com o valor pago da nota cancelada", "INT_FAT_DUVIDA", "Faturamento e Obrigações Fiscais"),
]

FOUR_HISTORICAL_CASES = [
    ("cobrado apenas pelo mínimo apesar de 3000 transações", "Contestação/Divergência de Cobrança"),
    ("enviar novo boleto", "Reenvio/Reemissão de Boleto"),
    ("congelar o contrato; cancelamento de notas é só contexto", "Congelamento de Contrato"),
    ("alterar data de emissão das NFs para o mesmo mês do vencimento", "Alteração/Prorrogação de Vencimento"),
]


@pytest.mark.parametrize("description, intent_id, classification", CASES)
def test_operational_intentions_map_to_canonical_cause_and_official_class(
    description,
    intent_id,
    classification,
):
    result = classify(description, DICTIONARY)

    assert result["intencao_id"] == intent_id
    assert result["causa_canonica"] is not None
    assert result["classificacao"] == classification
    assert result["status"] == "Sugerida"
    assert result["classificacao"] in DICTIONARY["classes_permitidas"]


@pytest.mark.parametrize("description, canonical_cause", FOUR_HISTORICAL_CASES)
def test_historical_failure_cases_use_expected_canonical_cause(
    description,
    canonical_cause,
):
    result = classify(description, DICTIONARY)

    assert result["causa_canonica"] == canonical_cause


def test_cancellation_intention_wins_over_incidental_billing_context():
    result = classify(
        "Cancelar a NF por cobrança indevida e erro no contrato",
        DICTIONARY,
    )

    assert result["intencao_id"] == "INT_NF_CANCEL_REEMISSAO"
    assert result["classificacao"] == "Cancelamento e Reemissão de Nota Fiscal"


def test_nf_cancellation_wins_over_duplicate_billing_reason():
    result = classify(
        "Cancelar a NF porque houve cobrança duplicada",
        DICTIONARY,
    )

    assert result["intencao_id"] == "INT_NF_CANCEL_REEMISSAO"
    assert result["classificacao"] == "Cancelamento e Reemissão de Nota Fiscal"


def test_contract_cancellation_wins_when_nf_is_only_context():
    result = classify("Cancelar contrato referente às notas fiscais", DICTIONARY)

    assert result["intencao_id"] == "INT_CON_CANCELAMENTO"
    assert result["classificacao"] == "Contratos, Comercial e Cadastro"


def test_two_explicit_actions_in_different_classes_are_ambiguous():
    result = classify("Cancelar NF e cancelar contrato", DICTIONARY)

    assert result["status"] == "Ambígua"
    assert result["classificacao"] is None
    assert result["causa_canonica"] is None


def test_canceling_nf_and_boleto_together_is_ambiguous():
    result = classify(
        "Solicitar cancelamento da NF emitida e boleto",
        DICTIONARY,
    )

    assert result["status"] == "Ambígua"
    assert result["classificacao"] is None


def test_context_words_without_an_operational_action_do_not_classify():
    result = classify("NF, boleto, cobrança, contrato e CNPJ", DICTIONARY)

    assert result["status"] == "Sem correspondência"
    assert result["classificacao"] is None
    assert result["causa_canonica"] is None


def test_dictionary_causes_map_to_one_of_the_six_official_classes():
    assert validate_dictionary(DICTIONARY) == []


def test_suggestion_keeps_legacy_score_blank_and_explains_intention():
    result = suggest("cancelamento da NF", DICTIONARY, objects=OBJECTS)

    assert result["confianca"] is None
    assert result["motivo"] == "Cancelar, substituir ou reemitir nota fiscal."