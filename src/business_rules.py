from datetime import datetime

import pandas as pd


def apply_situacao(
    status: str,
) -> str:
    """
    Regra MVP.

    Todo chamado aberto entra como PENDENTE.
    """

    if pd.isna(status):
        return "PENDENTE"

    status = str(status).strip().upper()

    if status in {
        "RESOLVIDO",
        "FINALIZADO",
        "FECHADO",
    }:
        return "FINALIZADO"

    return "PENDENTE"


def apply_dias_aberto(
    data_abertura,
) -> int:
    """
    Calcula dias corridos em aberto.
    """

    if pd.isna(data_abertura):
        return 0

    pd.to_datetime(
        data_abertura,
        dayfirst=True,
    )