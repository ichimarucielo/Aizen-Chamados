from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "output"
    / "plano_n2_gerado.xlsx"
)

SHEET_NAME = "Compilado chamados"
HEADER_ROW = 3

HISTORICAL_COLUMN = "Classificação"
SUGGESTED_COLUMN = "Classificação Sugerida"
STATUS_COLUMN = "Status da Sugestão"
RULE_COLUMN = "Regra Sugerida"
TICKET_COLUMN = "Número do Chamado"


def _normalize_text(series: pd.Series) -> pd.Series:
    """Normaliza campos textuais para comparações confiáveis."""
    return (
        series
        .fillna("")
        .astype(str)
        .str.strip()
    )


def _validate_columns(
    dataframe: pd.DataFrame,
    required_columns: list[str],
) -> None:
    """Garante que as colunas necessárias existem."""
    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise KeyError(
            "Colunas obrigatórias ausentes na planilha: "
            f"{missing_columns}"
        )


def load_dataframe() -> pd.DataFrame:
    """Carrega a aba Compilado chamados."""
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: '{INPUT_FILE}'."
        )

    dataframe = pd.read_excel(
        INPUT_FILE,
        sheet_name=SHEET_NAME,
        header=HEADER_ROW,
        engine="openpyxl",
    )

    _validate_columns(
        dataframe,
        [
            TICKET_COLUMN,
            HISTORICAL_COLUMN,
            SUGGESTED_COLUMN,
            STATUS_COLUMN,
            RULE_COLUMN,
        ],
    )

    return dataframe


def print_general_summary(
    dataframe: pd.DataFrame,
) -> None:
    """Exibe cobertura e distribuição geral do motor."""
    total = len(dataframe)

    statuses = dataframe[
        STATUS_COLUMN
    ].value_counts(
        dropna=False
    )

    classifications = dataframe[
        SUGGESTED_COLUMN
    ].value_counts(
        dropna=False
    )

    rules = dataframe[
        RULE_COLUMN
    ].value_counts(
        dropna=False
    ).head(10)

    suggested_count = int(
        dataframe[SUGGESTED_COLUMN]
        .notna()
        .sum()
    )

    coverage = (
        suggested_count / total
        if total
        else 0.0
    )

    print("\n=== RESUMO ===\n")

    print(f"Total: {total}")
    print(
        "Com classificação sugerida: "
        f"{suggested_count}"
    )
    print(f"Cobertura: {coverage:.1%}")

    print("\nStatus da Sugestão:\n")
    print(statuses)

    print("\nClassificações:\n")
    print(classifications)

    print("\nTop 10 Regras:\n")
    print(rules)


def build_comparison(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Cria a base comparável entre histórico e sugestão."""
    comparison = dataframe[
        dataframe[HISTORICAL_COLUMN].notna()
        & dataframe[SUGGESTED_COLUMN].notna()
    ].copy()

    comparison[
        "Classificação Histórica Normalizada"
    ] = _normalize_text(
        comparison[HISTORICAL_COLUMN]
    )

    comparison[
        "Classificação Sugerida Normalizada"
    ] = _normalize_text(
        comparison[SUGGESTED_COLUMN]
    )

    comparison["Concorda"] = (
        comparison[
            "Classificação Histórica Normalizada"
        ]
        == comparison[
            "Classificação Sugerida Normalizada"
        ]
    )

    return comparison


def print_comparison_summary(
    comparison: pd.DataFrame,
) -> None:
    """Exibe acurácia geral e acurácia por regra."""
    print("\n=== COMPARAÇÃO COM HISTÓRICO ===\n")

    total = len(comparison)

    print(f"Registros comparáveis: {total}")

    if comparison.empty:
        print(
            "Não existem registros suficientes "
            "para comparação."
        )
        return

    correct = int(
        comparison["Concorda"].sum()
    )

    disagreements = total - correct

    accuracy = correct / total

    print(f"Concordâncias: {correct}")
    print(f"Discordâncias: {disagreements}")
    print(f"Acurácia geral: {accuracy:.1%}")

    print("\nConcordância por regra:\n")

    rule_accuracy = (
        comparison
        .groupby(
            RULE_COLUMN,
            dropna=False,
        )
        .agg(
            Total=(
                TICKET_COLUMN,
                "count",
            ),
            Acertos=(
                "Concorda",
                "sum",
            ),
        )
    )

    rule_accuracy["Erros"] = (
        rule_accuracy["Total"]
        - rule_accuracy["Acertos"]
    )

    rule_accuracy["Acurácia"] = (
        rule_accuracy["Acertos"]
        / rule_accuracy["Total"]
    )

    rule_accuracy = rule_accuracy.sort_values(
        by=["Total", "Acurácia"],
        ascending=[False, True],
    )

    print(
        rule_accuracy.head(20).to_string(
            formatters={
                "Acurácia": (
                    lambda value: f"{value:.1%}"
                )
            }
        )
    )

    print("\nMatriz histórica x sugerida:\n")

    confusion_matrix = pd.crosstab(
        comparison[HISTORICAL_COLUMN],
        comparison[SUGGESTED_COLUMN],
        margins=True,
        margins_name="Total",
    )

    print(confusion_matrix.to_string())


def export_disagreements(
    comparison: pd.DataFrame,
) -> None:
    """Exporta divergências para análise manual."""
    disagreements = comparison[
        ~comparison["Concorda"]
    ].copy()

    if disagreements.empty:
        print(
            "\nNenhuma divergência encontrada."
        )
        return

    desired_columns = [
        TICKET_COLUMN,
        HISTORICAL_COLUMN,
        SUGGESTED_COLUMN,
        RULE_COLUMN,
        STATUS_COLUMN,
        "Motivo da Decisão",
        "Assunto",
        "Descrição detalhada",
        "Intenção Identificada",
        "Causa Identificada",
        "Causa Raiz Padrão",
    ]

    available_columns = [
        column
        for column in desired_columns
        if column in disagreements.columns
    ]

    output_file = (
        BASE_DIR
        / "data"
        / "output"
        / "aizen_divergencias.xlsx"
    )

    disagreements[
        available_columns
    ].to_excel(
        output_file,
        index=False,
        engine="openpyxl",
    )

    print(
        "\nDivergências exportadas: "
        f"{len(disagreements)}"
    )

    print(
        f"Arquivo: {output_file}"
    )


def export_unmatched(
    dataframe: pd.DataFrame,
) -> None:
    unmatched = dataframe[
        dataframe[STATUS_COLUMN]
        == "Sem correspondência"
    ].copy()

    output_file = (
        BASE_DIR
        / "data"
        / "output"
        / "aizen_sem_padrao.xlsx"
    )

    columns = [
        TICKET_COLUMN,
        "Assunto",
        "Descrição",
        "Descrição detalhada",
        "Causa raiz",
        HISTORICAL_COLUMN,
        "Motivo da Decisão",
    ]

    available_columns = [
        column
        for column in columns
        if column in unmatched.columns
    ]

    unmatched[
        available_columns
    ].to_excel(
        output_file,
        index=False,
        engine="openpyxl",
    )

    print(
        f"\nCasos sem padrão exportados: {len(unmatched)}"
    )
    print(f"Arquivo: {output_file}")


def main() -> None:
    dataframe = load_dataframe()

    print_general_summary(
        dataframe
    )

    comparison = build_comparison(
        dataframe
    )

    print_comparison_summary(
        comparison
    )

    export_unmatched(
        dataframe
    )

    export_disagreements(
        comparison
    )


if __name__ == "__main__":
    main()