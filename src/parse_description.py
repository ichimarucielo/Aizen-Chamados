"""Normalizacao e extracao de campos das descricoes do Salesforce."""

from __future__ import annotations

import html
import re

import pandas as pd


CNPJ_PATTERN = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}")
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
PHONE_PATTERN = re.compile(r"\(?\d{2}\)?\s?\d{4,5}-?\d{4}")

FORM_LABELS = (
    "Qual seu nome",
    "Endereco de e-mail",
    "Endereço de e-mail",
    "Telefone",
    "CNPJ",
    "CNPJ/CPF",
    "Assunto",
    "Merchant ID",
    "Sobre qual produto",
    "Como podemos te ajudar",
    "Data e hora do erro",
    "ID da transacao",
    "ID da transação",
    "Codigo do erro",
    "Código do erro",
    "GA Client ID",
    "Lead Hash ID",
    "Lead Form ID",
)

NEXT_FIELD_PATTERN = "|".join(re.escape(label) for label in FORM_LABELS)


def normalize_description(text: str) -> str:
    """Converte HTML e entidades em texto simples, preservando quebras de linha."""
    if text is None or pd.isna(text):
        return ""

    value = html.unescape(str(text))
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"</p\s*>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"</div\s*>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\s*\n\s*", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _extract_series(description_series: pd.Series, pattern: re.Pattern) -> pd.Series:
    return (
        description_series.fillna("").astype(str).str.extract(
            f"({pattern.pattern})",
            expand=False,
        )
    )


def extract_cnpj(description_series: pd.Series) -> pd.Series:
    return _extract_series(description_series, CNPJ_PATTERN)


def extract_email(description_series: pd.Series) -> pd.Series:
    return _extract_series(description_series, EMAIL_PATTERN)


def extract_phone(description_series: pd.Series) -> pd.Series:
    return _extract_series(description_series, PHONE_PATTERN)


def _extract_single_line(text: str, label: str) -> str:
    match = re.search(
        rf"{re.escape(label)}\s*:\s*([^\n]+)",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


def extract_problem(raw_description) -> str:
    """
    Extrai a solicitacao operacional do formulario.

    Nao depende do fechamento das tags HTML. Se a descricao estiver truncada,
    captura do marcador 'Descricao do problema' ate o proximo campo conhecido
    ou ate o fim do texto.
    """
    if raw_description is None or pd.isna(raw_description):
        return ""

    plain = normalize_description(str(raw_description))
    if not plain:
        return ""

    match = re.search(
        rf"Descri[cç][aã]o do problema\s*:\s*(.*?)"
        rf"(?=\n(?:{NEXT_FIELD_PATTERN})[^\n]*\s*:|\Z)",
        plain,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if match:
        problem = match.group(1).strip()
        if problem:
            return problem

    return plain


def parse_description(text: str) -> dict[str, str]:
    """Extrai os campos estruturados conhecidos do formulario."""
    plain = normalize_description(text)

    return {
        "email": _extract_single_line(plain, "Endereço de e-mail"),
        "telefone": _extract_single_line(plain, "Telefone"),
        "assunto": _extract_single_line(plain, "Assunto"),
        "merchant_id": _extract_single_line(
            plain,
            "Merchant ID/Estabelecimento Comercial (EC)",
        ),
        "descricao_problema": extract_problem(plain),
    }
