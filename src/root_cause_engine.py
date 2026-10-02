"""Descrição detalhada -> intenção -> causa padrão -> classificação oficial."""

from pathlib import Path
import re
import unicodedata

import pandas as pd
import yaml

from extract import load_compilado_sheet
from parse_description import normalize_description


BASE_DIR = Path(__file__).resolve().parent.parent
DICTIONARY_PATH = BASE_DIR / "data" / "input" / "dicionario_aizen_intencoes.yaml"
TAXONOMY_PATH = BASE_DIR / "data" / "input" / "causa_raiz_taxonomia.yaml"
TEMPLATE_PATH = BASE_DIR / "data" / "input" / "plano_n2_template.xlsx"


def normalize_text(text) -> str:
    if pd.isna(text):
        return ""
    value = unicodedata.normalize(
        "NFKD",
        normalize_description(str(text)).lower(),
    )
    value = "".join(
        char for char in value if not unicodedata.combining(char)
    )
    value = re.sub(r"\bnotas?\s+fisc(?:al|ais)\b|\bnfs\b", " nf ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    value = re.sub(r"\be\s+mail\b", "email", value)
    return value


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_dictionary(path: Path = DICTIONARY_PATH) -> dict:
    dictionary = _load_yaml(path)
    allowed = set(dictionary["classes_permitidas"])
    seen_ids = set()
    cause_classes = {}
    for intent in dictionary["intencoes"]:
        if intent["id"] in seen_ids:
            raise ValueError(f"ID de intenção duplicado: {intent['id']}")
        seen_ids.add(intent["id"])
        if intent["classificacao"] not in allowed:
            raise ValueError(
                f"Classificação fora do contrato em {intent['id']}: "
                f"{intent['classificacao']}"
            )
        cause = intent["causa_padrao"]
        previous = cause_classes.setdefault(cause, intent["classificacao"])
        if previous != intent["classificacao"]:
            raise ValueError(
                f"Causa padrão '{cause}' aponta para mais de uma classificação."
            )
    return dictionary


def load_taxonomy(path: Path = DICTIONARY_PATH) -> dict:
    """Mapa causa padrão -> classificação oficial, derivado do dicionário."""
    return {
        intent["causa_padrao"]: intent["classificacao"]
        for intent in load_dictionary(path)["intencoes"]
    }


def load_objects(path: Path = TAXONOMY_PATH) -> dict:
    return _load_yaml(path)["objetos_operacionais"]


def load_rules(
    path: Path = DICTIONARY_PATH,
    include_draft: bool = False,
) -> dict:
    """Compatibilidade: expõe intenções indexadas por ID, sem status/score."""
    return {
        intent["id"]: intent
        for intent in load_dictionary(path)["intencoes"]
    }


def validate_dictionary(dictionary: dict | None = None) -> list[str]:
    dictionary = dictionary or load_dictionary()
    allowed = set(dictionary["classes_permitidas"])
    problems = []
    ids = set()
    cause_classes = {}
    for intent in dictionary["intencoes"]:
        if intent["id"] in ids:
            problems.append(f"ID duplicado: {intent['id']}")
        ids.add(intent["id"])
        if intent["classificacao"] not in allowed:
            problems.append(f"Classe fora do contrato: {intent['id']}")
        previous = cause_classes.setdefault(
            intent["causa_padrao"],
            intent["classificacao"],
        )
        if previous != intent["classificacao"]:
            problems.append(
                f"Causa padrão com classes conflitantes: {intent['causa_padrao']}"
            )
        if not intent.get("padroes"):
            problems.append(f"Intenção sem padrões: {intent['id']}")
    return sorted(set(problems))


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized = normalize_text(phrase)
    return bool(normalized) and f" {normalized} " in f" {text} "


def _matches_pattern(text: str, pattern: str) -> bool:
    parts = [part.strip() for part in pattern.split("+")]
    return all(_contains_phrase(text, part) for part in parts)


def _apply_precedence(matches: list[dict], dictionary: dict) -> list[dict]:
    remaining = {intent["id"]: intent for intent in matches}
    for rule in dictionary.get("precedencia", []):
        preferred = rule["preferir"]
        if preferred not in remaining:
            continue
        for lower_priority in rule.get("sobre", []):
            remaining.pop(lower_priority, None)
    return list(remaining.values())


def identify_intent(description, dictionary: dict | None = None) -> dict:
    """Encontra intenções explícitas e deixa conflitos reais sem escolha arbitrária."""
    dictionary = dictionary or load_dictionary()
    text = normalize_text(description)
    if not text:
        return {
            "status": "Sem correspondência",
            "intencao_id": None,
            "intencao_identificada": None,
            "causa_identificada": [],
            "causa_padrao": None,
            "classificacao": None,
            "regra": None,
            "candidatas": [],
            "ambiguo": False,
        }

    matches = []
    matched_patterns = {}
    for intent in dictionary["intencoes"]:
        found = [
            pattern
            for pattern in intent.get("padroes", [])
            if _matches_pattern(text, pattern)
        ]
        if not found:
            continue
        if any(
            _matches_pattern(text, excluded)
            for excluded in intent.get("exclusoes", [])
        ):
            continue
        matches.append(intent)
        matched_patterns[intent["id"]] = found

    matches = _apply_precedence(matches, dictionary)
    if not matches:
        return {
            "status": "Sem correspondência",
            "intencao_id": None,
            "intencao_identificada": None,
            "causa_identificada": [],
            "causa_padrao": None,
            "classificacao": None,
            "regra": None,
            "candidatas": [],
            "ambiguo": False,
        }

    causes = list(dict.fromkeys(intent["causa_padrao"] for intent in matches))
    classes = list(dict.fromkeys(intent["classificacao"] for intent in matches))
    unique_cause = len(causes) == 1
    unique_class = len(classes) == 1
    status = "Sugerida" if unique_cause and unique_class else "Ambígua"
    selected = matches[0] if unique_cause else None
    matched = []
    seen_patterns = set()
    for intent in matches:
        for pattern in matched_patterns[intent["id"]]:
            normalized_pattern = normalize_text(pattern.replace("+", " "))
            if normalized_pattern not in seen_patterns:
                seen_patterns.add(normalized_pattern)
                matched.append(pattern)
    return {
        "status": status,
        "intencao_id": selected["id"] if selected else None,
        "intencao_identificada": "; ".join(
            dict.fromkeys(intent["intencao"] for intent in matches)
        ),
        "causa_identificada": matched,
        "causa_padrao": causes[0] if unique_cause else None,
        "classificacao": classes[0] if unique_class else None,
        "regra": selected["id"] if selected else None,
        "candidatas": [intent["id"] for intent in matches],
        "ambiguo": status == "Ambígua",
    }


def identify_cause(description, rules=None) -> dict:
    """Alias de compatibilidade para o passo novo de identificação da intenção."""
    return identify_intent(description, _dictionary_from_rules(rules))


def _dictionary_from_rules(rules=None) -> dict:
    if rules is None:
        return load_dictionary()
    if isinstance(rules, dict) and "intencoes" in rules:
        return rules
    intents = list(rules.values()) if isinstance(rules, dict) else list(rules)
    base = load_dictionary()
    return {**base, "intencoes": intents}


def normalize_root_cause(
    identified: dict,
    dictionary: dict | None = None,
) -> dict:
    """Resolve a causa padrão no dicionário e deriva dela a classe oficial."""
    dictionary = dictionary or load_dictionary()
    cause = identified.get("causa_padrao")
    class_by_cause = {
        intent["causa_padrao"]: intent["classificacao"]
        for intent in dictionary["intencoes"]
    }
    return {
        "causa_canonica": cause,
        "classificacao": class_by_cause.get(
            cause,
            identified.get("classificacao"),
        ),
    }


def classify(description, rules=None, taxonomy=None) -> dict:
    """Descrição -> intenção -> causa padrão -> classificação oficial."""
    dictionary = _dictionary_from_rules(rules)
    identified = identify_intent(description, dictionary)
    normalized = normalize_root_cause(identified, dictionary)
    return {**identified, **normalized}


def suggest(
    description,
    rules=None,
    taxonomy=None,
    objects: dict | None = None,
    stats: dict | None = None,
) -> dict:
    """Retorna uma classificação explicável; não pontua nem escolhe por score."""
    found = classify(description, rules, taxonomy)
    objects = objects or load_objects()
    classification = found["classificacao"]
    return {
        **found,
        "objeto_operacional": objects.get(classification),
        "confianca": None,
        "motivo": found["intencao_identificada"],
    }


def build_suggestions(
    descriptions: pd.Series,
    history: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Classifica Descrição detalhada; history fica na assinatura por compatibilidade."""
    dictionary = load_dictionary()
    objects = load_objects()
    rows = [
        suggest(description, dictionary, objects=objects)
        for description in descriptions
    ]
    return pd.DataFrame(rows, index=descriptions.index)


def evaluate(history: pd.DataFrame, dictionary: dict | None = None) -> dict:
    """Compara classes sugeridas com as classes históricas, sem score nem treino."""
    dictionary = _dictionary_from_rules(dictionary)
    rows = []
    for _, record in history.iterrows():
        actual = record.get("Classificação")
        if pd.isna(actual) or not str(actual).strip() or str(actual).strip() == "#N/A":
            continue
        result = classify(record.get("Descrição detalhada"), dictionary)
        rows.append({
            "real": str(actual).strip(),
            "motor": result["classificacao"],
            "status": result["status"],
            "intencao": result["intencao_id"],
        })
    frame = pd.DataFrame(rows)
    if frame.empty:
        frame = pd.DataFrame(columns=["real", "motor", "status", "intencao"])
    answered = frame[frame["motor"].notna()]
    correct = int((answered["real"] == answered["motor"]).sum())
    return {
        "total": len(frame),
        "com_resposta": len(answered),
        "sem_correspondencia": int((frame["status"] == "Sem correspondência").sum()),
        "ambiguos": int((frame["status"] == "Ambígua").sum()),
        "acertos": correct,
        "acuracia_entre_respostas": (
            round(correct / len(answered), 4) if len(answered) else None
        ),
        "por_classificacao": {
            name: {
                "total": int((frame["real"] == name).sum()),
                "respondidos": int((answered["motor"] == name).sum()),
                "corretos": int(((answered["real"] == name) & (answered["motor"] == name)).sum()),
            }
            for name in sorted(frame["real"].unique())
        },
    }


def main() -> None:
    dictionary = load_dictionary()
    history = load_compilado_sheet(TEMPLATE_PATH)
    result = evaluate(history, dictionary)
    answered = result["com_resposta"]
    print(f"Intenções no dicionário: {len(dictionary['intencoes'])}")
    print(f"Históricos avaliados: {result['total']}")
    print(f"Cobertura: {answered}/{result['total']}")
    print(f"Sem correspondência: {result['sem_correspondencia']}")
    print(f"Ambíguos: {result['ambiguos']}")
    if answered:
        print(
            f"Acerto de classe no histórico: {result['acertos']}/{answered} "
            f"({result['acuracia_entre_respostas']:.1%})"
        )
    print("\nPor classificação (total | respondidos | corretos):")
    for name, data in result["por_classificacao"].items():
        print(f"  {data['total']:>4} | {data['respondidos']:>4} | {data['corretos']:>4}  {name}")


if __name__ == "__main__":
    main()
