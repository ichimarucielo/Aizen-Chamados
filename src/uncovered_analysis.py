"""Agrupa padrões textuais dos chamados sem sugestão para revisão do N2."""

from collections import Counter
import json
from pathlib import Path
import re

import pandas as pd

from extract import (
    load_compilado_sheet,
    load_references,
    load_salesforce,
)
from main import build_n2_dataframe
from parse_description import (
    extract_problem,
    normalize_description,
)
from root_cause_analysis import ngrams


BASE_DIR = Path(__file__).resolve().parent.parent

TEMPLATE_PATH = (
    BASE_DIR
    / "data"
    / "input"
    / "plano_n2_template.xlsx"
)

MONITORAMENTO_PATH = (
    BASE_DIR
    / "data"
    / "input"
    / "monitoramento.xlsx"
)

WORKBOOK_PATH = (
    BASE_DIR
    / "data"
    / "output"
    / "plano_n2_gerado.xlsx"
)

OUTPUT_PATH = (
    BASE_DIR
    / "data"
    / "output"
    / "uncovered_analysis.json"
)

STATUS_UNCOVERED = "Sem correspondência"
STATUS_AMBIGUOUS = "Ambígua"

MIN_CLUSTER_SIZE = 2
MAX_CLUSTERS = 40


# Termos que aparecem no formulário/e-mail, mas não ajudam
# a identificar a intenção operacional.
CLUSTER_STOPWORDS = {
    "a",
    "as",
    "o",
    "os",
    "de",
    "da",
    "das",
    "do",
    "dos",
    "e",
    "em",
    "no",
    "na",
    "nos",
    "nas",
    "por",
    "para",
    "um",
    "uma",
    "que",
    "é",
    "foi",
    "ser",
    "são",
    "ao",
    "aos",
    "à",
    "às",
    "com",
    "sem",
    "se",
    "já",
    "mais",
    "menos",
    "anexo",
    "bom",
    "cielo",
    "dia",
    "deseja",
    "desejo",
    "ecommerce",
    "financeiro",
    "falar",
    "gerente",
    "meu",
    "nome",
    "obrigada",
    "obrigado",
    "ola",
    "prezados",
    "produto",
    "recebemos",
    "segue",
    "setor",
    "solicitacao",
    "sou",
    "time",
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
    """Remove e-mails, CNPJ e telefones antes do agrupamento lexical."""
    for pattern in IDENTIFIER_PATTERNS:
        text = pattern.sub(" ", text)

    return text


def _as_text(value) -> str:
    """Converte valores da planilha para texto sem transformar NaN em 'nan'."""
    if pd.isna(value):
        return ""

    return str(value).strip()


def _cluster_tokens(text: str) -> list[str]:
    """Tokenização simples e previsível para agrupamento lexical."""
    text = _as_text(text).lower()

    # Remove HTML.
    text = re.sub(r"<[^>]+>", " ", text)

    # Remove pontuação, preservando letras acentuadas e números.
    text = re.sub(r"[^\wÀ-ÿ]+", " ", text)

    return [
        token
        for token in text.split()
        if token not in CLUSTER_STOPWORDS
        and len(token) > 1
    ]


def _has_problem_field(description) -> bool:
    """Detecta o campo 'Descrição do problema' em HTML ou texto puro."""
    raw = _as_text(description)

    if not raw:
        return False

    return bool(
        re.search(
            r"Descrição do problema:",
            raw,
            flags=re.IGNORECASE,
        )
    )


def _extract_problem_for_analysis(description) -> str:
    """
    Extrai 'Descrição do problema' tanto do HTML do formulário
    quanto de descrições em texto puro usadas nas análises/testes.
    """
    raw = _as_text(description)

    if not raw:
        return ""

    if not _has_problem_field(raw):
        return ""

    # Texto puro:
    # "Descrição do problema: alguma coisa"
    plain_match = re.search(
        r"Descrição do problema:\s*(.*)$",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Se não houver HTML relevante, usa diretamente o conteúdo
    # depois de "Descrição do problema:".
    if plain_match and "<strong" not in raw.lower():
        return normalize_description(
            plain_match.group(1)
        ).strip()

    # Formulário HTML: usa o parser oficial.
    problem = extract_problem(raw)

    if problem:
        return problem.strip()

    # Fallback final para texto puro.
    if plain_match:
        return normalize_description(
            plain_match.group(1)
        ).strip()

    return ""


def _case_text(description, subject) -> tuple[str, str]:
    """
    Retorna o texto operacional e sua origem.

    Quando existe 'Descrição do problema', usa esse trecho.
    Quando não existe, usa o Assunto.
    """
    problem = _extract_problem_for_analysis(description)

    if problem:
        return problem, "descricao_problema"

    return _as_text(subject), "assunto"


def _has_suggestion_results(dataframe: pd.DataFrame) -> bool:
    """Verifica se o workbook já possui resultados reais de sugestão."""
    if not WORKBOOK_REQUIRED_COLUMNS.issubset(dataframe.columns):
        return False

    statuses = (
        dataframe["Status da Sugestão"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

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
        raise ValueError(
            "Colunas ausentes para análise de cobertura: "
            f"{sorted(missing)}"
        )

    uncovered = dataframe[
        dataframe["Status da Sugestão"] == STATUS_UNCOVERED
    ].copy()

    ambiguous_count = int(
        (
            dataframe["Status da Sugestão"]
            == STATUS_AMBIGUOUS
        ).sum()
    )

    entries = []

    document_frequencies: dict[int, Counter[str]] = {
        size: Counter()
        for size in (1, 2, 3)
    }

    problem_missing = 0
    problem_short = 0
    tokenless = 0

    for _, row in uncovered.iterrows():
        description = row["Descrição"]
        subject = row["Assunto"]

        has_problem_field = _has_problem_field(
            description
        )

        problem = (
            extract_problem(description)
            if has_problem_field
            else ""
        )

        text, text_source = _case_text(
            description,
            subject,
        )

        # Diagnóstico do campo de problema:
        #
        # 1. Campo não existe -> ausente
        # 2. Campo existe, mas conteúdo é curto -> curta
        if not has_problem_field:
            problem_missing += 1

        elif len(problem.strip()) < 40:
            problem_short += 1

        cleaned_text = _remove_identifiers(text)

        # Tokenização própria do agrupamento.
        # Não depende do tokenizer do motor de causa.
        tokens = _cluster_tokens(cleaned_text)

        if not tokens:
            tokenless += 1

        terms_by_size = {}

        for size in (1, 2, 3):
            terms = set(
                ngrams(tokens, size)
            )

            terms_by_size[size] = terms
            document_frequencies[size].update(
                terms
            )

        entries.append(
            {
                "ticket": str(
                    row["Número do Chamado"]
                ),
                "terms": terms_by_size,
                "validated_class": _as_text(
                    row["Classificação Validada"]
                ),
                "text_source": text_source,
            }
        )

    candidates = [
        (size, term, count)
        for size, counter in document_frequencies.items()
        for term, count in counter.items()
        if count >= min_cluster_size
    ]

    # Prioriza trigramas, depois bigramas, depois unigramas.
    # Dentro do mesmo tamanho, prioriza termos mais frequentes.
    candidates.sort(
        key=lambda item: (
            -item[0],
            -item[2],
            item[1],
        )
    )

    remaining = set(
        range(len(entries))
    )

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

        text_sources = Counter(
            entries[index]["text_source"]
            for index in matched
        )

        clusters.append(
            {
                "padrao": term,
                "tamanho_ngram": size,
                "chamados": len(matched),
                "numeros_chamado": [
                    entries[index]["ticket"]
                    for index in matched
                ],
                "fontes_texto": dict(
                    text_sources
                ),
                "classes_validadas_n2": dict(
                    validated_classes
                ),
                "revisao": (
                    "Confirmar relevância com N2 "
                    "antes de propor regra."
                ),
            }
        )

        # Um chamado entra em apenas um cluster.
        remaining.difference_update(matched)

    return {
        "chamados_sem_correspondencia": int(
            len(uncovered)
        ),
        "chamados_ambiguos": ambiguous_count,
        "minimo_chamados_por_cluster": min_cluster_size,
        "metodo": (
            "Agrupamento lexical não sobreposto por "
            "trigramas, bigramas e unigramas do trecho "
            "Descrição do problema; usa Assunto quando "
            "o trecho está ausente."
        ),
        "diagnosticos_de_texto": {
            "descricao_do_problema_ausente": problem_missing,
            "descricao_do_problema_curta": problem_short,
            "sem_termos_apos_normalizacao": tokenless,
        },
        "clusters": clusters,
        "chamados_individuais": [
            entries[index]["ticket"]
            for index in sorted(remaining)
        ],
        "notas": [
            (
                "Os clusters são exploratórios e não indicam "
                "automaticamente a causa da lacuna."
            ),
            (
                "Números dos chamados permitem revisão no "
                "fluxo operacional sem copiar descrições pessoais."
            ),
        ],
    }


def main() -> None:
    dataframe = None

    if WORKBOOK_PATH.exists():
        workbook_data = load_compilado_sheet(
            WORKBOOK_PATH
        )

        if _has_suggestion_results(workbook_data):
            dataframe = workbook_data

    if dataframe is None:
        monitoramento = load_salesforce(
            MONITORAMENTO_PATH
        )

        references = load_references(
            TEMPLATE_PATH
        )

        history = load_compilado_sheet(
            TEMPLATE_PATH
        )

        dataframe = build_n2_dataframe(
            monitoramento,
            references,
            history,
        )

    report = analyze_uncovered(
        dataframe
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"Sem correspondência: "
        f"{report['chamados_sem_correspondencia']}"
    )

    print(
        f"Clusters: {len(report['clusters'])}"
    )

    print(
        f"Chamados individuais: "
        f"{len(report['chamados_individuais'])}"
    )

    print(
        f"Análise salva: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()