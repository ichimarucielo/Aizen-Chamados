"""Mede a decisao operacional historica do N2 por causa raiz.

Somente frequencia: nao preve, nao decide e nao atribui responsavel.
"""

from collections import Counter
from pathlib import Path
import json

import pandas as pd

from extract import load_compilado_sheet


BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = BASE_DIR / "data" / "input" / "plano_n2_template.xlsx"
OUTPUT_PATH = BASE_DIR / "data" / "output" / "decisao_analise.json"

ROOT_CAUSE = "Causa raiz"
DECISION_FIELDS = {
    "classificacao": "Classificação",
    "ofensor": "Ofensor",
    "prioridade": "Prioridade",
    "responsavel": "RESPONSÁVEL",
}
TOP_N = 20
MIN_SAMPLE = 5


def confidence_level(confidence: float, sample: int) -> str:
    if sample < MIN_SAMPLE:
        return "AMOSTRA INSUFICIENTE"
    if confidence >= 0.90:
        return "MUITO ALTA"
    if confidence >= 0.75:
        return "ALTA"
    if confidence >= 0.60:
        return "MEDIA"
    return "BAIXA"


def _clean(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def dominant_value(values: pd.Series, total_records: int) -> dict:
    """Valor mais frequente; confianca = mais_frequente / preenchidos."""

    filled = values[values != ""]
    if filled.empty:
        return {
            "valor": None,
            "confianca": 0.0,
            "nivel": confidence_level(0.0, 0),
            "preenchidos": 0,
            "cobertura": 0.0,
            "distribuicao": {},
        }

    counts = Counter(filled)
    value, top_count = counts.most_common(1)[0]
    confidence = top_count / len(filled)

    return {
        "valor": value,
        "confianca": round(confidence, 3),
        "nivel": confidence_level(confidence, len(filled)),
        "preenchidos": int(len(filled)),
        "cobertura": round(len(filled) / total_records, 3),
        "distribuicao": dict(counts.most_common()),
    }


def analyze_decisions(dataframe: pd.DataFrame) -> dict:
    required = {ROOT_CAUSE, *DECISION_FIELDS.values()}
    missing = required.difference(dataframe.columns)
    if missing:
        raise ValueError(f"Colunas obrigatorias ausentes: {sorted(missing)}")

    working = dataframe[list(required)].copy()
    for column in required:
        working[column] = _clean(working[column])
    working = working[working[ROOT_CAUSE] != ""]

    # Variacoes apenas de caixa/espacos (ex.: "Cancelamento de nf") viram um grupo.
    working["_chave"] = working[ROOT_CAUSE].str.casefold()

    causes = {}
    for _, group in working.groupby("_chave", sort=False):
        label = group[ROOT_CAUSE].value_counts().index[0]
        entry = {
            "causa_raiz": label,
            "ocorrencias": int(len(group)),
        }
        for key, column in DECISION_FIELDS.items():
            entry[key] = dominant_value(group[column], len(group))
        causes[label] = entry

    ranked = sorted(
        causes.values(),
        key=lambda item: (-item["ocorrencias"], item["causa_raiz"]),
    )

    return {
        "registros_historicos": int(len(dataframe)),
        "registros_com_causa_raiz": int(len(working)),
        "causas_raiz_distintas": len(causes),
        "classificacoes": classification_report(working),
        "causas_raiz": {item["causa_raiz"]: item for item in ranked},
        "top_20": [_executive_row(item) for item in ranked[:TOP_N]],
    }


def classification_report(working: pd.DataFrame) -> dict:
    """Para cada classificacao: quais causas raiz ela absorve e quantas vezes."""

    labeled = working[working["Classificação"] != ""]
    report = {}
    for classification, group in labeled.groupby("Classificação"):
        causes = [
            {
                "causa_raiz": subgroup[ROOT_CAUSE].value_counts().index[0],
                "ocorrencias": int(len(subgroup)),
            }
            for _, subgroup in group.groupby("_chave")
        ]
        causes.sort(key=lambda item: (-item["ocorrencias"], item["causa_raiz"]))
        report[classification] = {
            "ocorrencias": int(len(group)),
            "causas_distintas": len(causes),
            "causas": causes,
        }

    conflicts = (
        labeled.groupby("_chave")["Classificação"].nunique().loc[lambda s: s > 1]
    )
    return {
        "por_classificacao": dict(
            sorted(report.items(), key=lambda kv: -kv[1]["ocorrencias"])
        ),
        "causas_em_mais_de_uma_classificacao": sorted(conflicts.index),
        "sem_classificacao": sorted(
            working.loc[working["Classificação"] == "", ROOT_CAUSE].unique()
        ),
    }


def print_classification_report(analysis: dict) -> None:
    report = analysis["classificacoes"]
    print("\nCLASSIFICACAO -> CAUSAS RAIZ")
    print("=" * 100)
    for name, data in report["por_classificacao"].items():
        print(f"\n{name}: {data['ocorrencias']} chamados, "
              f"{data['causas_distintas']} causas distintas")
        for cause in data["causas"][:8]:
            print(f"  {cause['ocorrencias']:>4}  {cause['causa_raiz']}")
        if data["causas_distintas"] > 8:
            print(f"  ... +{data['causas_distintas'] - 8} causas (ver JSON)")
    print(f"\nCausas em mais de uma classificacao: "
          f"{len(report['causas_em_mais_de_uma_classificacao'])}")
    print(f"Causas sem classificacao: {report['sem_classificacao']}")


def _executive_row(item: dict) -> dict:
    return {
        "causa_raiz": item["causa_raiz"],
        "ocorrencias": item["ocorrencias"],
        "classificacao": item["classificacao"]["valor"],
        "classificacao_confianca": item["classificacao"]["confianca"],
        "ofensor": item["ofensor"]["valor"],
        "ofensor_confianca": item["ofensor"]["confianca"],
        "ofensor_cobertura": item["ofensor"]["cobertura"],
        "responsavel": item["responsavel"]["valor"],
        "prioridade": item["prioridade"]["valor"],
    }


def describe(item: dict) -> str:
    """Frase no formato: historicamente, quando a causa raiz foi X, ..."""

    parts = [
        f"Historicamente, quando a causa raiz foi '{item['causa_raiz']}' "
        f"({item['ocorrencias']} ocorrencias):"
    ]
    for key in ("classificacao", "ofensor", "prioridade"):
        data = item[key]
        if data["valor"] is None:
            parts.append(f"  {key}: sem dados historicos")
            continue
        parts.append(
            f"  {key}: {data['valor']} - {data['confianca']:.1%} "
            f"({data['nivel']}, {data['preenchidos']}/{item['ocorrencias']} preenchidos)"
        )
    return "\n".join(parts)


def print_executive_report(analysis: dict) -> None:
    print(f"\nTOP {TOP_N} causas raiz")
    print("=" * 100)
    for position, row in enumerate(analysis["top_20"], start=1):
        item = analysis["causas_raiz"][row["causa_raiz"]]
        print(
            f"{position:>2}. {row['causa_raiz']} ({row['ocorrencias']})\n"
            f"    Classificacao: {row['classificacao']} "
            f"[{row['classificacao_confianca']:.1%} "
            f"{item['classificacao']['nivel']}]\n"
            f"    Ofensor: {row['ofensor'] or 'sem dados'} "
            f"[{row['ofensor_confianca']:.1%} {item['ofensor']['nivel']}, "
            f"cobertura {row['ofensor_cobertura']:.0%}]\n"
            f"    Prioridade: {row['prioridade']} | "
            f"Responsavel (so analise): {row['responsavel']}"
        )


def main() -> None:
    dataframe = load_compilado_sheet(TEMPLATE_PATH)
    analysis = analyze_decisions(dataframe)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Historicos: {analysis['registros_historicos']}")
    print(f"Com causa raiz: {analysis['registros_com_causa_raiz']}")
    print(f"Causas distintas (sem variacao de caixa): {analysis['causas_raiz_distintas']}")
    print(f"Analise gerada: {OUTPUT_PATH}")
    print_executive_report(analysis)
    print_classification_report(analysis)

    first = analysis["top_20"][0]["causa_raiz"]
    print("\nExemplo:")
    print(describe(analysis["causas_raiz"][first]))


if __name__ == "__main__":
    main()
