"""Motor determinístico do AIZEN.

Fluxo de decisão:
1. Texto -> vocabulário canônico -> assinatura operacional.
2. Assinatura -> causa raiz -> uma das seis classificações oficiais.
3. Padrões textuais atuais como fallback.
4. Sem evidência segura -> NO_PATTERN.
"""

from __future__ import annotations

from pathlib import Path
import re
import unicodedata
from typing import Any

import pandas as pd
import yaml

from parse_description import normalize_description


BASE_DIR = Path(__file__).resolve().parent.parent
DICTIONARY_PATH = (
    BASE_DIR
    / "data"
    / "input"
    / "dicionario_aizen_intencoes.yaml"
)
TAXONOMY_PATH = (
    BASE_DIR
    / "data"
    / "input"
    / "causa_raiz_taxonomia.yaml"
)

STATUS_SUGGESTED = "Sugerida"
STATUS_UNMATCHED = "Sem correspondencia"
STATUS_AMBIGUOUS = "Ambigua"

REASON_CLASSIFIED_SIGNATURE = "CLASSIFIED_SIGNATURE"
REASON_CLASSIFIED_PATTERN = "CLASSIFIED_PATTERN"
REASON_EMPTY_TEXT = "EMPTY_TEXT"
REASON_NO_PATTERN = "NO_PATTERN"
REASON_AMBIGUOUS = "AMBIGUOUS_CAUSE"
REASON_NO_CLASS = "CAUSE_WITHOUT_CLASS"

VOCABULARY_GROUPS = (
    "acoes",
    "objetos",
    "contextos",
    "canais",
)

SIGNATURE_FIELDS = {
    "acoes_um_de": "acoes",
    "acoes_todas": "acoes",
    "objetos_um_de": "objetos",
    "objetos_todos": "objetos",
    "contextos_um_de": "contextos",
    "contextos_todos": "contextos",
    "canais_um_de": "canais",
    "canais_todos": "canais",
    "excluir_acoes": "acoes",
    "excluir_objetos": "objetos",
    "excluir_contextos": "contextos",
    "excluir_canais": "canais",
}

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


def normalize_text(value: Any) -> str:
    """Normaliza texto para correspondência determinística."""
    if value is None or pd.isna(value):
        return ""

    text = normalize_description(str(value)).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )
    text = re.sub(
        r"[\w.+-]+@[\w.-]+\.\w+",
        " email ",
        text,
    )
    text = re.sub(
        r"\bnotas?\s+fisc(?:al|ais)\b"
        r"|\bnf'?s\b"
        r"|\bnfs\b"
        r"|\bnf-?e\b"
        r"|\bnfs-?e\b",
        " nf ",
        text,
    )
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def prepare_classification_text(value: Any) -> str:
    """Remove ruído estrutural do formulário."""
    text = normalize_text(value)
    for pattern in FORM_BOILERPLATE_PATTERNS:
        text = re.sub(pattern, " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _load_yaml(path: Path) -> dict[str, Any]:
    content = yaml.safe_load(
        path.read_text(encoding="utf-8-sig")
    )
    return content or {}


def load_dictionary(
    path: Path = DICTIONARY_PATH,
) -> dict[str, Any]:
    dictionary = _load_yaml(path)
    required = {
    "classes_permitidas",
    "causas",
    "aliases_causas",
    "vocabulario",
    "intencoes",
    }
    missing = required.difference(dictionary)
    if missing:
        raise ValueError(
            "Seções ausentes no dicionário: "
            f"{sorted(missing)}"
        )
    return dictionary


def load_taxonomy(
    path: Path = DICTIONARY_PATH,
) -> dict[str, str]:
    return {
        str(item["causa_padrao"]).strip(): str(
            item["classificacao"]
        ).strip()
        for item in load_dictionary(path)["intencoes"]
        if item.get("causa_padrao")
        and item.get("classificacao")
    }


def load_objects(
    path: Path = TAXONOMY_PATH,
) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _load_yaml(path).get(
        "objetos_operacionais",
        {},
    )


def load_rules(
    path: Path = DICTIONARY_PATH,
    include_draft: bool = False,
) -> dict[str, dict[str, Any]]:
    del include_draft
    return {
        item["id"]: item
        for item in load_dictionary(path)["intencoes"]
        if item.get("id")
    }

def standardize_manual_cause(
    raw_cause: Any,
    dictionary: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Padroniza uma causa manual por correspondência exata.

    Retorna None quando a causa não possui alias seguro.
    """
    dictionary = dictionary or load_dictionary()

    cause_name = _clean(raw_cause)
    if not cause_name:
        return None

    cause_aliases = dictionary.get(
        "aliases_causas",
        {},
    )

    causes = dictionary.get(
        "causas",
        {},
    )

    cause_id = cause_aliases.get(
        cause_name
    )

    if not cause_id:
        return None

    cause_data = causes.get(
        cause_id
    )

    if not isinstance(cause_data, dict):
        return None

    canonical_name = _clean(
        cause_data.get("nome")
    )

    classification = _clean(
        cause_data.get("classificacao")
    )

    if not canonical_name or not classification:
        return None

    return {
        "causa_id": cause_id,
        "causa_padrao": canonical_name,
        "classificacao": classification,
    }



def resolve_intent_cause(
    intent: dict[str, Any],
    dictionary: dict[str, Any],
) -> dict[str, str]:
    """
    Resolve causa e classificação pelo catálogo canônico.

    Enquanto as intenções são migradas, mantém compatibilidade
    com causa_padrao e classificacao existentes.
    """
    cause_id = _clean(
        intent.get("causa_id")
    )

    causes = dictionary.get(
        "causas",
        {},
    )

    if cause_id:
        cause_data = causes.get(
            cause_id
        )

        if not isinstance(cause_data, dict):
            raise ValueError(
                "Causa canônica inexistente na intenção "
                f"'{_clean(intent.get('id'))}': "
                f"'{cause_id}'."
            )

        canonical_name = _clean(
            cause_data.get("nome")
        )

        classification = _clean(
            cause_data.get("classificacao")
        )

        if not canonical_name:
            raise ValueError(
                f"Causa canônica sem nome: '{cause_id}'."
            )

        if not classification:
            raise ValueError(
                "Causa canônica sem classificação: "
                f"'{cause_id}'."
            )

        return {
            "causa_id": cause_id,
            "causa_padrao": canonical_name,
            "classificacao": classification,
        }

    return {
        "causa_id": "",
        "causa_padrao": _clean(
            intent.get("causa_padrao")
        ),
        "classificacao": _clean(
            intent.get("classificacao")
        ),
    }



def _clean(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return [str(value).strip()]
    return [
        str(item).strip()
        for item in value
        if str(item).strip()
    ]


def validate_dictionary(
    dictionary: dict[str, Any] | None = None,
) -> list[str]:
    """
    Valida classes, causas, aliases, vocabulário,
    intenções, padrões e assinaturas.
    """
    dictionary = dictionary or load_dictionary()

    allowed_classes = set(
        dictionary.get(
            "classes_permitidas",
            [],
        )
    )

    vocabulary = dictionary.get(
        "vocabulario",
        {},
    )

    causes = dictionary.get(
        "causas",
        {},
    )

    cause_aliases = dictionary.get(
        "aliases_causas",
        {},
    )

    problems: list[str] = []
    seen_intent_ids: set[str] = set()

    # Validação do catálogo canônico de causas.
    if not isinstance(causes, dict):
        problems.append(
            "Seção de causas inválida."
        )
        causes = {}

    cause_names: list[str] = []

    for cause_id, cause_data in causes.items():
        if not isinstance(cause_data, dict):
            problems.append(
                f"Causa inválida: {cause_id}"
            )
            continue

        cause_name = _clean(
            cause_data.get("nome")
        )

        classification = _clean(
            cause_data.get("classificacao")
        )

        if not cause_name:
            problems.append(
                f"Causa sem nome: {cause_id}"
            )
        else:
            cause_names.append(
                cause_name
            )

        if not classification:
            problems.append(
                "Causa sem classificação: "
                f"{cause_id}"
            )
        elif classification not in allowed_classes:
            problems.append(
                "Classificação inválida na causa: "
                f"{cause_id} -> {classification}"
            )

    duplicate_cause_names = {
        cause_name
        for cause_name in cause_names
        if cause_names.count(cause_name) > 1
    }

    for cause_name in sorted(
        duplicate_cause_names
    ):
        problems.append(
            "Nome de causa duplicado: "
            f"{cause_name}"
        )

    # Validação dos aliases das causas manuais.
    if not isinstance(cause_aliases, dict):
        problems.append(
            "Seção de aliases_causas inválida."
        )
        cause_aliases = {}

    for alias, cause_id in cause_aliases.items():
        alias_name = _clean(alias)
        canonical_cause_id = _clean(
            cause_id
        )

        if not alias_name:
            problems.append(
                "Alias de causa vazio."
            )

        if not canonical_cause_id:
            problems.append(
                "Alias sem causa canônica: "
                f"{alias_name}"
            )
            continue

        if canonical_cause_id not in causes:
            problems.append(
                "Alias aponta para causa inexistente: "
                f"{alias_name} -> "
                f"{canonical_cause_id}"
            )

    # Validação do vocabulário canônico.
    if not isinstance(vocabulary, dict):
        problems.append(
            "Seção de vocabulário inválida."
        )
        vocabulary = {}

    for group in VOCABULARY_GROUPS:
        concepts = vocabulary.get(
            group
        )

        if not isinstance(concepts, dict):
            problems.append(
                "Vocabulário ausente ou inválido: "
                f"{group}"
            )
            continue

        for concept, aliases in concepts.items():
            concept_name = _clean(
                concept
            )

            if not concept_name:
                problems.append(
                    "Conceito vazio no vocabulário: "
                    f"{group}"
                )

            if not _as_string_list(aliases):
                problems.append(
                    "Conceito sem aliases: "
                    f"{group}.{concept_name}"
                )

    # Validação das intenções atuais.
    for item in dictionary.get(
        "intencoes",
        [],
    ):
        if not isinstance(item, dict):
            problems.append(
                "Intenção inválida."
            )
            continue

        intent_id = _clean(
            item.get("id")
        )

        if not intent_id:
            problems.append(
                "Intenção sem id"
            )
            continue

        if intent_id in seen_intent_ids:
            problems.append(
                f"ID duplicado: {intent_id}"
            )

        seen_intent_ids.add(
            intent_id
        )

        # Compatibilidade temporária com o modelo atual.
        cause_id = _clean(
            item.get("causa_id")
        )

        if cause_id:
            cause_data = causes.get(
                cause_id
            )

            if not isinstance(cause_data, dict):
                problems.append(
                    "Intenção aponta para causa "
                    "canônica inexistente: "
                    f"{intent_id} -> {cause_id}"
                )
            else:
                canonical_classification = _clean(
                    cause_data.get(
                        "classificacao"
                    )
                )

                legacy_classification = _clean(
                    item.get(
                        "classificacao"
                    )
                )

                if (
                    legacy_classification
                    and canonical_classification
                    != legacy_classification
                ):
                    problems.append(
                        "Classificação divergente entre "
                        "intenção e causa canônica: "
                        f"{intent_id} -> {cause_id}"
                    )

        # Compatibilidade temporária com as intenções
        # que ainda não foram migradas para causa_id.
        if not cause_id:
            if not item.get("causa_padrao"):
                problems.append(
                    "Intenção sem causa_padrao: "
                    f"{intent_id}"
                )

            classification = _clean(
                item.get("classificacao")
            )

            if classification not in allowed_classes:
                problems.append(
                    "Classe inválida: "
                    f"{intent_id} -> "
                    f"{classification}"
                )

        if not item.get("padroes"):
            problems.append(
                "Intenção sem padrões: "
                f"{intent_id}"
            )

        signatures = item.get(
            "assinaturas",
            [],
        )

        if signatures and not isinstance(
            signatures,
            list,
        ):
            problems.append(
                "Assinaturas inválidas: "
                f"{intent_id}"
            )
            continue

        for index, signature in enumerate(
            signatures,
            start=1,
        ):
            if not isinstance(
                signature,
                dict,
            ):
                problems.append(
                    "Assinatura inválida: "
                    f"{intent_id}[{index}]"
                )
                continue

            unknown_fields = (
                set(signature)
                - set(SIGNATURE_FIELDS)
            )

            if unknown_fields:
                problems.append(
                    "Campos de assinatura inválidos: "
                    f"{intent_id}[{index}] "
                    f"{sorted(unknown_fields)}"
                )

            for field, values in signature.items():
                group = SIGNATURE_FIELDS.get(
                    field
                )

                if not group:
                    continue

                known_concepts = set(
                    vocabulary.get(
                        group,
                        {},
                    )
                )

                for concept in _as_string_list(
                    values
                ):
                    if concept not in known_concepts:
                        problems.append(
                            "Conceito desconhecido: "
                            f"{intent_id}[{index}]."
                            f"{field}={concept}"
                        )

    return sorted(
        set(problems)
    )


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized_phrase = normalize_text(phrase)
    if not normalized_phrase:
        return False
    return (
        f" {normalized_phrase} "
        in f" {text} "
    )


def extract_signature(
    text: str,
    dictionary: dict[str, Any],
) -> dict[str, set[str]]:
    """Extrai conceitos canônicos presentes no texto."""
    normalized_text = prepare_classification_text(text)
    vocabulary = dictionary.get("vocabulario", {})

    extracted: dict[str, set[str]] = {
        group: set()
        for group in VOCABULARY_GROUPS
    }

    for group in VOCABULARY_GROUPS:
        concepts = vocabulary.get(group, {})
        for concept, aliases in concepts.items():
            if any(
                _contains_phrase(normalized_text, alias)
                for alias in _as_string_list(aliases)
            ):
                extracted[group].add(str(concept))

    return extracted


def _matches_any(
    actual: set[str],
    expected: list[str],
) -> bool:
    return bool(set(expected).intersection(actual))


def _matches_all(
    actual: set[str],
    expected: list[str],
) -> bool:
    return set(expected).issubset(actual)


def _signature_matches(
    extracted: dict[str, set[str]],
    rule: dict[str, Any],
) -> bool:
    """Avalia uma assinatura sem score ou probabilidade."""
    positive_rules = (
        ("acoes_um_de", "acoes", _matches_any),
        ("acoes_todas", "acoes", _matches_all),
        ("objetos_um_de", "objetos", _matches_any),
        ("objetos_todos", "objetos", _matches_all),
        ("contextos_um_de", "contextos", _matches_any),
        ("contextos_todos", "contextos", _matches_all),
        ("canais_um_de", "canais", _matches_any),
        ("canais_todos", "canais", _matches_all),
    )

    for field, group, matcher in positive_rules:
        expected = _as_string_list(rule.get(field))
        if expected and not matcher(
            extracted[group],
            expected,
        ):
            return False

    exclusions = (
        ("excluir_acoes", "acoes"),
        ("excluir_objetos", "objetos"),
        ("excluir_contextos", "contextos"),
        ("excluir_canais", "canais"),
    )

    for field, group in exclusions:
        excluded = set(
            _as_string_list(rule.get(field))
        )
        if excluded.intersection(extracted[group]):
            return False

    has_positive_condition = any(
        _as_string_list(rule.get(field))
        for field, _, _ in positive_rules
    )
    return has_positive_condition


def _signature_specificity(
    rule: dict[str, Any],
) -> tuple[int, int, int, int]:
    """Prioriza ação explícita e maior completude semântica."""
    action_present = int(
        bool(_as_string_list(rule.get("acoes_um_de")))
        or bool(_as_string_list(rule.get("acoes_todas")))
    )
    object_present = int(
        bool(_as_string_list(rule.get("objetos_um_de")))
        or bool(_as_string_list(rule.get("objetos_todos")))
    )
    context_present = int(
        bool(_as_string_list(rule.get("contextos_um_de")))
        or bool(_as_string_list(rule.get("contextos_todos")))
    )
    channel_present = int(
        bool(_as_string_list(rule.get("canais_um_de")))
        or bool(_as_string_list(rule.get("canais_todos")))
    )

    dimensions = (
        action_present
        + object_present
        + context_present
        + channel_present
    )
    exclusions = sum(
        len(_as_string_list(rule.get(field)))
        for field in (
            "excluir_acoes",
            "excluir_objetos",
            "excluir_contextos",
            "excluir_canais",
        )
    )
    required_all = sum(
        len(_as_string_list(rule.get(field)))
        for field in (
            "acoes_todas",
            "objetos_todos",
            "contextos_todos",
            "canais_todos",
        )
    )

    # Ordem determinística: ação explícita, dimensões, condições 'todas', exclusões.
    return action_present, dimensions, required_all, exclusions


def _signature_candidates(
    text: str,
    dictionary: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, set[str]]]:
    extracted = extract_signature(text, dictionary)
    candidates: list[dict[str, Any]] = []

    for item in dictionary.get("intencoes", []):
        for index, signature_rule in enumerate(
            item.get("assinaturas", []),
            start=1,
        ):
            if not _signature_matches(
                extracted,
                signature_rule,
            ):
                continue

            resolved_cause = resolve_intent_cause(
                intent=item,
                dictionary=dictionary,
            )

            candidates.append(
                {
                    "id": _clean(item.get("id")),
                    "intencao": _clean(
                        item.get("intencao")
                    ),
                    "causa_id": resolved_cause[
                        "causa_id"
                    ],
                    "causa": resolved_cause[
                        "causa_padrao"
                    ],
                    "yaml_class": resolved_cause[
                        "classificacao"
                    ],
                    "signature_index": index,
                    "signature_rule": signature_rule,
                    "specificity": _signature_specificity(
                        signature_rule
                    ),
                }
            )

    return candidates, extracted


def _pattern_matches(text: str, pattern: str) -> bool:
    """Suporta frase simples e partes obrigatórias separadas por '+'."""
    parts = [
        normalize_text(part)
        for part in str(pattern).split("+")
    ]
    parts = [part for part in parts if part]
    return bool(parts) and all(
        f" {part} " in f" {text} "
        for part in parts
    )


def _pattern_specificity(
    pattern: str,
) -> tuple[int, int]:
    normalized_parts = [
        normalize_text(part)
        for part in str(pattern).split("+")
    ]
    normalized_parts = [
        part
        for part in normalized_parts
        if part
    ]
    token_count = sum(
        len(part.split())
        for part in normalized_parts
    )
    return token_count, len(normalized_parts)


def _pattern_candidates(
    text: str,
    dictionary: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for item in dictionary.get("intencoes", []):
        patterns = _as_string_list(
            item.get("padroes", [])
        )
        exclusions = _as_string_list(
            item.get("exclusoes", [])
        )

        if any(
            _pattern_matches(text, exclusion)
            for exclusion in exclusions
        ):
            continue

        matches = [
            pattern
            for pattern in patterns
            if _pattern_matches(text, pattern)
        ]
        if not matches:
            continue

        best_pattern = max(
            matches,
            key=_pattern_specificity,
        )

        resolved_cause = resolve_intent_cause(
            intent=item,
            dictionary=dictionary,
        )

        candidates.append(
            {
                "id": _clean(item.get("id")),
                "intencao": _clean(
                    item.get("intencao")
                ),
                "causa_id": resolved_cause[
                    "causa_id"
                ],
                "causa": resolved_cause[
                    "causa_padrao"
                ],
                "yaml_class": resolved_cause[
                    "classificacao"
                ],
                "patterns": matches,
                "best_pattern": best_pattern,
                "specificity": _pattern_specificity(
                    best_pattern
                ),
                "historical_evidence": int(
                    item.get("evidencias_historicas")
                    or 0
                ),
            }
        )

    return candidates


def _empty_result(
    reason_code: str,
    status: str = STATUS_UNMATCHED,
) -> dict[str, Any]:
    return {
        "status": status,
        "intencao_id": None,
        "intencao_identificada": None,
        "causa_identificada": [],
        "causa_id": None,
        "causa_padrao": None,
        "causa_canonica": None,
        "classificacao": None,
        "regra": None,
        "candidatas": [],
        "ambiguo": status == STATUS_AMBIGUOUS,
        "reason_code": reason_code,
    }


def _canonical_evidence(
    extracted: dict[str, set[str]],
) -> list[str]:
    labels = {
        "acoes": "ACAO",
        "objetos": "OBJETO",
        "contextos": "CONTEXTO",
        "canais": "CANAL",
    }
    evidence: list[str] = []
    for group in VOCABULARY_GROUPS:
        for concept in sorted(extracted[group]):
            evidence.append(
                f"{labels[group]}:{concept}"
            )
    return evidence


def _result_from_candidate(
    candidate: dict[str, Any],
    evidence: list[str],
    reason_code: str,
) -> dict[str, Any]:
    classification = candidate.get("yaml_class") or None
    if classification is None:
        return _empty_result(REASON_NO_CLASS)

    return {
        "status": STATUS_SUGGESTED,
        "intencao_id": candidate["id"],
        "intencao_identificada": candidate["intencao"],
        "causa_identificada": evidence,
        "causa_id": (
            candidate.get("causa_id")
            or None
        ),
        "causa_padrao": candidate["causa"],
        "causa_canonica": candidate["causa"],
        "classificacao": classification,
        "regra": candidate["id"],
        "candidatas": [candidate["id"]],
        "ambiguo": False,
        "reason_code": reason_code,
    }


def _consolidate_candidates(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Mantém uma candidata por intenção, escolhendo sua melhor evidência."""
    by_id: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        intent_id = candidate["id"]
        current = by_id.get(intent_id)
        if current is None or candidate["specificity"] > current["specificity"]:
            by_id[intent_id] = candidate
    return list(by_id.values())


def _select_candidate(
    candidates: list[dict[str, Any]],
    use_historical_evidence: bool = False,
) -> tuple[dict[str, Any] | None, list[str]]:
    candidates = _consolidate_candidates(candidates)
    if not candidates:
        return None, []

    def rank(item: dict[str, Any]) -> tuple[Any, ...]:
        base = (item["specificity"],)
        if use_historical_evidence:
            return (*base, int(item.get("historical_evidence") or 0))
        return base

    candidates.sort(key=rank, reverse=True)
    best = candidates[0]
    best_rank = rank(best)
    tied = [
        item
        for item in candidates[1:]
        if rank(item) == best_rank
        and item["causa"] != best["causa"]
    ]

    if not tied:
        return best, []

    candidate_ids = list(dict.fromkeys([
        best["id"],
        *[item["id"] for item in tied],
    ]))
    return None, candidate_ids


def classify(
    description: Any,
    rules: dict[str, Any] | None = None,
    taxonomy: dict[str, str] | None = None,
    history: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Classifica por assinatura e usa padrões atuais como fallback."""
    del taxonomy, history

    dictionary = (
        rules
        if isinstance(rules, dict)
        and "intencoes" in rules
        else load_dictionary()
    )
    text = prepare_classification_text(description)

    if not text:
        return _empty_result(REASON_EMPTY_TEXT)

    signature_candidates, extracted = _signature_candidates(
        text,
        dictionary,
    )
    signature_match, signature_ties = _select_candidate(
        signature_candidates
    )

    if signature_ties:
        result = _empty_result(
            REASON_AMBIGUOUS,
            STATUS_AMBIGUOUS,
        )
        result["candidatas"] = signature_ties
        result["causa_identificada"] = (
            _canonical_evidence(extracted)
        )
        return result

    if signature_match:
        return _result_from_candidate(
            candidate=signature_match,
            evidence=_canonical_evidence(extracted),
            reason_code=REASON_CLASSIFIED_SIGNATURE,
        )

    pattern_candidates = _pattern_candidates(
        text,
        dictionary,
    )
    pattern_match, pattern_ties = _select_candidate(
        pattern_candidates,
        use_historical_evidence=True,
    )

    if pattern_ties:
        result = _empty_result(
            REASON_AMBIGUOUS,
            STATUS_AMBIGUOUS,
        )
        result["candidatas"] = pattern_ties
        return result

    if pattern_match:
        return _result_from_candidate(
            candidate=pattern_match,
            evidence=pattern_match["patterns"],
            reason_code=REASON_CLASSIFIED_PATTERN,
        )

    return _empty_result(REASON_NO_PATTERN)


def identify_intent(
    description: Any,
    dictionary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return classify(description, rules=dictionary)


def identify_cause(
    description: Any,
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return classify(description, rules=rules)


def normalize_root_cause(
    identified: dict[str, Any],
    dictionary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del dictionary
    return {
        "causa_canonica": identified.get(
            "causa_padrao"
        ),
        "classificacao": identified.get(
            "classificacao"
        ),
    }


def suggest(
    description: Any,
    rules: dict[str, Any] | None = None,
    taxonomy: dict[str, str] | None = None,
    objects: dict[str, Any] | None = None,
    stats: dict[str, Any] | None = None,
    history: pd.DataFrame | None = None,
) -> dict[str, Any]:
    del stats
    found = classify(
        description,
        rules=rules,
        taxonomy=taxonomy,
        history=history,
    )
    objects = objects or load_objects()
    classification = found.get("classificacao")
    return {
        **found,
        "objeto_operacional": objects.get(
            classification
        ),
        "confianca": None,
        "motivo": (
            found.get("causa_padrao")
            or found.get("reason_code")
        ),
    }


def build_suggestions(
    descriptions: pd.Series,
    history: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Interface mantida para o backfill e o main.py."""
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
    return pd.DataFrame(
        rows,
        index=descriptions.index,
    )


def evaluate(
    history: pd.DataFrame,
    dictionary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dictionary = dictionary or load_dictionary()
    rows: list[dict[str, Any]] = []

    for _, record in history.iterrows():
        actual = _clean(
            record.get("Classificação")
        )
        if not actual or actual == "#N/A":
            continue

        result = classify(
            record.get("Descrição detalhada"),
            rules=dictionary,
        )
        rows.append(
            {
                "real": actual,
                "motor": result.get(
                    "classificacao"
                ),
                "status": result.get("status"),
                "intencao": result.get(
                    "intencao_id"
                ),
            }
        )

    frame = pd.DataFrame(
        rows,
        columns=[
            "real",
            "motor",
            "status",
            "intencao",
        ],
    )
    answered = frame[
        frame["motor"].notna()
    ]
    correct = int(
        (
            answered["real"]
            == answered["motor"]
        ).sum()
    )

    return {
        "total": len(frame),
        "com_resposta": len(answered),
        "sem_correspondencia": int(
            (
                frame["status"]
                == STATUS_UNMATCHED
            ).sum()
        ),
        "ambiguos": int(
            (
                frame["status"]
                == STATUS_AMBIGUOUS
            ).sum()
        ),
        "acertos": correct,
        "acuracia_entre_respostas": (
            round(correct / len(answered), 4)
            if len(answered)
            else None
        ),
    }


def main() -> None:
    dictionary = load_dictionary()
    problems = validate_dictionary(dictionary)

    intent_count = len(
        dictionary["intencoes"]
    )

    canonical_cause_count = len(
        dictionary.get("causas", {})
    )

    cause_alias_count = len(
        dictionary.get("aliases_causas", {})
    )

    signature_count = sum(
        len(item.get("assinaturas", []))
        for item in dictionary["intencoes"]
    )

    print(
        f"Intenções no dicionário: {intent_count}"
    )
    print(
        f"Causas canônicas: {canonical_cause_count}"
    )
    print(
        f"Aliases de causas: {cause_alias_count}"
    )
    print(
        f"Assinaturas no dicionário: {signature_count}"
    )
    print(
        f"Problemas no dicionário: {len(problems)}"
    )

    for problem in problems:
        print(f"- {problem}")


if __name__ == "__main__":
    main()