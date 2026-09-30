from pathlib import Path

from export import create_output_copy

from extract import (
    load_salesforce,
    load_references,
    load_compilado_sheet,
)

from parse_description import (
    normalize_description,
    extract_cnpj,
    extract_email,
    extract_phone,
    parse_description,
)

from lookup import (
    build_razao_social_lookup,
    lookup_razao_social,
)

from business_rules import (
    apply_situacao,
    apply_dias_aberto,
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

OUTPUT_PATH = (
    BASE_DIR
    / "data"
    / "output"
    / "plano_n2_gerado.xlsx"
)


def main() -> None:
    generated_file = create_output_copy(
        template_path=TEMPLATE_PATH,
        output_path=OUTPUT_PATH,
    )

    print(f"Arquivo gerado: {generated_file}")

    references_df = load_references(
        TEMPLATE_PATH
    )

    print(
        f"Referencias carregadas: {len(references_df)}"
    )

    monitoramento_df = load_salesforce(
        MONITORAMENTO_PATH
    )

    print(
        f"Chamados carregados: {len(monitoramento_df)}"
    )

    monitoramento_df["CNPJ"] = extract_cnpj(
        monitoramento_df["Descrição"]
    )

    monitoramento_df["EMAIL_EXTRAIDO"] = extract_email(
        monitoramento_df["Descrição"]
    )

    monitoramento_df["TELEFONE"] = extract_phone(
        monitoramento_df["Descrição"]
    )

    monitoramento_df["DESCRICAO_NORMALIZADA"] = (
        monitoramento_df["Descrição"]
        .fillna("")
        .astype(str)
        .apply(normalize_description)
    )

    razao_social_lookup = (
        build_razao_social_lookup(
            references_df
        )
    )

    monitoramento_df["RAZAO_SOCIAL"] = (
        monitoramento_df["CNPJ"]
        .apply(
            lambda x: lookup_razao_social(
                x,
                razao_social_lookup,
            )
        )
    )

    n2_df = monitoramento_df[
    [
        "Número do Chamado",
        "Número de Chamado Pai",
        "Número Protocolo",
        "RAZAO_SOCIAL",
        "CNPJ",
        "Assunto",
        "Data de abertura",
        "Data da última modificação do chamado",
        "Proprietário do Chamado",
        "Email da Web",
        "Nome Fantasia",
        "DESCRICAO_NORMALIZADA",
    ]
].copy()

    n2_df["Situação"] = (
    monitoramento_df["Status"]
    .apply(apply_situacao)
    )

    n2_df["Dias em Aberto"] = (
        monitoramento_df["Data de abertura"]
        .apply(apply_dias_aberto)
    )

    n2_df = n2_df.rename(
    columns={
        "Número do Chamado": "Número do Chamado",
        "Número de Chamado Pai": "Chamado Pai (clone)",
        "Número Protocolo": "Número de protocolo",
        "RAZAO_SOCIAL": "Razão social",
        "CNPJ": "CNPJ",
        "Assunto": "Assunto",
        "Data de abertura": "Data de abertura",
        "Data da última modificação do chamado":
            "Data da última modificação do chamado",
        "Proprietário do Chamado":
            "Proprietário do Chamado",
        "Email da Web": "Email da Web",
        "Nome Fantasia": "Nome Fantasia",
        "DESCRICAO_NORMALIZADA":
            "Descrição detalhada",
    }
)
    print("\nN2 PREVIEW")
    print("=" * 100)

    print(
        n2_df.head(5)
    )


    print(
        monitoramento_df[
            [
                "Número do Chamado",
                "CNPJ",
                "RAZAO_SOCIAL",
            ]
        ].head(10)
    )

    dados = parse_description(
        monitoramento_df.loc[0, "Descrição"]
    )

    print("\nCAMPOS EXTRAIDOS")
    print("=" * 100)

    for chave, valor in dados.items():
        print(f"{chave}:")
        print(valor)
        print()


    compilado_df = load_compilado_sheet(
        TEMPLATE_PATH
    )

    print("\nCOMPILADO")
    print("=" * 100)

    print(
        f"Registros: {len(compilado_df)}"
    )

    print(
        compilado_df.columns.tolist()
    )

if __name__ == "__main__":
    main()