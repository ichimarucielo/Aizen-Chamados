from pathlib import Path
from shutil import copy2
from copy import copy

from openpyxl import load_workbook
from openpyxl.formula.translate import Translator
import pandas as pd


SHEET_NAME = "Compilado chamados"
HEADER_ROW = 4


def _normalize_id(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().split(".")[0]


def _copy_row_format_and_formulas(
    worksheet,
    source_row: int,
    target_row: int,
) -> None:
    for column in range(1, worksheet.max_column + 1):
        source = worksheet.cell(source_row, column)
        target = worksheet.cell(target_row, column)

        if source.has_style:
            target._style = copy(source._style)
        target.number_format = source.number_format

        if isinstance(source.value, str) and source.value.startswith("="):
            target.value = Translator(
                source.value,
                origin=source.coordinate,
            ).translate_formula(target.coordinate)


def _find_last_ticket_row(
    worksheet,
    ticket_column: int,
) -> int:
    for row in range(worksheet.max_row, HEADER_ROW, -1):
        value = worksheet.cell(row, ticket_column).value
        if _normalize_id(value):
            return row

    return HEADER_ROW


def create_output_copy(
    template_path: Path,
    output_path: Path,
) -> Path:
    """
    Cria uma cópia do template do Plano N2.
    """

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    copy2(
        src=template_path,
        dst=output_path,
    )

    return output_path


def export_plano_n2(
    dataframe: pd.DataFrame,
    template_path: Path,
    output_path: Path,
) -> tuple[Path, int]:
    """Copia o template e acrescenta apenas chamados ainda inexistentes."""

    create_output_copy(template_path, output_path)

    workbook = load_workbook(output_path)
    worksheet = workbook[SHEET_NAME]

    headers = {
        worksheet.cell(HEADER_ROW, column).value: column
        for column in range(1, worksheet.max_column + 1)
    }
    ticket_column = headers["Número do Chamado"]
    existing_ids = {
        _normalize_id(worksheet.cell(row, ticket_column).value)
        for row in range(HEADER_ROW + 1, worksheet.max_row + 1)
    }

    new_rows = dataframe[
        ~dataframe["Número do Chamado"].map(_normalize_id).isin(existing_ids)
    ].copy()

    source_row = _find_last_ticket_row(worksheet, ticket_column)
    next_row = source_row + 1

    for row_offset, (_, row) in enumerate(new_rows.iterrows()):
        target_row = next_row + row_offset
        _copy_row_format_and_formulas(
            worksheet,
            source_row=source_row,
            target_row=target_row,
        )

        for column_name, column in headers.items():
            if column_name in new_rows.columns:
                worksheet.cell(target_row, column, row[column_name])

        _copy_row_format_and_formulas(
            worksheet,
            source_row=source_row,
            target_row=target_row,
        )

    workbook.save(output_path)
    return output_path, len(new_rows)
