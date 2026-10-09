from pathlib import Path

import pandas as pd

from business_rules import (
    apply_dias_aberto,
    apply_situacao,
)
from export import export_plano_n2
from extract import (
    load_compilado_sheet,
    load_references,
    load_salesforce,
)
from lookup import (
    build_razao_social_lookup,
    lookup_razao_social,
)
from parse_description import extract_cnpj
from classification_input import prepare_descriptions
from schema import AIZEN_OUTPUT_COLUMNS, VALIDATION_COLUMNS
from root_cause_engine import build_suggestions

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

OUTPUT_PATH = (
    BASE_DIR
    / "data"
    / "output"
    / "plano_n2_gerado.xlsx"
)


COMPILADO_COLUMNS = [
    "Obs",
    "RESPONSÁVEL",
    "Classificação",
    "Número do Chamado",
    "Chamado Pai (clone)",
    "Número de protocolo",
    "Razão social",
    "CNPJ",
    "Causa raiz",
    "Observação/Ação",
    "Ofensor",
    "Status",
    "Prioridade",
    "Assunto",
    "Data de abertura",
    "Data da última modificação do chamado",
    "Mês/Ano",
    "Proprietário do Chamado",
    "Email da Web",
    "Nome Fantasia",
    "Descrição",
    "Descrição detalhada",
    "Ref.",
    "Dt.Encerramento",
    "Situação",
    "Dias em Aberto",
    "Aux_Ranking",
    "Origem",
]


def _month_year(value) -> str:
    if pd.isna(value):
        return ""

    months = [
        "jan",
        "fev",
        "mar",
        "abr",
        "mai",
        "jun",
        "jul",
        "ago",
        "set",
        "out",
        "nov",
        "dez",
    ]

    date = pd.to_datetime(value, dayfirst=True)

    return f"{months[date.month - 1]}/{date.year}"


def build_n2_dataframe(
    monitoramento_df: pd.DataFrame,
    references_df: pd.DataFrame,
    history_df: pd.DataFrame,
) -> pd.DataFrame:
    """Mapeia o relatório do Salesforce para o layout Compilado chamados."""

    dataframe = monitoramento_df.copy()

    # ------------------------------------------------------------
    # 1. Dados básicos
    # ------------------------------------------------------------
    description = (
        dataframe["Descrição"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    dataframe["CNPJ"] = extract_cnpj(description)
    descriptions = prepare_descriptions(dataframe)
    dataframe["DESCRICAO_NORMALIZADA"] = descriptions["Descrição detalhada"]
    dataframe["ENTRADA_CLASSIFICACAO"] = descriptions["Entrada de Classificação"]

    # ------------------------------------------------------------
    # 3. Razão social
    # ------------------------------------------------------------
    razao_social_lookup = build_razao_social_lookup(
        references_df
    )

    dataframe["RAZAO_SOCIAL"] = dataframe["CNPJ"].apply(
        lambda value: lookup_razao_social(
            value,
            razao_social_lookup,
        )
    )

    # ------------------------------------------------------------
    # 4. Causa raiz histórica, quando existir
    # ------------------------------------------------------------
    causa_raiz = dataframe.get(
        "Causa raiz",
        pd.Series("", index=dataframe.index),
    ).fillna("")

    # ------------------------------------------------------------
    # 5. Lookup de classificação histórica
    # ------------------------------------------------------------
    classificacao_lookup = {
        str(row["Tema"]).strip(): row["Macro Classificação"]
        for _, row in references_df.iterrows()
        if pd.notna(row.get("Tema"))
        and pd.notna(row.get("Macro Classificação"))
    }

    # ------------------------------------------------------------
    # 6. Estrutura de saída
    # ------------------------------------------------------------
    result = pd.DataFrame(index=dataframe.index)

    result["Obs"] = ""
    result["RESPONSÁVEL"] = ""

    result["Classificação"] = causa_raiz.map(
        lambda value: classificacao_lookup.get(
            str(value).strip(),
            "",
        )
    )

    result["Número do Chamado"] = dataframe[
        "Número do Chamado"
    ]

    result["Chamado Pai (clone)"] = dataframe[
        "Número de Chamado Pai"
    ]

    result["Número de protocolo"] = dataframe[
        "Número Protocolo"
    ]

    result["Razão social"] = dataframe[
        "RAZAO_SOCIAL"
    ]

    result["CNPJ"] = dataframe[
        "CNPJ"
    ]

    result["Causa raiz"] = causa_raiz

    result["Observação/Ação"] = ""
    result["Ofensor"] = ""

    result["Status"] = dataframe[
        "Status"
    ]

    result["Prioridade"] = ""

    result["Assunto"] = dataframe[
        "Assunto"
    ]

    result["Data de abertura"] = dataframe[
        "Data de abertura"
    ]

    result["Data da última modificação do chamado"] = (
        dataframe[
            "Data da última modificação do chamado"
        ]
    )

    result["Mês/Ano"] = dataframe[
        "Data de abertura"
    ].apply(_month_year)

    result["Proprietário do Chamado"] = dataframe[
        "Proprietário do Chamado"
    ]

    result["Email da Web"] = dataframe[
        "Email da Web"
    ]

    result["Nome Fantasia"] = dataframe[
        "Nome Fantasia"
    ]

    result["Descrição"] = dataframe[
        "Descrição"
    ]

    result["Descrição detalhada"] = dataframe[
        "DESCRICAO_NORMALIZADA"
    ]

    result["Ref."] = ""
    result["Dt.Encerramento"] = ""

    result["Situação"] = dataframe[
        "Status"
    ].apply(apply_situacao)

    result["Dias em Aberto"] = dataframe[
        "Data de abertura"
    ].apply(apply_dias_aberto)

    result["Aux_Ranking"] = ""
    result["Origem"] = ""

    # ------------------------------------------------------------
    # 7. Motor determinístico
    # ------------------------------------------------------------
    suggestions = build_suggestions(
        dataframe["ENTRADA_CLASSIFICACAO"],
        history_df,
    )

    identified_causes = suggestions[
        "causa_identificada"
    ].map(
        lambda terms: "; ".join(terms)
        if terms
        else ""
    )

    standard_causes = suggestions[
        "causa_padrao"
    ]

    standard_cause_ids = suggestions[
        "causa_id"
    ]

    # ------------------------------------------------------------
    # 8. Preenchimento das sugestões
    # ------------------------------------------------------------
    result["Intenção Identificada"] = suggestions[
        "intencao_identificada"
    ]

    result["Causa Identificada"] = identified_causes

    result["ID Causa Padrão"] = standard_cause_ids

    result["Causa Raiz Padrão"] = standard_causes

    result["Causa raiz"] = standard_causes.where(
        standard_causes.notna(),
        result["Causa raiz"],
    )

    result["Classificação"] = suggestions[
        "classificacao"
    ].where(
        suggestions["classificacao"].notna(),
        result["Classificação"],
    )

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

    result["Ambiguidade"] = suggestions[
        "ambiguo"
    ]

    result["Status da Sugestão"] = [
        (
            "Ambígua"
            if ambiguous
            else "Sugerida"
            if pd.notna(classification)
            else "Sem correspondência"
        )
        for classification, ambiguous in zip(
            suggestions["classificacao"],
            suggestions["ambiguo"],
        )
    ]

    result["Motivo da Decisão"] = suggestions[
        "reason_code"
    ]

    # ------------------------------------------------------------
    # 9. Campos de validação do N2
    # ------------------------------------------------------------
    result["Objeto Operacional Validado"] = ""
    result["Classificação Validada"] = ""
    result["Concordância"] = ""

    return result[
        COMPILADO_COLUMNS
        + AIZEN_OUTPUT_COLUMNS
        + VALIDATION_COLUMNS
    ]


def main() -> None:
    references_df = load_references(
        TEMPLATE_PATH
    )

    print(
        f"Referencias carregadas: "
        f"{len(references_df)}"
    )

    monitoramento_df = load_salesforce(
        MONITORAMENTO_PATH
    )

    print(
        f"Chamados carregados: "
        f"{len(monitoramento_df)}"
    )

    n2_df = build_n2_dataframe(
        monitoramento_df,
        references_df,
        load_compilado_sheet(TEMPLATE_PATH),
    )

    suggested = n2_df[
        "Classificação Sugerida"
    ].notna().sum()

    print(
        f"Sugestões geradas: "
        f"{suggested} de {len(n2_df)}"
    )

    generated_file, inserted = export_plano_n2(
        dataframe=n2_df,
        template_path=TEMPLATE_PATH,
        output_path=OUTPUT_PATH,
    )

    print(
        f"Arquivo gerado: "
        f"{generated_file}"
    )

    print(
        f"Novos chamados inseridos: "
        f"{len(inserted)}"
    )

    print(
        "Com sugestão entre os inseridos: "
        f"{inserted['Classificação Sugerida'].notna().sum()}"
    )

    print(
        "Registros no compilado: "
        f"{len(load_compilado_sheet(generated_file))}"
    )


if __name__ == "__main__":
    main()