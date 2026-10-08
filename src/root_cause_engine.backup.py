"""Motor MVP do AIZEN: texto -> causa raiz -> uma das seis classificacoes."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import unicodedata

import pandas as pd
import yaml

from parse_description import normalize_description


BASE_DIR = Path(__file__).resolve().parent.parent
DICTIONARY_PATH = BASE_DIR / "data" / "input" / "dicionario_aizen_intencoes.yaml"
TAXONOMY_PATH = BASE_DIR / "data" / "input" / "causa_raiz_taxonomia.yaml"
TEMPLATE_PATH = BASE_DIR / "data" / "input" / "plano_n2_template.xlsx"

STATUS_SUGGESTED = "Sugerida"
STATUS_UNMATCHED = "Sem correspondencia"
STATUS_AMBIGUOUS = "Ambigua"

REASON_CLASSIFIED = "CLASSIFIED"
REASON_EMPTY_TEXT = "EMPTY_TEXT"
REASON_NO_PATTERN = "NO_PATTERN"
REASON_AMBIGUOUS = "AMBIGUOUS_CAUSE"
REASON_NO_CLASS = "CAUSE_WITHOUT_CLASS"

FORM_BOILERPLATE_PATTERNS = (
    r"\bdesejo falar com o setor financeiro\b",
    r"\bsobre qual produto ou area deseja falar\b",
    r"\bcomo podemos te ajudar\b",
    r"\btransferir (?:o )?chamado para o financeiro\b",
    r"\btransferir (?:o )?chamado para o n2\b",
    r"\bdemanda precisa ser tratada pelo n2\b",
    r"\bencaminhar (?:o )?chamado para o financeiro\b",
    r"\bencaminhar (?:o )?chamado para o n2\b",
)


def normalize_text(value) -> str:
    """Normaliza texto para correspondencia deterministica."""
    if pd.isna(value):
        return ""

    text = normalize_description(str(value)).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[\w.+-]+@[\w.-]+\.\w+", " email ", text)
    text = re.sub(r"\bnotas?\s+fisc(?:al|ais)\b|\bnf'?s\b|\bnfs\b", " nf ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def prepare_classification_text(value) -> str:
    """Remove ruido estrutural do formulario."""
    text = normalize_text(value)
    for pattern in FORM_BOILERPLATE_PATTERNS:
        text = re.sub(pattern, " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _load_yaml(path: Path) -> dict:
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    return content or {}


def load_dictionary(path: Path = DICTIONARY_PATH) -> dict:
    dictionary = _load_yaml(path)
    required = {"classes_permitidas", "intencoes"}
    missing = required.difference(dictionary)
    if missing:
        raise ValueError(f"Secoes ausentes no dicionario: {sorted(missing)}")
    return dictionary


def load_taxonomy(path: Path = DICTIONARY_PATH) -> dict[str, str]:
    return {
        str(item["causa_padrao"]).strip(): str(item["classificacao"]).strip()
        for item in load_dictionary(path)["intencoes"]
        if item.get("causa_padrao") and item.get("classificacao")
    }


def load_objects(path: Path = TAXONOMY_PATH) -> dict:
    if not path.exists():
        return {}
    return _load_yaml(path).get("objetos_operacionais", {})


def load_rules(path: Path = DICTIONARY_PATH, include_draft: bool = False) -> dict:
    del include_draft
    return {
        item["id"]: item
        for item in load_dictionary(path)["intencoes"]
        if item.get("id")
    }


def validate_dictionary(dictionary: dict | None = None) -> list[str]:
    dictionary = dictionary or load_dictionary()
    allowed = set(dictionary.get("classes_permitidas", []))
    problems: list[str] = []
    seen: set[str] = set()

    for item in dictionary.get("intencoes", []):
        intent_id = str(item.get("id") or "").strip()
        if not intent_id:
            problems.append("Intencao sem id")
        elif intent_id in seen:
            problems.append(f"ID duplicado: {intent_id}")
        seen.add(intent_id)

        if not item.get("causa_padrao"):
            problems.append(f"Intencao sem causa_padrao: {intent_id}")
        if item.get("classificacao") not in allowed:
            problems.append(f"Classe invalida: {intent_id}")
        if not item.get("padroes"):
            problems.append(f"Intencao sem padroes: {intent_id}")

    return sorted(set(problems))


def _clean(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def build_class_by_cause(history: pd.DataFrame | None, dictionary: dict) -> dict[str, str]:
    """Deriva causa -> classe pela moda historica; usa YAML como fallback."""
    fallback = {
        _clean(item.get("causa_padrao")): _clean(item.get("classificacao"))
        for item in dictionary.get("intencoes", [])
        if _clean(item.get("causa_padrao")) and _clean(item.get("classificacao"))
    }

    if history is None or history.empty:
        return fallback
    if not {"Causa raiz", "Classificação"}.issubset(history.columns):
        return fallback

    valid = history[["Causa raiz", "Classificação"]].copy()
    valid["Causa raiz"] = valid["Causa raiz"].map(_clean)
    valid["Classificação"] = valid["Classificação"].map(_clean)
    valid = valid[(valid["Causa raiz"] != "") & (valid["Classificação"] != "")]

    result = dict(fallback)
    for cause, group in valid.groupby("Causa raiz"):
        counts = Counter(group["Classificação"])
        if not counts:
            continue
        top_two = counts.most_common(2)
        if len(top_two) > 1 and top_two[0][1] == top_two[1][1]:
            continue
        result[cause] = top_two[0][0]

    return result


def _pattern_matches(text: str, pattern: str) -> bool:
    """Suporta frase simples e partes obrigatorias separadas por '+'."""
    parts = [normalize_text(part) for part in str(pattern).split("+")]
    parts = [part for part in parts if part]
    return bool(parts) and all(f" {part} " in f" {text} " for part in parts)


def _pattern_specificity(pattern: str) -> tuple[int, int]:
    normalized_parts = [normalize_text(part) for part in str(pattern).split("+")]
    normalized_parts = [part for part in normalized_parts if part]
    token_count = sum(len(part.split()) for part in normalized_parts)
    return token_count, len(normalized_parts)


def _cause_candidates(text: str, dictionary: dict) -> list[dict]:
    candidates: list[dict] = []

    for item in dictionary.get("intencoes", []):
        patterns = [
            str(pattern).strip()
            for pattern in item.get("padroes", [])
            if str(pattern).strip()
        ]
        exclusions = [
            str(pattern).strip()
            for pattern in item.get("exclusoes", [])
            if str(pattern).strip()
        ]

        if any(_pattern_matches(text, exclusion) for exclusion in exclusions):
            continue

        matches = [pattern for pattern in patterns if _pattern_matches(text, pattern)]
        if not matches:
            continue

        best_pattern = max(matches, key=_pattern_specificity)
        candidates.append(
            {
                "id": _clean(item.get("id")),
                "intencao": _clean(item.get("intencao")),
                "causa": _clean(item.get("causa_padrao")),
                "yaml_class": _clean(item.get("classificacao")),
                "patterns": matches,
                "best_pattern": best_pattern,
                "specificity": _pattern_specificity(best_pattern),
                "historical_evidence": int(item.get("evidencias_historicas") or 0),
            }
        )

    return candidates


def _empty_result(reason_code: str, status: str = STATUS_UNMATCHED) -> dict:
    return {
        "status": status,
        "intencao_id": None,
        "intencao_identificada": None,
        "causa_identificada": [],
        "causa_padrao": None,
        "causa_canonica": None,
        "classificacao": None,
        "regra": None,
        "candidatas": [],
        "ambiguo": status == STATUS_AMBIGUOUS,
        "reason_code": reason_code,
    }


def classify(
    description,
    rules=None,
    taxonomy=None,
    history: pd.DataFrame | None = None,
) -> dict:
    """Classifica pela causa com padrao mais especifico."""
    del taxonomy
    dictionary = rules if isinstance(rules, dict) and "intencoes" in rules else load_dictionary()
    text = prepare_classification_text(description)

    if not text:
        return _empty_result(REASON_EMPTY_TEXT)

    candidates = _cause_candidates(text, dictionary)
    if not candidates:
        return _empty_result(REASON_NO_PATTERN)

    candidates.sort(
        key=lambda item: (item["specificity"], item["historical_evidence"]),
        reverse=True,
    )
    best = candidates[0]
    tied = [
        item
        for item in candidates
        if item["specificity"] == best["specificity"]
        and item["historical_evidence"] == best["historical_evidence"]
        and item["causa"] != best["causa"]
    ]

    if tied:
        result = _empty_result(REASON_AMBIGUOUS, STATUS_AMBIGUOUS)
        result["candidatas"] = [best["id"], *[item["id"] for item in tied]]
        return result

    class_by_cause = build_class_by_cause(history, dictionary)
    classification = class_by_cause.get(best["causa"]) or best["yaml_class"] or None
    if classification is None:
        return _empty_result(REASON_NO_CLASS)

    return {
        "status": STATUS_SUGGESTED,
        "intencao_id": best["id"],
        "intencao_identificada": best["intencao"],
        "causa_identificada": best["patterns"],
        "causa_padrao": best["causa"],
        "causa_canonica": best["causa"],
        "classificacao": classification,
        "regra": best["id"],
        "candidatas": [best["id"]],
        "ambiguo": False,
        "reason_code": REASON_CLASSIFIED,
    }


def identify_intent(description, dictionary: dict | None = None) -> dict:
    return classify(description, rules=dictionary)


def identify_cause(description, rules=None) -> dict:
    return classify(description, rules=rules)


def normalize_root_cause(identified: dict, dictionary: dict | None = None) -> dict:
    del dictionary
    return {
        "causa_canonica": identified.get("causa_padrao"),
        "classificacao": identified.get("classificacao"),
    }


def suggest(
    description,
    rules=None,
    taxonomy=None,
    objects: dict | None = None,
    stats: dict | None = None,
    history: pd.DataFrame | None = None,
) -> dict:
    del stats
    found = classify(description, rules=rules, taxonomy=taxonomy, history=history)
    objects = objects or load_objects()
    classification = found.get("classificacao")
    return {
        **found,
        "objeto_operacional": objects.get(classification),
        "confianca": None,
        "motivo": found.get("causa_padrao") or found.get("reason_code"),
    }


def build_suggestions(
    descriptions: pd.Series,
    history: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Interface mantida para nao quebrar main.py."""
    dictionary = load_dictionary()
    objects = load_objects()
    rows = [
        suggest(
            description,
            rules=dictionary,
            objects=objects,
            history=history,
        )
        for description in descriptions
    ]
    return pd.DataFrame(rows, index=descriptions.index)


def evaluate(history: pd.DataFrame, dictionary: dict | None = None) -> dict:
    dictionary = dictionary or load_dictionary()
    rows: list[dict] = []

    for _, record in history.iterrows():
        actual = _clean(record.get("Classificação"))
        if not actual or actual == "#N/A":
            continue

        result = classify(
            record.get("Descrição detalhada"),
            rules=dictionary,
            history=history,
        )
        rows.append(
            {
                "real": actual,
                "motor": result.get("classificacao"),
                "status": result.get("status"),
                "intencao": result.get("intencao_id"),
            }
        )

    frame = pd.DataFrame(rows, columns=["real", "motor", "status", "intencao"])
    answered = frame[frame["motor"].notna()]
    correct = int((answered["real"] == answered["motor"]).sum())

    return {
        "total": len(frame),
        "com_resposta": len(answered),
        "sem_correspondencia": int((frame["status"] == STATUS_UNMATCHED).sum()),
        "ambiguos": int((frame["status"] == STATUS_AMBIGUOUS).sum()),
        "acertos": correct,
        "acuracia_entre_respostas": round(correct / len(answered), 4) if len(answered) else None,
    }


def main() -> None:
    dictionary = load_dictionary()
    problems = validate_dictionary(dictionary)
    print(f"Causas no dicionario: {len(dictionary['intencoes'])}")
    print(f"Problemas no dicionario: {len(problems)}")
    for problem in problems:
        print(f"- {problem}")


if __name__ == "__main__":
    main()
