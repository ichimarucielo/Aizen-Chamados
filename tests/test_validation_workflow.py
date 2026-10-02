from pathlib import Path

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.table import Table, TableColumn

from export import HEADER_ROW, SHEET_NAME, TABLE_NAME, export_plano_n2


def _create_template(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = SHEET_NAME
    worksheet.cell(HEADER_ROW, 1, "Número do Chamado")
    worksheet.cell(HEADER_ROW + 1, 1, "BASE-1")

    table = Table(displayName=TABLE_NAME, ref=f"A{HEADER_ROW}:A{HEADER_ROW + 1}")
    table.tableColumns = [TableColumn(id=1, name="Número do Chamado")]
    worksheet.add_table(table)
    workbook.save(path)


def _incoming_ticket() -> pd.DataFrame:
    return pd.DataFrame([{
        "Número do Chamado": "N2-1001",
        "Causa Identificada": "cancelamento da nf",
        "Causa Raiz Padrão": "Cancelamento de Nota Fiscal",
        "Objeto Operacional Sugerido": "Documento Fiscal",
        "Classificação Sugerida": "Cancelamento e Reemissão de Nota Fiscal",
        "Score Confiança": 0.94,
        "Regra Sugerida": "cancelamento_nf_reemissao",
        "Status da Sugestão": "Sugerida",
        "Ambiguidade": False,
        "Objeto Operacional Validado": "",
        "Classificação Validada": "",
        "Concordância": "",
    }])


def test_validation_survives_reexport_and_agreement_is_formula(tmp_path):
    template_path = tmp_path / "template.xlsx"
    output_path = tmp_path / "output.xlsx"
    _create_template(template_path)

    export_plano_n2(_incoming_ticket(), template_path, output_path)

    workbook = load_workbook(output_path)
    worksheet = workbook[SHEET_NAME]
    headers = {
        worksheet.cell(HEADER_ROW, column).value: column
        for column in range(1, worksheet.max_column + 1)
    }
    ticket_row = next(
        row
        for row in range(HEADER_ROW + 1, worksheet.max_row + 1)
        if worksheet.cell(row, headers["Número do Chamado"]).value == "N2-1001"
    )
    assert worksheet.cell(ticket_row, headers["Causa Identificada"]).value == "cancelamento da nf"
    assert worksheet.cell(
        ticket_row,
        headers["Causa Raiz Padrão"],
    ).value == "Cancelamento de Nota Fiscal"
    worksheet.cell(ticket_row, headers["Objeto Operacional Validado"], "Documento Fiscal")
    worksheet.cell(
        ticket_row,
        headers["Classificação Validada"],
        "Cancelamento e Reemissão de Nota Fiscal",
    )
    workbook.save(output_path)

    export_plano_n2(_incoming_ticket(), template_path, output_path)

    workbook = load_workbook(output_path, data_only=False)
    worksheet = workbook[SHEET_NAME]
    assert worksheet.cell(ticket_row, headers["Objeto Operacional Validado"]).value == "Documento Fiscal"
    assert worksheet.cell(
        ticket_row,
        headers["Classificação Validada"],
    ).value == "Cancelamento e Reemissão de Nota Fiscal"
    assert worksheet.cell(ticket_row, headers["Concordância"]).value.startswith("=IF(")