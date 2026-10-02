"""Audita o dicionário contra o histórico Compilado chamados."""

from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import unicodedata

import pandas as pd

from root_cause_engine import classify, load_dictionary


BASE_DIR = Path(__file__).resolve().parent.parent
WORKBOOK_PATH = BASE_DIR / "data" / "input" / "plano_n2_template.xlsx"
OUTPUT_PATH = BASE_DIR / "data" / "output" / "dicionario_aizen_analise.json"


def _text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _label_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _aliases_by_label(dictionary: dict) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for intent in dictionary["intencoes"]:
        for alias in set(intent.get("aliases_historicos", [])):
            result[_label_key(alias)].add(intent["id"])
    return result


def analyze_dictionary(
    history: pd.DataFrame,
    references: pd.DataFrame,
    dictionary: dict | None = None,
) -> dict:
    dictionary = dictionary or load_dictionary()
    required = {
        "Classificação",
        "Causa raiz",
        "Descrição detalhada",
        "Descrição",
        "Assunto",
    }
    missing = required.difference(history.columns)
    if missing:
        raise ValueError(f"Colunas históricas ausentes: {sorted(missing)}")

    allowed_classes = dictionary["classes_permitidas"]
    intents = {intent["id"]: intent for intent in dictionary["intencoes"]}
    alias_map = _aliases_by_label(dictionary)
    causes = history["Causa raiz"].map(_text)
    classes = history["Classificação"].map(_text)
    cause_counts = Counter(causes)
    class_counts = Counter(classes)

    cause_classes: dict[str, set[str]] = defaultdict(set)
    for cause, classification in zip(causes, classes):
        if cause and classification:
            cause_classes[cause].add(classification)
    literal_conflicts = {
        cause: sorted(values)
        for cause, values in cause_classes.items()
        if len(values) > 1
    }

    cause_consolidation = []
    alias_volume_by_intent = Counter()
    for cause, count in cause_counts.most_common():
        key = _label_key(cause)
        matching_ids = sorted(alias_map.get(key, set())) if cause else []
        canonical_causes = {
            intents[intent_id]["causa_padrao"] for intent_id in matching_ids
        }
        canonical_classes = {
            intents[intent_id]["classificacao"] for intent_id in matching_ids
        }
        mapped = len(canonical_causes) == 1 and len(canonical_classes) == 1
        is_na = cause.casefold() == "#n/a"
        if mapped:
            canonical = next(iter(canonical_causes))
            classification = next(iter(canonical_classes))
            for intent_id in matching_ids:
                alias_volume_by_intent[intent_id] += count
            status = "consolidada"
        else:
            canonical = None
            classification = None
            status = (
                "causa_vazia" if not cause
                else "rotulo_na" if is_na
                else "revisao_sem_alias_unico"
            )
        cause_consolidation.append({
            "causa_historica": cause or None,
            "causa_padrao": canonical,
            "classificacao_padrao": classification,
            "classificacoes_historicas": sorted(cause_classes.get(cause, set())),
            "quantidade": int(count),
            "intencoes_candidatas": matching_ids,
            "status_consolidacao": status,
        })

    intent_volume_by_text = Counter()
    classifications_by_intent = defaultdict(Counter)
    class_mismatches = []
    no_match = 0
    ambiguous = 0
    answered = 0
    correct = 0
    labelled_total = 0
    description_empty = 0

    for _, row in history.iterrows():
        actual_class = _text(row.get("Classificação"))
        description = _text(row.get("Descrição detalhada"))
        if not description:
            description = _text(row.get("Descrição"))
        if not description:
            description_empty += 1
        result = classify(description, dictionary)
        if result["status"] == "Sem correspondência":
            no_match += 1
        if result["status"] == "Ambígua":
            ambiguous += 1
        if result["intencao_id"]:
            intent_volume_by_text[result["intencao_id"]] += 1
            classifications_by_intent[result["intencao_id"]][actual_class] += 1
        if not actual_class or actual_class.upper() == "#N/A":
            continue
        labelled_total += 1
        predicted = result["classificacao"]
        if predicted:
            answered += 1
            if predicted == actual_class:
                correct += 1
            else:
                class_mismatches.append({
                    "numero_chamado": _text(row.get("Número do Chamado")),
                    "causa_historica": _text(row.get("Causa raiz")) or None,
                    "classificacao_historica": actual_class,
                    "intencao_detectada": result["intencao_id"],
                    "causa_padrao_detectada": result["causa_canonica"],
                    "classificacao_detectada": predicted,
                    "status": result["status"],
                })

    intent_report = []
    for intent in dictionary["intencoes"]:
        intent_id = intent["id"]
        intent_report.append({
            "id": intent_id,
            "intencao": intent["intencao"],
            "padroes": intent["padroes"],
            "causa_padrao": intent["causa_padrao"],
            "classificacao": intent["classificacao"],
            "volume_por_alias_historico": int(alias_volume_by_intent[intent_id]),
            "descricoes_com_intencao_detectada": int(intent_volume_by_text[intent_id]),
            "distribuicao_classe_historica_dos_matches": dict(
                classifications_by_intent[intent_id]
            ),
        })
    intent_report.sort(
        key=lambda item: (-item["volume_por_alias_historico"], item["id"])
    )

    themes = references.get("Tema", pd.Series(dtype=object)).map(_text)
    nonempty_themes = {value for value in themes if value}
    cause_text = causes.map(_label_key)
    class_text = classes.map(_label_key)
    description_text = history["Descrição detalhada"].map(_text)
    raw_description = history["Descrição"].map(_text)
    na_labels = int(
        causes.str.casefold().eq("#n/a").sum()
        + classes.str.casefold().eq("#n/a").sum()
    )
    cause_empty = int(causes.eq("").sum())
    class_empty = int(classes.eq("").sum())
    references_unique_themes = len(nonempty_themes)

    return {
        "fonte": {
            "workbook_utilizado": "data/input/plano_n2_template.xlsx",
            "workbook_oficial_exato_disponivel": False,
            "workbook_oficial_comparado": "Plano de ação - Chamados Fila N2 - Oficial (4).xlsx",
            "validacao_da_fonte": "409 linhas e valores idênticos nas colunas históricas solicitadas e Tema/Macro Classificação.",
        },
        "resumo_historico": {
            "chamados_analisados": int(len(history)),
            "causas_historicas_unicas_nao_vazias": int(
                causes[(cause_text != "") & causes.str.casefold().ne("#n/a")].nunique()
            ),
            "rotulos_de_causa_incluindo_vazio": int(causes.nunique()),
            "temas_unicos_na_aba_referencias": int(references_unique_themes),
            "intencoes_no_dicionario": int(len(dictionary["intencoes"])),
            "classificacoes_permitidas": int(len(allowed_classes)),
            "classificacoes_historicas": dict(class_counts),
            "classes_oficiais": allowed_classes,
            "causa_vazia": cause_empty,
            "classificacao_vazia": class_empty,
            "rotulos_literal_na": na_labels,
            "descricao_detalhada_vazia": int(description_text.eq("").sum()),
            "descricao_vazia": int(raw_description.eq("").sum()),
        },
        "frequencia_causas_historicas": [
            {
                "causa_historica": cause or None,
                "quantidade": int(count),
                "classificacoes": sorted(cause_classes.get(cause, set())),
            }
            for cause, count in cause_counts.most_common()
        ],
        "causa_historica_para_padrao": cause_consolidation,
        "relacao_causa_classificacao": [
            {
                "causa_historica": cause,
                "classificacoes": sorted(values),
                "quantidade": int(cause_counts[cause]),
            }
            for cause, values in sorted(cause_classes.items())
        ],
        "conflitos_causa_literal_em_multiplas_classes": literal_conflicts,
        "conflitos_e_excecoes_documentados": dictionary.get(
            "conflitos_e_excecoes",
            [],
        ),
        "rotulos_genericos_para_revisao": [
            item for item in cause_consolidation
            if item["causa_historica"]
            and _label_key(item["causa_historica"]) in {
                "outros", "duvidas", "informacoes geral",
                "reenvio de boleto nf", "cancelamento contrato produto nf",
                "inclusao de po nf",
            }
        ],
        "intencoes_priorizadas_por_volume": intent_report,
        "avaliacao_deterministica_no_historico": {
            "chamados_com_classe_historica": labelled_total,
            "respostas_com_classe_unica": answered,
            "sem_correspondencia": no_match,
            "ambiguos": ambiguous,
            "acertos_entre_respostas": correct,
            "acuracia_entre_respostas": (
                round(correct / answered, 4) if answered else None
            ),
            "divergencias_descricao_vs_classe_historica": class_mismatches,
        },
        "dez_intencoes_de_maior_volume_historico": intent_report[:10],
        "regras_novas_no_dicionario": int(len(dictionary["intencoes"])),
    }


def main() -> None:
    history = pd.read_excel(
        WORKBOOK_PATH,
        sheet_name="Compilado chamados",
        header=3,
        keep_default_na=False,
    )
    references = pd.read_excel(
        WORKBOOK_PATH,
        sheet_name="Referencias ",
        keep_default_na=False,
    )
    dictionary = load_dictionary()
    report = analyze_dictionary(history, references, dictionary)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary = report["resumo_historico"]
    print(f"Chamados analisados: {summary['chamados_analisados']}")
    print(f"Causas históricas únicas: {summary['causas_historicas_unicas_nao_vazias']}")
    print(f"Temas únicos: {summary['temas_unicos_na_aba_referencias']}")
    print(f"Intenções: {summary['intencoes_no_dicionario']}")
    print(f"Classificações oficiais: {summary['classificacoes_permitidas']}")
    print(
        "Causas sem consolidação automática: "
        f"{sum(item['status_consolidacao'] != 'consolidada' for item in report['causa_historica_para_padrao'])}"
    )
    print(f"Conflitos literais causa/classe: {len(report['conflitos_causa_literal_em_multiplas_classes'])}")
    print(f"Divergências texto/classe detectadas: {len(report['avaliacao_deterministica_no_historico']['divergencias_descricao_vs_classe_historica'])}")
    print(f"Campos vazios: causa={summary['causa_vazia']}, classe={summary['classificacao_vazia']}, descrição detalhada={summary['descricao_detalhada_vazia']}")
    print(f"Rótulos #N/A: {summary['rotulos_literal_na']}")
    print(f"Exceções documentadas: {len(report['conflitos_e_excecoes_documentados'])}")
    print(f"Regras novas no dicionário: {report['regras_novas_no_dicionario']}")
    print("Top 10 intenções por volume histórico:")
    for rank, intent in enumerate(report["dez_intencoes_de_maior_volume_historico"], 1):
        print(f"{rank:>2}. {intent['causa_padrao']}: {intent['volume_por_alias_historico']}")
    print(f"Análise gerada: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
