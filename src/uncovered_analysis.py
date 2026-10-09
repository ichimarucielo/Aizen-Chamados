"""Agrupa lacunas de classificação para revisão do N2."""

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
from root_cause_engine import (
    REASON_NO_PATTERN,
    extract_signature,
    load_dictionary,
    normalize_text,
)


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
REASON_CONTRACT_NOT_FOUND = "CONTRACT_NOT_FOUND"
GAP_REASONS = {REASON_NO_PATTERN, REASON_CONTRACT_NOT_FOUND}

MIN_CLUSTER_SIZE = 2
MAX_CLUSTERS = 40
MAX_CONTRACT_GAPS = 40


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
    re.compile(
        r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}"
    ),
    re.compile(
        r"\(?\d{2}\)?\s?\d{4,5}-?\d{4}"
    ),
]


WORKBOOK_REQUIRED_COLUMNS = {
    "Número do Chamado",
    "Descrição",
    "Assunto",
    "Status da Sugestão",
    "Classificação Validada",
}


def _remove_identifiers(text: str) -> str:
    """Remove e-mails, CNPJ e telefones."""
    for pattern in IDENTIFIER_PATTERNS:
        text = pattern.sub(" ", text)

    return text


def _as_text(value) -> str:
    """Converte valor para texto sem transformar NaN em 'nan'."""
    if pd.isna(value):
        return ""

    return str(value).strip()


def _cluster_tokens(text: str) -> list[str]:
    """Tokenização simples para agrupamento lexical."""
    normalized = _as_text(text).lower()

    normalized = re.sub(
        r"<[^>]+>",
        " ",
        normalized,
    )

    normalized = re.sub(
        r"[^\wÀ-ÿ]+",
        " ",
        normalized,
    )

    return [
        token
        for token in normalized.split()
        if token not in CLUSTER_STOPWORDS
        and len(token) > 1
    ]


def _has_problem_field(description) -> bool:
    """Detecta o campo Descrição do problema."""
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


def _extract_problem_for_analysis(
    description,
) -> str:
    """Extrai o conteúdo operacional da descrição."""
    raw = _as_text(description)

    if not raw:
        return ""

    if not _has_problem_field(raw):
        return ""

    plain_match = re.search(
        r"Descrição do problema:\s*(.*)$",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if (
        plain_match
        and "<strong" not in raw.lower()
    ):
        return normalize_description(
            plain_match.group(1)
        ).strip()

    problem = extract_problem(raw)

    if problem:
        return problem.strip()

    if plain_match:
        return normalize_description(
            plain_match.group(1)
        ).strip()

    return ""


def _case_text(
    description,
    subject,
) -> tuple[str, str]:
    """Retorna texto operacional e origem."""
    problem = _extract_problem_for_analysis(
        description
    )

    if problem:
        return problem, "descricao_problema"

    return _as_text(subject), "assunto"


def _has_suggestion_results(
    dataframe: pd.DataFrame,
) -> bool:
    """Verifica se o workbook possui resultados do motor."""
    if not WORKBOOK_REQUIRED_COLUMNS.issubset(
        dataframe.columns
    ):
        return False

    statuses = (
        dataframe["Status da Sugestão"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    return statuses.ne("").any()


def _extract_concept_groups(
    text: str,
    dictionary: dict,
) -> tuple[list[str], list[str], list[str]]:
    """Separa conceitos identificados por categoria."""
    concepts = extract_signature(text, dictionary)

    objects = sorted(f"OBJETO:{value}" for value in concepts["objetos"])
    actions = sorted(f"ACAO:{value}" for value in concepts["acoes"])
    contexts = sorted(
        [f"CONTEXTO:{value}" for value in concepts["contextos"]]
        + [f"CANAL:{value}" for value in concepts["canais"]]
    )

    return objects, actions, contexts


def _build_contract_signature(
    objects: list[str],
    actions: list[str],
    contexts: list[str],
) -> str:
    """Cria assinatura determinística dos conceitos."""
    return " + ".join(
        objects + actions + contexts
    )


def analyze_uncovered(
    dataframe: pd.DataFrame,
    min_cluster_size: int = MIN_CLUSTER_SIZE,
    max_clusters: int = MAX_CLUSTERS,
) -> dict:
    """Analisa padrões lexicais e contratos ausentes."""
    missing = WORKBOOK_REQUIRED_COLUMNS.difference(
        dataframe.columns
    )

    if missing:
        raise ValueError(
            "Colunas ausentes para análise de cobertura: "
            f"{sorted(missing)}"
        )

    uncovered = dataframe[
        dataframe["Status da Sugestão"]
        == STATUS_UNCOVERED
    ].copy()

    ambiguous_count = int(
        (
            dataframe["Status da Sugestão"]
            == STATUS_AMBIGUOUS
        ).sum()
    )

    dictionary = load_dictionary()

    entries = []
    contract_signatures: Counter[str] = Counter()

    document_frequencies: dict[
        int,
        Counter[str],
    ] = {
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

        reason_code = _as_text(
            row.get("Motivo da Decisão")
        )

        objects, actions, contexts = (
            _extract_concept_groups(
                text,
                dictionary,
            )
        )

        signature = _build_contract_signature(
            objects,
            actions,
            contexts,
        )

        if (
            reason_code
            in GAP_REASONS
            and signature
        ):
            contract_signatures[signature] += 1

        if not has_problem_field:
            problem_missing += 1
        elif len(_as_text(problem)) < 40:
            problem_short += 1

        cleaned_text = _remove_identifiers(
            text
        )

        tokens = _cluster_tokens(
            cleaned_text
        )

        if not tokens:
            tokenless += 1

        terms_by_size: dict[int, set[str]] = {}

        for size in (1, 2, 3):
            terms = set(
                ngrams(
                    tokens,
                    size,
                )
            )

            terms_by_size[size] = terms

            document_frequencies[size].update(
                terms
            )

        entries.append(
            {
                "ticket": _as_text(
                    row["Número do Chamado"]
                ),
                "terms": terms_by_size,
                "validated_class": _as_text(
                    row["Classificação Validada"]
                ),
                "text_source": text_source,
                "reason_code": reason_code,
                "objects": objects,
                "actions": actions,
                "contexts": contexts,
                "signature": signature,
            }
        )

    candidates = [
        (size, term, count)
        for size, counter
        in document_frequencies.items()
        for term, count in counter.items()
        if count >= min_cluster_size
    ]

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

        remaining.difference_update(
            matched
        )

    contract_gaps = []

    for signature, quantity in (
        contract_signatures.most_common(
            MAX_CONTRACT_GAPS
        )
    ):
        matching_entries = [
            entry
            for entry in entries
            if (
                entry["reason_code"]
                in GAP_REASONS
                and entry["signature"]
                == signature
            )
        ]

        first_entry = matching_entries[0]

        validated_classes = Counter(
            entry["validated_class"]
            for entry in matching_entries
            if entry["validated_class"]
        )

        contract_gaps.append(
            {
                "assinatura": signature,
                "quantidade": quantity,
                "objetos": first_entry["objects"],
                "acoes": first_entry["actions"],
                "contextos": first_entry["contexts"],
                "numeros_chamado": [
                    entry["ticket"]
                    for entry in matching_entries
                ],
                "classes_validadas_n2": dict(
                    validated_classes
                ),
                "revisao": (
                    "Avaliar criação de contrato somente "
                    "se a combinação indicar classe inequívoca."
                ),
            }
        )

    reason_counts = Counter(
        entry["reason_code"]
        for entry in entries
        if entry["reason_code"]
    )

    return {
        "chamados_sem_correspondencia": int(
            len(uncovered)
        ),
        "chamados_ambiguos": ambiguous_count,
        "motivos_da_decisao": dict(
            reason_counts
        ),
        "minimo_chamados_por_cluster": (
            min_cluster_size
        ),
        "metodo": (
            "Agrupamento lexical e análise das "
            "combinações de conceitos sem contrato."
        ),
        "diagnosticos_de_texto": {
            "descricao_do_problema_ausente": (
                problem_missing
            ),
            "descricao_do_problema_curta": (
                problem_short
            ),
            "sem_termos_apos_normalizacao": (
                tokenless
            ),
        },
        "lacunas_de_contrato": contract_gaps,
        "clusters": clusters,
        "chamados_individuais": [
            entries[index]["ticket"]
            for index in sorted(remaining)
        ],
        "notas": [
            (
                "As lacunas de contrato agrupam conceitos reconhecidos em "
                "casos sem correspondência. Exigem revisão da evidência, "
                "dos padrões e das assinaturas antes de propor uma regra."
            ),
            (
                "Os clusters lexicais são exploratórios "
                "e não criam regras automaticamente."
            ),
        ],
    }


def main() -> None:
    dataframe = None

    if WORKBOOK_PATH.exists():
        workbook_data = load_compilado_sheet(
            WORKBOOK_PATH
        )

        if _has_suggestion_results(
            workbook_data
        ):
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
        "Sem correspondência: "
        f"{report['chamados_sem_correspondencia']}"
    )

    print(
        f"Clusters lexicais: "
        f"{len(report['clusters'])}"
    )

    print(
        f"Lacunas de contrato: "
        f"{len(report['lacunas_de_contrato'])}"
    )

    print("\nTop combinações sem contrato:\n")

    for gap in report[
        "lacunas_de_contrato"
    ][:20]:
        print(
            f"{gap['quantidade']:>4} | "
            f"{gap['assinatura']}"
        )

    print(
        "\nChamados individuais: "
        f"{len(report['chamados_individuais'])}"
    )

    print(
        f"Análise salva: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
