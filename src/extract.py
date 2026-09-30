from pathlib import Path
import pandas as pd


HEADER_COLUMN = "Número do Chamado"


def find_header_row(file_path: Path) -> int:
    """
    Localiza a linha onde começa a tabela do Salesforce.
    """
    preview = pd.read_excel(
        file_path,
        header=None,
    )

    for idx, row in preview.iterrows():
        values = row.astype(str)
        if values.str.contains(
            HEADER_COLUMN,
            case=False,
            na=False,
        ).any():
            return idx
 


    raise ValueError(
        f"Cabeçalho '{HEADER_COLUMN}' não encontrado."
    )



def load_salesforce(
    file_path: Path,
) -> pd.DataFrame:
    """
    Carrega o relatório do Salesforce.
    """

    header_row = find_header_row(file_path)

    df = pd.read_excel(
        file_path,
        header=header_row,
    )

    df = df.loc[
        :,
        ~df.columns.astype(str).str.startswith("Unnamed")
    ]

    return df

def load_references(
    file_path: Path,
) -> pd.DataFrame:
    """
    Carrega a aba Referencias do Plano N2.
    """

    return pd.read_excel(
        file_path,
        sheet_name="Referencias "
    )

def load_compilado_sheet(
    file_path: Path,
) -> pd.DataFrame:
    """
    Carrega Compilado chamados.
    """

    return pd.read_excel(
        file_path,
        sheet_name="Compilado chamados",
        header=3,
    )