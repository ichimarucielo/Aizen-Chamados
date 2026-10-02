"""Descricao -> grupo -> classificacao -> objeto operacional, via regras e taxonomia (YAML).

O motor apenas SUGERE; nada e preenchido nas colunas de negocio. Sugestoes usam
regras "aprovado" e "revisar" (nunca "descartar"). A avaliacao historica usa
somente as aprovadas, ou tambem as rascunho com --incluir-rascunho. Sem regra
aplicavel ou com empate entre classificacoes, nao ha sugestao.
A metrica de sucesso e o acerto da CLASSIFICACAO, nao da causa raiz exata.
"""

from pathlib import Path
import re
import sys
import unicodedata

import pandas as pd
import yaml

from extract import load_compilado_sheet
from parse_description import normalize_description


BASE_DIR = Path(__file__).resolve().parent.parent
RULES_PATH = BASE_DIR / "data" / "input" / "causa_raiz_rules.yaml"
TAXONOMY_PATH = BASE_DIR / "data" / "input" / "causa_raiz_taxonomia.yaml"
TEMPLATE_PATH = BASE_DIR / "data" / "input" / "plano_n2_template.xlsx"

APPROVED = "aprovado"
DRAFT = "revisar"


def normalize_text(text) -> str:
    if pd.isna(text):
        return ""
    value = unicodedata.normalize("NFKD", normalize_description(text).lower())
    return "".join(char for char in value if not unicodedata.combining(char))


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_taxonomy(path: Path = TAXONOMY_PATH) -> dict:
    return _load_yaml(path)["grupos"]


def load_objects(path: Path = TAXONOMY_PATH) -> dict:
    return _load_yaml(path)["objetos_operacionais"]


def load_rules(path: Path = RULES_PATH, include_draft: bool = False) -> dict:
    allowed = {APPROVED, DRAFT} if include_draft else {APPROVED}
    return {
        name: rule
        for name, rule in _load_yaml(path)["rules"].items()
        if rule.get("status") in allowed
    }


def validate_taxonomy(history: pd.DataFrame, taxonomy: dict, rules: dict) -> list[str]:
    """Problemas que invalidam a medicao: regra sem grupo, variante duplicada ou fora do historico."""

    problems = []
    seen = {}
    for group, data in taxonomy.items():
        for variant in data["variantes"]:
            key = variant.strip().casefold()
            if key in seen:
                problems.append(f"variante repetida: '{variant}' em {seen[key]} e {group}")
            seen[key] = group

    for name, rule in rules.items():
        if rule["grupo"] not in taxonomy:
            problems.append(f"regra '{name}' aponta para grupo inexistente '{rule['grupo']}'")

    for _, record in history.iterrows():
        cause = record.get("Causa raiz")
        if pd.isna(cause):
            continue
        key = str(cause).strip().casefold()
        group = seen.get(key)
        if group is None:
            problems.append(f"causa sem grupo na taxonomia: '{str(cause).strip()}'")
            continue
        classification = record.get("Classificação")
        if pd.notna(classification) and classification != taxonomy[group]["classificacao"]:
            problems.append(
                f"'{str(cause).strip()}': historico='{classification}' "
                f"taxonomia='{taxonomy[group]['classificacao']}'"
            )
    return sorted(set(problems))


def _has_term(text: str, term: str) -> bool:
    # Casa no inicio de palavra: "boleto" casa "boletos".
    return re.search(rf"(?<!\w){re.escape(normalize_text(term))}", text) is not None


def _match(text: str, rule: dict) -> list[str] | None:
    """Termos encontrados, ou None se a regra nao se aplica."""

    if any(_has_term(text, term) for term in rule.get("excluded", [])):
        return None
    if not all(_has_term(text, term) for term in rule.get("required", [])):
        return None

    optional = [term for term in rule.get("optional", []) if _has_term(text, term)]
    if rule.get("optional") and not optional:
        return None
    return list(rule.get("required", [])) + optional


def classify(description, rules: dict, taxonomy: dict) -> dict:
    """Escolhe o grupo com mais termos; empate entre classificacoes distintas = sem resposta."""

    text = normalize_text(description)
    matches = {
        name: terms
        for name, rule in rules.items()
        if (terms := _match(text, rule)) is not None
    }
    empty = {"grupo": None, "causa_canonica": None, "classificacao": None,
             "regra": None, "termos": [], "candidatas": []}
    if not matches:
        return empty

    best = max(len(terms) for terms in matches.values())
    top = [name for name, terms in matches.items() if len(terms) == best]
    classifications = {taxonomy[rules[name]["grupo"]]["classificacao"] for name in top}
    if len(classifications) > 1:
        return {**empty, "candidatas": top}

    group = rules[top[0]]["grupo"]
    return {
        "grupo": group,
        "causa_canonica": taxonomy[group]["causa_canonica"],
        "classificacao": taxonomy[group]["classificacao"],
        "regra": top[0],
        "termos": matches[top[0]],
        "candidatas": top,
    }


def _run_history(history: pd.DataFrame, rules: dict, taxonomy: dict) -> pd.DataFrame:
    rows = []
    for _, record in history.iterrows():
        real = record.get("Classificação")
        if pd.isna(real) or pd.isna(record.get("Causa raiz")):
            continue
        found = classify(record.get("Descrição detalhada"), rules, taxonomy)
        rows.append({
            "real": real,
            "motor": found["classificacao"],
            "regra": found["regra"],
            "ambiguo": found["classificacao"] is None and len(found["candidatas"]) > 1,
        })
    return pd.DataFrame(rows)


def rule_stats(history: pd.DataFrame, rules: dict, taxonomy: dict) -> dict:
    """Por regra: (acertos de classificacao, respostas) no historico."""

    frame = _run_history(history, rules, taxonomy)
    answered = frame[frame["regra"].notna()]
    return {
        name: (int((group["real"] == group["motor"]).sum()), len(group))
        for name, group in answered.groupby("regra")
    }


def suggest(description, rules: dict, taxonomy: dict, objects: dict, stats: dict) -> dict:
    """Sugestao nao vinculante; vazia quando nenhuma regra se aplica sem ambiguidade."""

    found = classify(description, rules, taxonomy)
    if found["classificacao"] is None:
        return {"objeto_operacional": None, "classificacao": None,
                "confianca": None, "motivo": None}

    hits, total = stats.get(found["regra"], (0, 0))
    return {
        "objeto_operacional": objects[found["classificacao"]],
        "classificacao": found["classificacao"],
        "confianca": round((hits + 1) / (total + 2), 2),  # Laplace: evita 100% com poucos casos
        "motivo": (f"Regra '{found['regra']}' (termos: {', '.join(found['termos'])}); "
                   f"acertou {hits}/{total} no histórico."),
    }


def build_suggestions(descriptions: pd.Series, history: pd.DataFrame) -> pd.DataFrame:
    """Sugestoes para cada trecho de problema, calibradas no historico."""

    rules = load_rules(include_draft=True)
    taxonomy = load_taxonomy()
    objects = load_objects()
    stats = rule_stats(history, rules, taxonomy)
    rows = [suggest(text, rules, taxonomy, objects, stats) for text in descriptions]
    return pd.DataFrame(rows, index=descriptions.index)


def evaluate(history: pd.DataFrame, rules: dict, taxonomy: dict) -> dict:
    """Acerto da classificacao do motor contra a coluna Classificação do historico."""

    frame = _run_history(history, rules, taxonomy)
    answered = frame[frame["motor"].notna()]
    return {
        "total": len(frame),
        "com_resposta": len(answered),
        "ambiguos": int(frame["ambiguo"].sum()),
        "acertos": int((answered["real"] == answered["motor"]).sum()),
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
    include_draft = "--incluir-rascunho" in sys.argv
    rules = load_rules(include_draft=include_draft)
    taxonomy = load_taxonomy()
    scope = "aprovadas + rascunho" if include_draft else "aprovadas"
    print(f"Grupos na taxonomia: {len(taxonomy)} | regras ({scope}): {len(rules)}")

    history = load_compilado_sheet(TEMPLATE_PATH)
    problems = validate_taxonomy(history, taxonomy, rules)
    print(f"Inconsistencias taxonomia x historico: {len(problems)}")
    for problem in problems[:10]:
        print(f"  - {problem}")

    if not rules:
        print("Nenhuma regra aprovada. Use --incluir-rascunho para avaliar rascunhos.")
        return

    result = evaluate(history, rules, taxonomy)
    answered = result["com_resposta"]
    print(f"\nHistoricos avaliados: {result['total']}")
    print(f"Cobertura (motor respondeu): {answered} ({answered / result['total']:.1%})")
    print(f"Ambiguos entre classificacoes: {result['ambiguos']}")
    if answered:
        print(f"ACERTO DA CLASSIFICACAO: {result['acertos']}/{answered} "
              f"({result['acertos'] / answered:.1%})")
    print("\nPor classificacao (total | respondidos | corretos):")
    for name, data in result["por_classificacao"].items():
        print(f"  {data['total']:>4} | {data['respondidos']:>4} | {data['corretos']:>4}  {name}")


if __name__ == "__main__":
    main()
