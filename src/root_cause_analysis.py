"""Analisa padroes historicos para apoiar o dicionario de causa raiz.

Este modulo e exploratorio. Ele nao classifica chamados novos nem cria regras
automaticas; produz candidatos para revisao da equipe N2.
"""

from collections import Counter
from pathlib import Path
import json
import re
import unicodedata

import pandas as pd

from extract import load_compilado_sheet
from parse_description import normalize_description


BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = BASE_DIR / "data" / "input" / "plano_n2_template.xlsx"
OUTPUT_PATH = BASE_DIR / "data" / "output" / "causa_raiz_analise.json"

TEXT_COLUMN = "Descrição detalhada"
ROOT_CAUSE_COLUMN = "Causa raiz"

STOPWORDS = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do",
    "dos", "e", "em", "era", "essa", "esse", "esta", "este", "eu",
    "foi", "for", "ha", "isso", "isto", "ja", "mais", "mas", "me",
    "mesmo", "na", "nas", "no", "nos", "o", "os", "ou", "para", "por",
    "que", "se", "sem", "ser", "sua", "suas", "tambem", "um", "uma",
    "umas", "uns", "vai", "voce", "bem", "boa", "bom", "dia", "tarde",
    "cliente", "favor", "tudo", "nao",
}

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def tokenize(text: str) -> list[str]:
    normalized = _strip_accents(normalize_description(text).lower())
    return [
        token
        for token in TOKEN_PATTERN.findall(normalized)
        if token not in STOPWORDS and len(token) > 2 and not token.isdigit()
    ]


def ngrams(tokens: list[str], size: int) -> Counter[str]:
    return Counter(
        " ".join(tokens[index:index + size])
        for index in range(len(tokens) - size + 1)
    )


def _ranked_terms(counter: Counter[str], limit: int = 20) -> list[dict]:
    return [
        {"term": term, "occurrences": count}
        for term, count in counter.most_common(limit)
    ]


def _exclusive_terms(
    group_counter: Counter[str],
    other_counter: Counter[str],
    limit: int = 20,
) -> list[dict]:
    candidates = [
        (term, count)
        for term, count in group_counter.items()
        if other_counter[term] == 0
    ]
    candidates.sort(key=lambda item: (-item[1], item[0]))
    return [
        {"term": term, "occurrences": count}
        for term, count in candidates[:limit]
    ]


def analyze_root_causes(dataframe: pd.DataFrame) -> dict:
    required_columns = {TEXT_COLUMN, ROOT_CAUSE_COLUMN}
    missing_columns = required_columns.difference(dataframe.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Colunas obrigatorias ausentes: {missing}")

    working = dataframe[[TEXT_COLUMN, ROOT_CAUSE_COLUMN]].copy()
    working[TEXT_COLUMN] = working[TEXT_COLUMN].fillna("").astype(str)
    working[ROOT_CAUSE_COLUMN] = (
        working[ROOT_CAUSE_COLUMN].fillna("").astype(str).str.strip()
    )
    working = working[working[ROOT_CAUSE_COLUMN] != ""]
    working["tokens"] = working[TEXT_COLUMN].map(tokenize)

    all_tokens = Counter(
        token
        for tokens in working["tokens"]
        for token in set(tokens)
    )
    result = {
        "historical_records": int(len(dataframe)),
        "records_with_root_cause": int(len(working)),
        "distinct_root_causes": int(working[ROOT_CAUSE_COLUMN].nunique()),
        "root_causes": {},
    }

    for cause, group in working.groupby(ROOT_CAUSE_COLUMN, sort=True):
        group_counter = Counter(
            token
            for tokens in group["tokens"]
            for token in tokens
        )
        other = working[working[ROOT_CAUSE_COLUMN] != cause]
        other_counter = Counter(
            token
            for tokens in other["tokens"]
            for token in tokens
        )
        group_bigrams = Counter(
            phrase
            for tokens in group["tokens"]
            for phrase, count in ngrams(tokens, 2).items()
            for _ in range(count)
        )
        group_trigrams = Counter(
            phrase
            for tokens in group["tokens"]
            for phrase, count in ngrams(tokens, 3).items()
            for _ in range(count)
        )

        result["root_causes"][cause] = {
            "occurrences": int(len(group)),
            "top_words": _ranked_terms(group_counter),
            "bigrams": _ranked_terms(group_bigrams),
            "trigrams": _ranked_terms(group_trigrams),
            "exclusive_words": _exclusive_terms(group_counter, other_counter),
            "candidate_rule": {
                "required": [],
                "optional": [
                    item["term"]
                    for item in _ranked_terms(group_counter, 5)
                ],
                "excluded": [],
                "cause": cause,
            },
        }

    result["global_top_words"] = _ranked_terms(all_tokens)
    return result


def main() -> None:
    dataframe = load_compilado_sheet(TEMPLATE_PATH)
    analysis = analyze_root_causes(dataframe)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Historicos analisados: {analysis['historical_records']}")
    print(f"Com causa raiz: {analysis['records_with_root_cause']}")
    print(f"Causas distintas: {analysis['distinct_root_causes']}")
    print(f"Analise gerada: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()