"""Métricas de validação operacional preenchida pelo N2 no Plano N2."""

import json
from pathlib import Path

import pandas as pd

from extract import load_compilado_sheet


BASE_DIR = Path(__file__).resolve().parent.parent
WORKBOOK_PATH = BASE_DIR / "data" / "output" / "plano_n2_gerado.xlsx"
OUTPUT_PATH = BASE_DIR / "data" / "output" / "validation_analysis.json"

SUGGESTED_CLASS = "Classificação Sugerida"
VALIDATED_CLASS = "Classificação Validada"
CONFIDENCE = "Score Confiança"
RULE = "Regra Sugerida"
SUGGESTION_STATUS = "Status da Sugestão"

CONFIDENCE_BANDS = [
    (0.0, 0.5, "0.00-0.49"),
    (0.5, 0.6, "0.50-0.59"),
    (0.6, 0.7, "0.60-0.69"),
    (0.7, 0.8, "0.70-0.79"),
    (0.8, 0.9, "0.80-0.89"),
    (0.9, 1.000001, "0.90-1.00"),
]


def _clean_text(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def _rate(numerator: int, denominator: int) -> float | None:
    if not denominator:
        return None
    return round(numerator / denominator, 4)


def _confidence_band(value: float) -> str | None:
    for lower, upper, label in CONFIDENCE_BANDS:
        if lower <= value < upper:
            return label
    return None


def evaluate_validations(dataframe: pd.DataFrame) -> dict:
    """Calcula métricas apenas com sugestões e validações efetivamente preenchidas."""

    required = {
        SUGGESTED_CLASS,
        VALIDATED_CLASS,
        CONFIDENCE,
        RULE,
        SUGGESTION_STATUS,
    }
    missing = required.difference(dataframe.columns)
    if missing:
        raise ValueError(f"Colunas de validação ausentes: {sorted(missing)}")

    working = dataframe.copy()
    working[SUGGESTED_CLASS] = _clean_text(working[SUGGESTED_CLASS])
    working[VALIDATED_CLASS] = _clean_text(working[VALIDATED_CLASS])
    working[RULE] = _clean_text(working[RULE]).replace("", "Sem regra registrada")
    working[SUGGESTION_STATUS] = _clean_text(working[SUGGESTION_STATUS])
    working[CONFIDENCE] = pd.to_numeric(working[CONFIDENCE], errors="coerce")

    processed = working[
        working[SUGGESTION_STATUS].isin(
            {"Sugerida", "Ambígua", "Sem correspondência"}
        )
    ].copy()
    suggested = processed[
        (processed[SUGGESTION_STATUS] == "Sugerida")
        & (processed[SUGGESTED_CLASS] != "")
    ].copy()
    validated = suggested[suggested[VALIDATED_CLASS] != ""].copy()
    validated["concordou"] = validated[SUGGESTED_CLASS] == validated[VALIDATED_CLASS]

    labeled = processed[processed[VALIDATED_CLASS] != ""].copy()
    labeled["tem_sugestao"] = labeled[SUGGESTION_STATUS] == "Sugerida"
    coverage_by_validated_class = {}
    for classification, group in labeled.groupby(VALIDATED_CLASS, sort=True):
        covered = group[group["tem_sugestao"]]
        agreements_in_class = int(
            (covered[SUGGESTED_CLASS] == classification).sum()
        )
        coverage_by_validated_class[classification] = {
            "rotulados_pelo_n2": int(len(group)),
            "com_sugestao": int(len(covered)),
            "cobertura": _rate(len(covered), len(group)),
            "concordancias": agreements_in_class,
            "concordancia_das_sugestoes": _rate(
                agreements_in_class,
                len(covered),
            ),
        }

    precision_by_class = {}
    for classification, group in suggested.groupby(SUGGESTED_CLASS, sort=True):
        reviewed = validated[validated[SUGGESTED_CLASS] == classification]
        agreed = int(reviewed["concordou"].sum())
        precision_by_class[classification] = {
            "sugestoes": int(len(group)),
            "validadas": int(len(reviewed)),
            "concordancias": agreed,
            "concordancia": _rate(agreed, len(reviewed)),
        }

    confidence_vs_accuracy = {}
    confidence_validated = validated[validated[CONFIDENCE].between(0, 1)].copy()
    confidence_validated["faixa"] = confidence_validated[CONFIDENCE].map(
        _confidence_band
    )
    for _, _, label in CONFIDENCE_BANDS:
        group = confidence_validated[confidence_validated["faixa"] == label]
        agreed = int(group["concordou"].sum())
        confidence_vs_accuracy[label] = {
            "validadas": int(len(group)),
            "concordancias": agreed,
            "concordancia": _rate(agreed, len(group)),
        }

    errors_by_rule = {}
    for rule, group in validated.groupby(RULE, sort=True):
        errors = int((~group["concordou"]).sum())
        errors_by_rule[rule] = {
            "validadas": int(len(group)),
            "erros": errors,
            "concordancias": int(group["concordou"].sum()),
            "concordancia": _rate(int(group["concordou"].sum()), len(group)),
        }

    agreements = int(validated["concordou"].sum())
    ambiguous = int((processed[SUGGESTION_STATUS] == "Ambígua").sum())
    return {
        "total_chamados": int(len(processed)),
        "linhas_nao_avaliadas": int(len(working) - len(processed)),
        "sugestoes": int(len(suggested)),
        "cobertura": _rate(len(suggested), len(processed)),
        "ambiguos": ambiguous,
        "taxa_ambiguidade": _rate(ambiguous, len(processed)),
        "validacoes": int(len(validated)),
        "concordancias": agreements,
        "discordancias": int(len(validated) - agreements),
        "concordancia_classificacao": _rate(agreements, len(validated)),
        "cobertura_por_classificacao_validada": coverage_by_validated_class,
        "precisao_por_classificacao": precision_by_class,
        "confianca_por_faixa": confidence_vs_accuracy,
        "erros_por_regra": errors_by_rule,
    }


def main() -> None:
    if not WORKBOOK_PATH.exists():
        raise FileNotFoundError(
            f"Planilha gerada não encontrada: {WORKBOOK_PATH}. Execute src/main.py primeiro."
        )

    metrics = evaluate_validations(load_compilado_sheet(WORKBOOK_PATH))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Chamados: {metrics['total_chamados']}")
    print(f"Cobertura: {metrics['cobertura']}")
    print(f"Ambiguidade: {metrics['ambiguos']} ({metrics['taxa_ambiguidade']})")
    print(
        "Concordância de classificação: "
        f"{metrics['concordancias']}/{metrics['validacoes']} "
        f"({metrics['concordancia_classificacao']})"
    )
    print(f"Análise salva: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()