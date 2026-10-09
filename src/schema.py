"""Colunas compartilhadas e campos que o Aizen pode atualizar no compilado."""

SUGGESTION_COLUMNS = [
    "Intenção Identificada",
    "Causa Identificada",
    "ID Causa Padrão",
    "Causa Raiz Padrão",
    "Objeto Operacional Sugerido",
    "Classificação Sugerida",
    "Score Confiança",
]

TRACKING_COLUMNS = [
    "Regra Sugerida",
    "Status da Sugestão",
    "Motivo da Decisão",
    "Ambiguidade",
]

VALIDATION_COLUMNS = [
    "Objeto Operacional Validado",
    "Classificação Validada",
    "Concordância",
]

OPERATIONAL_UPDATE_COLUMNS = [
    "Status",
    "Situação",
    "Dias em Aberto",
    "Data da última modificação do chamado",
    "Descrição",
    "Descrição detalhada",
    "Assunto",
    "CNPJ",
    "Razão social",
    "Proprietário do Chamado",
]

AIZEN_OUTPUT_COLUMNS = SUGGESTION_COLUMNS + TRACKING_COLUMNS
UPDATE_COLUMNS = AIZEN_OUTPUT_COLUMNS + OPERATIONAL_UPDATE_COLUMNS
