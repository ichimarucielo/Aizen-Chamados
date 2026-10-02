from pathlib import Path
from shutil import copy2
from copy import copy

from openpyxl import load_workbook
from openpyxl.formula.translate import Translator
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries
from openpyxl.worksheet.table import TableColumn
import pandas as pd


SHEET_NAME = "Compilado chamados"
TABLE_NAME = "Tabela2"
HEADER_ROW = 4
SUGGESTION_COLUMNS = [
    "Intenção Identificada",
    "Causa Identificada",
    "Causa Raiz Padrão",
    "Objeto Operacional Sugerido",
    "Classificação Sugerida",
    "Score Confiança",
]
TRACKING_COLUMNS = [
    "Regra Sugerida",
    "Status da Sugestão",
    "Ambiguidade",
]
VALIDATION_COLUMNS = [
    "Objeto Operacional Validado",
    "Classificação Validada",
    "Concordância",
]


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


def _resize_table(worksheet, last_row: int | None = None) -> None:
    table = worksheet.tables[TABLE_NAME]
    min_col, min_row, _, max_row = range_boundaries(table.ref)
    ref = (
        f"{get_column_letter(min_col)}{min_row}:"
        f"{get_column_letter(worksheet.max_column)}{last_row or max_row}"
    )
    table.ref = ref
    if table.autoFilter is not None:
        table.autoFilter.ref = ref


def _ensure_columns(worksheet, names: list[str]) -> None:
    """Cria colunas de sugestao ao lado da ultima e as inclui na tabela."""

    table = worksheet.tables[TABLE_NAME]
    existing = {
        worksheet.cell(HEADER_ROW, column).value
        for column in range(1, worksheet.max_column + 1)
    }
    for name in names:
        if name in existing:
            continue

        column = worksheet.max_column + 1
        header = worksheet.cell(HEADER_ROW, column, name)
        previous = worksheet.cell(HEADER_ROW, column - 1)
        if previous.has_style:
            header._style = copy(previous._style)
        worksheet.column_dimensions[get_column_letter(column)].width = 34

        table.tableColumns.append(
            TableColumn(id=len(table.tableColumns) + 1, name=name)
        )

    _resize_table(worksheet)


def _write_agreement_formulas(worksheet, headers: dict[str, int], last_row: int) -> None:
    suggested_column = get_column_letter(headers["Classificação Sugerida"])
    validated_column = get_column_letter(headers["Classificação Validada"])
    agreement_column = headers["Concordância"]

    for row in range(HEADER_ROW + 1, last_row + 1):
        worksheet.cell(row, agreement_column).value = (
            f'=IF(OR({suggested_column}{row}="",{validated_column}{row}=""),'
            f'"",IF({suggested_column}{row}={validated_column}{row},"SIM","NÃO"))'
        )


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
) -> tuple[Path, pd.DataFrame]:
    """Copia o template e acrescenta apenas chamados ainda inexistentes."""

    if not output_path.exists():
        create_output_copy(template_path, output_path)

    workbook = load_workbook(output_path)
    worksheet = workbook[SHEET_NAME]

    _ensure_columns(
        worksheet,
        SUGGESTION_COLUMNS + TRACKING_COLUMNS + VALIDATION_COLUMNS,
    )
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

    last_row = max(source_row, next_row + len(new_rows) - 1)
    _resize_table(worksheet, last_row)
    _write_agreement_formulas(worksheet, headers, last_row)

    workbook.save(output_path)
    return output_path, new_rows
