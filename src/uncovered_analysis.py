"""Agrupa padrões textuais dos chamados sem sugestão para revisão do N2."""

from collections import Counter
import json
from pathlib import Path
import re

import pandas as pd

from extract import load_compilado_sheet, load_references, load_salesforce
from main import build_n2_dataframe
from parse_description import extract_problem
from root_cause_analysis import ngrams, tokenize


BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = BASE_DIR / "data" / "input" / "plano_n2_template.xlsx"
MONITORAMENTO_PATH = BASE_DIR / "data" / "input" / "monitoramento.xlsx"
WORKBOOK_PATH = BASE_DIR / "data" / "output" / "plano_n2_gerado.xlsx"
OUTPUT_PATH = BASE_DIR / "data" / "output" / "uncovered_analysis.json"

STATUS_UNCOVERED = "Sem correspondência"
STATUS_AMBIGUOUS = "Ambígua"
MIN_CLUSTER_SIZE = 2
MAX_CLUSTERS = 40

CLUSTER_STOPWORDS = {
    "anexo", "bom", "cielo", "dia", "deseja", "desejo", "ecommerce",
    "financeiro", "falar", "gerente", "meu", "nome", "obrigada",
    "obrigado", "ola", "prezados", "produto", "recebemos", "segue",
    "setor", "solicitacao", "sou", "time",
}
IDENTIFIER_PATTERNS = [
    re.compile(r"[\w.+-]+@[\w.-]+\.\w+"),
    re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}"),
    re.compile(r"\(?\d{2}\)?\s?\d{4,5}-?\d{4}"),
]
WORKBOOK_REQUIRED_COLUMNS = {
    "Número do Chamado",
    "Descrição",
    "Assunto",
    "Status da Sugestão",
    "Classificação Validada",
}


def _remove_identifiers(text: str) -> str:
    for pattern in IDENTIFIER_PATTERNS:
        text = pattern.sub(" ", text)
    return text


def _as_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _case_text(description, subject) -> tuple[str, str]:
    problem = extract_problem(description)
    if problem:
        return problem, "descricao_problema"
    return _as_text(subject), "assunto"


def _has_suggestion_results(dataframe: pd.DataFrame) -> bool:
    if not WORKBOOK_REQUIRED_COLUMNS.issubset(dataframe.columns):
        return False
    statuses = dataframe["Status da Sugestão"].fillna("").astype(str).str.strip()
    return statuses.ne("").any()


def analyze_uncovered(
    dataframe: pd.DataFrame,
    min_cluster_size: int = MIN_CLUSTER_SIZE,
    max_clusters: int = MAX_CLUSTERS,
) -> dict:
    """Gera clusters lexicais auditáveis; não infere causa nem cria regras."""

    required = {
        "Número do Chamado",
        "Descrição",
        "Assunto",
        "Status da Sugestão",
        "Classificação Validada",
    }
    missing = required.difference(dataframe.columns)
    if missing:
        raise ValueError(f"Colunas ausentes para análise de cobertura: {sorted(missing)}")

    uncovered = dataframe[
        dataframe["Status da Sugestão"] == STATUS_UNCOVERED
    ].copy()
    ambiguous_count = int(
        (dataframe["Status da Sugestão"] == STATUS_AMBIGUOUS).sum()
    )

    entries = []
    document_frequencies: dict[int, Counter[str]] = {
        size: Counter() for size in (1, 2, 3)
    }
    problem_missing = 0
    problem_short = 0
    tokenless = 0

    for _, row in uncovered.iterrows():
        problem = extract_problem(row["Descrição"])
        text, text_source = _case_text(row["Descrição"], row["Assunto"])
        if not problem:
            problem_missing += 1
        elif len(problem.strip()) < 40:
            problem_short += 1

        cleaned_text = _remove_identifiers(text)
        tokens = [
            token
            for token in tokenize(cleaned_text)
            if token not in CLUSTER_STOPWORDS
        ]
        if not tokens:
            tokenless += 1

        terms_by_size = {}
        for size in (1, 2, 3):
            terms = set(ngrams(tokens, size))
            terms_by_size[size] = terms
            document_frequencies[size].update(terms)

        entries.append({
            "ticket": str(row["Número do Chamado"]),
            "terms": terms_by_size,
            "validated_class": _as_text(row["Classificação Validada"]),
            "text_source": text_source,
        })

    candidates = [
        (size, term, count)
        for size, counter in document_frequencies.items()
        for term, count in counter.items()
        if count >= min_cluster_size
    ]
    candidates.sort(key=lambda item: (-item[0], -item[2], item[1]))

    remaining = set(range(len(entries)))
    clusters = []
    for size, term, _ in candidates:
        if len(clusters) >= max_clusters:
            break
        matched = [
            index
            for index in remaining
            if term in entries[index]["terms"][size]
        ]
        if len(matched) < min_cluster_size:
            continue

        validated_classes = Counter(
            entries[index]["validated_class"]
            for index in matched
            if entries[index]["validated_class"]
        )
        text_sources = Counter(entries[index]["text_source"] for index in matched)
        clusters.append({
            "padrao": term,
            "tamanho_ngram": size,
            "chamados": len(matched),
            "numeros_chamado": [entries[index]["ticket"] for index in matched],
            "fontes_texto": dict(text_sources),
            "classes_validadas_n2": dict(validated_classes),
            "revisao": "Confirmar relevância com N2 antes de propor regra.",
        })
        remaining.difference_update(matched)

    return {
        "chamados_sem_correspondencia": int(len(uncovered)),
        "chamados_ambiguos": ambiguous_count,
        "minimo_chamados_por_cluster": min_cluster_size,
        "metodo": (
            "Agrupamento lexical não sobreposto por trigramas, bigramas e unigramas "
            "do trecho Descrição do problema; usa Assunto quando o trecho está ausente."
        ),
        "diagnosticos_de_texto": {
            "descricao_do_problema_ausente": problem_missing,
            "descricao_do_problema_curta": problem_short,
            "sem_termos_apos_normalizacao": tokenless,
        },
        "clusters": clusters,
        "chamados_individuais": [
            entries[index]["ticket"] for index in sorted(remaining)
        ],
        "notas": [
            "Os clusters são exploratórios e não indicam automaticamente a causa da lacuna.",
            "Números dos chamados permitem revisão no fluxo operacional sem copiar descrições pessoais.",
        ],
    }


def main() -> None:
    dataframe = None
    if WORKBOOK_PATH.exists():
        workbook_data = load_compilado_sheet(WORKBOOK_PATH)
        if _has_suggestion_results(workbook_data):
            dataframe = workbook_data

    if dataframe is None:
        monitoramento = load_salesforce(MONITORAMENTO_PATH)
        references = load_references(TEMPLATE_PATH)
        history = load_compilado_sheet(TEMPLATE_PATH)
        dataframe = build_n2_dataframe(monitoramento, references, history)

    report = analyze_uncovered(dataframe)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Sem correspondência: {report['chamados_sem_correspondencia']}")
    print(f"Clusters: {len(report['clusters'])}")
    print(f"Chamados individuais: {len(report['chamados_individuais'])}")
    print(f"Análise salva: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()