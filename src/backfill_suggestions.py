from pathlib import Path

import pandas as pd

from export import export_plano_n2
from extract import load_compilado_sheet
from root_cause_engine import build_suggestions
from classification_input import build_classification_input
from schema import AIZEN_OUTPUT_COLUMNS

BASE_DIR = Path(__file__).resolve().parent.parent

TEMPLATE_PATH = (
    BASE_DIR
    / "data"
    / "input"
    / "plano_n2_template.xlsx"
)

OUTPUT_PATH = (
    BASE_DIR
    / "data"
    / "output"
    / "plano_n2_gerado.xlsx"
)

KEY_COLUMN = "Número do Chamado"


def _select_pending_rows(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Reprocessa todo o histórico com o motor MVP atual."""
    return dataframe.copy()


def _build_status(
    suggestions: pd.DataFrame,
) -> pd.Series:
    """Traduz o retorno técnico para o status operacional."""
    return pd.Series(
        [
            (
                "Ambígua"
                if bool(ambiguous)
                else "Sugerida"
                if pd.notna(classification)
                else "Sem correspondência"
            )
            for classification, ambiguous in zip(
                suggestions["classificacao"],
                suggestions["ambiguo"],
            )
        ],
        index=suggestions.index,
        dtype="object",
    )


def build_backfill_dataframe(
    pending_df: pd.DataFrame,
) -> pd.DataFrame:
    """Executa o motor sobre os históricos pendentes."""
    descriptions = build_classification_input(
        pending_df
    )

    suggestions = build_suggestions(
        descriptions=descriptions,
        history=pending_df,
    )

    result = pd.DataFrame(
        index=pending_df.index
    )

    result[KEY_COLUMN] = pending_df[
        KEY_COLUMN
    ]

    result["Intenção Identificada"] = suggestions[
        "intencao_identificada"
    ]

    result["Causa Identificada"] = suggestions[
        "causa_identificada"
    ].map(
        lambda values: (
            "; ".join(values)
            if isinstance(values, list)
            else ""
        )
    )

    result["ID Causa Padrão"] = suggestions["causa_id"]
    result["Causa Raiz Padrão"] = suggestions["causa_padrao"]

    result["Objeto Operacional Sugerido"] = suggestions[
        "objeto_operacional"
    ]

    result["Classificação Sugerida"] = suggestions[
        "classificacao"
    ]

    result["Score Confiança"] = suggestions[
        "confianca"
    ]

    result["Regra Sugerida"] = suggestions[
        "regra"
    ]

    result["Status da Sugestão"] = _build_status(
        suggestions
    )

    result["Motivo da Decisão"] = suggestions[
        "reason_code"
    ]

    result["Ambiguidade"] = suggestions[
        "ambiguo"
    ]

    return result[
        [KEY_COLUMN] + AIZEN_OUTPUT_COLUMNS
    ]


def print_summary(
    backfill_df: pd.DataFrame,
) -> None:
    """Exibe as métricas do lote de backfill."""
    total = len(backfill_df)

    suggested = int(
        backfill_df[
            "Classificação Sugerida"
        ].notna().sum()
    )

    ambiguous = int(
        (
            backfill_df["Status da Sugestão"]
            == "Ambígua"
        ).sum()
    )

    unmatched = int(
        (
            backfill_df["Status da Sugestão"]
            == "Sem correspondência"
        ).sum()
    )

    coverage = (
        suggested / total
        if total
        else 0.0
    )

    print("\n=== BACKFILL AIZEN ===")
    print(f"Pendentes processados: {total}")
    print(f"Com classificação sugerida: {suggested}")
    print(f"Ambíguos: {ambiguous}")
    print(f"Sem correspondência: {unmatched}")
    print(f"Cobertura do backfill: {coverage:.1%}")

    print("\nMotivos da decisão:")

    print(
        backfill_df["Motivo da Decisão"]
        .fillna("SEM_MOTIVO")
        .value_counts(
            dropna=False
        )
    )


def main() -> None:
    if not OUTPUT_PATH.exists():
        raise FileNotFoundError(
            "O arquivo gerado ainda não existe: "
            f"'{OUTPUT_PATH}'. Execute src/main.py primeiro."
        )

    compilado_df = load_compilado_sheet(
        OUTPUT_PATH
    )

    if KEY_COLUMN not in compilado_df.columns:
        raise KeyError(
            f"A coluna '{KEY_COLUMN}' não existe "
            "na aba Compilado chamados."
        )

    pending_df = _select_pending_rows(
        compilado_df
    )

    print(
        f"Registros no compilado: "
        f"{len(compilado_df)}"
    )

    print(
        f"Registros pendentes: "
        f"{len(pending_df)}"
    )

    if pending_df.empty:
        print(
            "Nenhum chamado pendente de classificação."
        )
        return

    backfill_df = build_backfill_dataframe(
        pending_df
    )

    print_summary(
        backfill_df
    )

    generated_file, inserted = export_plano_n2(
        dataframe=backfill_df,
        template_path=TEMPLATE_PATH,
        output_path=OUTPUT_PATH,
    )

    if not inserted.empty:
        raise RuntimeError(
            "O backfill tentou inserir chamados novos. "
            "A operação deveria somente atualizar registros existentes."
        )

    print(
        f"\nArquivo atualizado: {generated_file}"
    )

    print(
        "Nenhum chamado novo foi inserido."
    )


if __name__ == "__main__":
    main()