"""Entrada única de classificação para processamento, backfill e avaliação."""

import pandas as pd

from parse_description import parse_description


def _text_column(dataframe: pd.DataFrame, name: str) -> pd.Series:
    empty = pd.Series("", index=dataframe.index, dtype=object)
    return dataframe.get(name, empty).fillna("").astype(str).str.strip()


def prepare_descriptions(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Combina assunto interno e problema; usa descrição histórica e assunto como fallback."""
    parsed = _text_column(dataframe, "Descrição").apply(parse_description)
    subject = parsed.map(lambda value: value["assunto"])
    problem = parsed.map(lambda value: value["descricao_problema"])
    detailed = problem.mask(problem.eq(""), _text_column(dataframe, "Descrição detalhada"))
    classification = detailed.copy()
    both = subject.ne("") & detailed.ne("")
    classification.loc[both] = subject.loc[both] + ". " + detailed.loc[both]
    classification = classification.mask(classification.eq(""), subject)
    external_subject = _text_column(dataframe, "Assunto")
    classification = classification.mask(classification.eq(""), external_subject)
    detailed = detailed.mask(detailed.eq(""), external_subject)
    return pd.DataFrame({
        "Descrição detalhada": detailed,
        "Entrada de Classificação": classification,
    }, index=dataframe.index)


def build_classification_input(dataframe: pd.DataFrame) -> pd.Series:
    return prepare_descriptions(dataframe)["Entrada de Classificação"]
