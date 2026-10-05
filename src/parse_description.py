import html
import re

import pandas as pd


def normalize_description(text: str) -> str:
    """
    Normaliza descrições vindas do Salesforce.
    """

    if not text:
        return ""

    text = str(text)

    text = html.unescape(text)

    text = re.sub(
        r"<br\s*/?>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"</p>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"<[^>]+>",
        "",
        text,
    )

    text = re.sub(
        r"\n\s*\n+",
        "\n\n",
        text,
    )

    return text.strip()


CNPJ_PATTERN = re.compile(
    r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}"
)

EMAIL_PATTERN = re.compile(
    r"[\w\.-]+@[\w\.-]+\.\w+"
)

PHONE_PATTERN = re.compile(
    r"\(?\d{2}\)?\s?\d{4,5}-?\d{4}"
)


def extract_cnpj(
    description_series: pd.Series,
) -> pd.Series:
    return (
        description_series
        .fillna("")
        .astype(str)
        .str.extract(
            f"({CNPJ_PATTERN.pattern})",
            expand=False,
        )
    )


def extract_email(
    description_series: pd.Series,
) -> pd.Series:
    return (
        description_series
        .fillna("")
        .astype(str)
        .str.extract(
            f"({EMAIL_PATTERN.pattern})",
            expand=False,
        )
    )


def extract_phone(
    description_series: pd.Series,
) -> pd.Series:
    return (
        description_series
        .fillna("")
        .astype(str)
        .str.extract(
            f"({PHONE_PATTERN.pattern})",
            expand=False,
        )
    )


FIELD_PATTERNS = {
    "email": r"Endereço de e-mail:\s*([^\n]+)",
    "telefone": r"Telefone:\s*([^\n]+)",
    "assunto": r"Assunto:\s*([^\n]+)",
    "merchant_id": (
        r"Merchant ID/Estabelecimento Comercial \(EC\):\s*([^\n]+)"
    ),
    "descricao_problema": (
        r"Descrição do problema:\s*(.*?)"
        r"(?=\n[A-ZÀ-Ú].*?:|\Z)"
    ),
}


def parse_description(
    text: str,
) -> dict[str, str]:
    """
    Extrai campos estruturados da descrição.
    """

    text = normalize_description(text)

    result: dict[str, str] = {}

    for field, pattern in FIELD_PATTERNS.items():
        match = re.search(
            pattern,
            text,
            flags=re.DOTALL,
        )

        result[field] = (
            match.group(1).strip()
            if match
            else ""
        )

    return result


def extract_problem(raw_description) -> str:
    """Trecho 'Descrição do problema' ou texto inteiro quando não houver formulário."""
    if pd.isna(raw_description):
        return ""

    text = str(raw_description)

    # Formulário HTML do Salesforce
    match = re.search(
        r"Descrição do problema:</strong>(.*?)(?:</p>|$)",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if match:
        return normalize_description(match.group(1))

    plain = normalize_description(text)

    # Formulário em texto simples
    labels = (
        r"(?:Qual seu nome|Endereço de e-mail|Telefone|CNPJ/CPF|"
        r"Assunto|Merchant ID|Sobre qual produto|Como podemos)"
    )

    match = re.search(
        r"Descrição do problema:\s*(.*?)(?=\n"
        + labels
        + r"[^\n]*:|\Z)",
        plain,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if match and match.group(1).strip():
        return match.group(1).strip()

    # E-mail / texto solto / assunto sem formulário
    return plain