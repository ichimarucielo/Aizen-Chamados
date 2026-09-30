import pandas as pd


def normalize_key(value: str) -> str:
    """
    Remove formatação da chave.
    """

    if pd.isna(value):
        return ""

    return "".join(
        filter(str.isdigit, str(value))
    )


def build_razao_social_lookup(
    references_df: pd.DataFrame,
) -> dict[str, str]:
    """
    Cria índice CNPJ -> Razão Social.
    """

    lookup = {}

    for _, row in references_df.iterrows():
        key = normalize_key(
            row["CNPJ"]
        )

        if key:
            lookup[key] = row["Cliente"]

    return lookup


def lookup_razao_social(
    cnpj: str,
    lookup_dict: dict[str, str],
) -> str:
    """
    Retorna razão social.
    """

    return lookup_dict.get(
        normalize_key(cnpj),
        "",
    )