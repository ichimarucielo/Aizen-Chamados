
"""Texto -> normalização -> conceitos/padrões -> intenção -> causa padrão -> classificação oficial."""

from pathlib import Path
import re
import unicodedata

import pandas as pd
import yaml

from extract import load_compilado_sheet
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

TEMPLATE_PATH = (
    BASE_DIR
    / "data"
    / "input"
    / "plano_n2_template.xlsx"
)


# ---------------------------------------------------------------------------
# NORMALIZAÇÃO
# ---------------------------------------------------------------------------

def normalize_text(text) -> str:
    if pd.isna(text):
        return ""

    value = unicodedata.normalize(
        "NFKD",
        normalize_description(str(text)).lower(),
    )

    value = "".join(
        char
        for char in value
        if not unicodedata.combining(char)
    )

    # ------------------------------------------------------------------
    # 1. Normaliza números associados a conceitos relevantes.
    #    Faz isso ANTES de transformar "notas fiscais" em "nf".
    # ------------------------------------------------------------------

    # 2 notas fiscais -> duas notas fiscais
    value = re.sub(
        r"\b2\s+notas?\s+fiscais?\b",
        "duas notas fiscais",
        value,
    )

    # 3 notas fiscais -> tres notas fiscais
    value = re.sub(
        r"\b3\s+notas?\s+fiscais?\b",
        "tres notas fiscais",
        value,
    )

    value = re.sub(
    r"\b3\s+notas?\b",
    "tres notas",
    value,
    )

    # 4+ notas fiscais
    for number, word in {
        "4": "quatro",
        "5": "cinco",
        "6": "seis",
        "7": "sete",
        "8": "oito",
        "9": "nove",
    }.items():
        value = re.sub(
            rf"\b{number}\s+notas?\s+fiscais?\b",
            f"{word} notas fiscais",
            value,
        )

    # Números associados a boletos.
    for number, word in {
        "2": "dois",
        "3": "tres",
        "4": "quatro",
        "5": "cinco",
        "6": "seis",
        "7": "sete",
        "8": "oito",
        "9": "nove",
    }.items():
        value = re.sub(
            rf"\b{number}\b(?=\s+boletos?)",
            word,
            value,
        )

    # ------------------------------------------------------------------
    # 2. Unifica variações de nota fiscal.
    # ------------------------------------------------------------------

    value = re.sub(
        r"\bnotas?\s+fisc(?:al|ais)\b"
        r"|\bnotas?\b"
        r"|\bnf'?s\b"
        r"|\bnfs\b",
        " nf ",
        value,
    )

    # ------------------------------------------------------------------
    # 3. Normaliza e-mail.
    # ------------------------------------------------------------------

    value = re.sub(
        r"[\w.-]+@[\w.-]+\.\w+",
        " email ",
        value,
    )

    # ------------------------------------------------------------------
    # 4. Limpeza geral.
    # ------------------------------------------------------------------

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    ).strip()

    value = re.sub(
        r"\be\s+mail\b",
        "email",
        value,
    )

    return value

# ---------------------------------------------------------------------------
# CARGA DE CONFIGURAÇÃO
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(
        path.read_text(encoding="utf-8")
    )


def load_dictionary(
    path: Path = DICTIONARY_PATH,
) -> dict:
    dictionary = _load_yaml(path)

    allowed = set(
        dictionary["classes_permitidas"]
    )

    seen_ids = set()
    cause_classes = {}

    for intent in dictionary["intencoes"]:
        intent_id = intent["id"]

        if intent_id in seen_ids:
            raise ValueError(
                f"ID de intenção duplicado: {intent_id}"
            )

        seen_ids.add(intent_id)

        if intent["classificacao"] not in allowed:
            raise ValueError(
                f"Classificação fora do contrato em "
                f"{intent_id}: "
                f"{intent['classificacao']}"
            )

        cause = intent["causa_padrao"]

        previous = cause_classes.setdefault(
            cause,
            intent["classificacao"],
        )

        if previous != intent["classificacao"]:
            raise ValueError(
                f"Causa padrão '{cause}' aponta "
                "para mais de uma classificação."
            )

    return dictionary


def load_taxonomy(
    path: Path = DICTIONARY_PATH,
) -> dict:
    """Mapa causa padrão -> classificação oficial, derivado do dicionário."""
    return {
        intent["causa_padrao"]: intent["classificacao"]
        for intent in load_dictionary(path)["intencoes"]
    }


def load_objects(
    path: Path = TAXONOMY_PATH,
) -> dict:
    return _load_yaml(path)[
        "objetos_operacionais"
    ]


def load_rules(
    path: Path = DICTIONARY_PATH,
    include_draft: bool = False,
) -> dict:
    """Compatibilidade: expõe intenções indexadas por ID, sem status/score."""
    return {
        intent["id"]: intent
        for intent in load_dictionary(path)["intencoes"]
    }


def validate_dictionary(
    dictionary: dict | None = None,
) -> list[str]:
    dictionary = (
        dictionary
        or load_dictionary()
    )

    allowed = set(
        dictionary["classes_permitidas"]
    )

    problems = []
    ids = set()
    cause_classes = {}

    for intent in dictionary["intencoes"]:
        intent_id = intent["id"]

        if intent_id in ids:
            problems.append(
                f"ID duplicado: {intent_id}"
            )

        ids.add(intent_id)

        if intent["classificacao"] not in allowed:
            problems.append(
                f"Classe fora do contrato: "
                f"{intent_id}"
            )

        previous = cause_classes.setdefault(
            intent["causa_padrao"],
            intent["classificacao"],
        )

        if previous != intent["classificacao"]:
            problems.append(
                "Causa padrão com classes "
                f"conflitantes: {intent['causa_padrao']}"
            )

        if not intent.get("padroes"):
            problems.append(
                f"Intenção sem padrões: {intent_id}"
            )

    for rule in dictionary.get(
        "precedencia",
        [],
    ):
        for intent_id in [
            rule["preferir"],
            *rule.get("sobre", []),
        ]:
            if intent_id not in ids:
                problems.append(
                    "Precedência aponta para "
                    f"intenção inexistente: {intent_id}"
                )

    # A camada conceitual é opcional nesta primeira etapa.
    # Quando presente, validamos apenas a estrutura mínima, sem
    # impor uma ontologia rígida ao projeto.
    concepts = dictionary.get("conceitos", {})
    if concepts is not None and not isinstance(concepts, dict):
        problems.append(
            "A seção 'conceitos' deve ser um mapa conceito -> padrões."
        )

    if isinstance(concepts, dict):
        for concept_id, definition in concepts.items():
            if not str(concept_id).strip():
                problems.append(
                    "Conceito com ID vazio."
                )

            if not _concept_patterns(
                concepts,
                concept_id,
            ):
                problems.append(
                    f"Conceito sem padrões: {concept_id}"
                )

    fallback_classes = dictionary.get(
        "classificacoes_fallback",
        [],
    )

    if fallback_classes is not None and not isinstance(
        fallback_classes,
        list,
    ):
        problems.append(
            "A seção 'classificacoes_fallback' deve ser uma lista."
        )
    else:
        fallback_ids = set()
        fallback_causes = set()

        for fallback in fallback_classes:
            if not isinstance(fallback, dict):
                problems.append(
                    "Fallback de classificação inválido: esperado objeto YAML."
                )
                continue

            fallback_id = fallback.get("id")
            classification = fallback.get("classificacao")
            cause = fallback.get("causa_padrao")
            requirements = fallback.get("conceitos", [])

            if not fallback_id:
                problems.append("Fallback de classificação sem ID.")
            elif fallback_id in fallback_ids:
                problems.append(
                    f"ID de fallback duplicado: {fallback_id}"
                )
            else:
                fallback_ids.add(fallback_id)

            if classification not in allowed:
                problems.append(
                    f"Fallback fora do contrato: {fallback_id or '<sem id>'}"
                )

            if not cause:
                problems.append(
                    f"Fallback sem causa padrão: {fallback_id or '<sem id>'}"
                )
            elif cause in fallback_causes:
                problems.append(
                    f"Causa padrão de fallback duplicada: {cause}"
                )
            else:
                fallback_causes.add(cause)

            if not requirements:
                problems.append(
                    f"Fallback sem conceitos: {fallback_id or '<sem id>'}"
                )

            for concept_id in requirements:
                if concept_id not in concepts:
                    problems.append(
                        "Fallback aponta para conceito inexistente: "
                        f"{concept_id}"
                    )

    conceptual_rules = dictionary.get(
        "regras_conceituais",
        [],
    )

    if conceptual_rules is not None and not isinstance(
        conceptual_rules,
        list,
    ):
        problems.append(
            "A seção 'regras_conceituais' deve ser uma lista."
        )
    else:
        rule_ids = set()
        allowed_scopes = {"local", "texto"}

        for rule in conceptual_rules:
            if not isinstance(rule, dict):
                problems.append(
                    "Regra conceitual inválida: esperado objeto YAML."
                )
                continue

            rule_id = rule.get("id")
            intent_id = rule.get("intencao")
            requirements = rule.get("requisitos", [])
            scope = rule.get("escopo", "local")

            if not rule_id:
                problems.append(
                    "Regra conceitual sem ID."
                )
            elif rule_id in rule_ids:
                problems.append(
                    f"ID de regra conceitual duplicado: {rule_id}"
                )
            else:
                rule_ids.add(rule_id)

            if scope not in allowed_scopes:
                problems.append(
                    f"Escopo conceitual inválido em {rule_id or '<sem id>'}: {scope}"
                )

            if not intent_id:
                problems.append(
                    f"Regra conceitual sem intenção: {rule_id or '<sem id>'}"
                )
            elif intent_id not in ids:
                problems.append(
                    "Regra conceitual aponta para intenção "
                    f"inexistente: {intent_id}"
                )

            if not requirements:
                problems.append(
                    f"Regra conceitual sem requisitos: "
                    f"{rule_id or '<sem id>'}"
                )

            for requirement in requirements:
                for concept_id in _normalize_concept_requirement(
                    requirement
                ):
                    if concept_id not in concepts:
                        problems.append(
                            "Regra conceitual aponta para conceito "
                            f"inexistente: {concept_id}"
                        )

    return sorted(set(problems))


# ---------------------------------------------------------------------------
# MATCHING
# ---------------------------------------------------------------------------

def _contains_phrase(
    text: str,
    phrase: str,
) -> bool:
    normalized = normalize_text(
        phrase
    )

    return (
        bool(normalized)
        and f" {normalized} "
        in f" {text} "
    )


def _matches_pattern(
    text: str,
    pattern: str,
) -> bool:
    parts = [
        part.strip()
        for part in pattern.split("+")
    ]

    return all(
        _contains_phrase(text, part)
        for part in parts
    )


# ---------------------------------------------------------------------------
# CONCEITOS
# ---------------------------------------------------------------------------

def _concept_patterns(concepts: dict, concept_id: str) -> list[str]:
    """Retorna os padrões de texto associados a um conceito."""
    definition = concepts.get(concept_id, [])

    if isinstance(definition, dict):
        patterns = (
            definition.get("padroes")
            or definition.get("patterns")
            or definition.get("termos")
            or []
        )
    else:
        patterns = definition

    if isinstance(patterns, str):
        patterns = [patterns]

    return [
        str(pattern).strip()
        for pattern in patterns
        if str(pattern).strip()
    ]


def _normalized_clauses(text: str) -> list[str]:
    """Divide o texto em blocos operacionais sem destruir a lógica de normalização."""
    raw = "" if pd.isna(text) else str(text)
    chunks = re.split(r"[;\n\r.!?:]+", raw)
    clauses = [normalize_text(chunk) for chunk in chunks]
    return [clause for clause in clauses if clause]


def _concept_occurrences(
    text: str,
    dictionary: dict,
) -> dict[str, list[dict]]:
    """Extrai ocorrências de conceitos com posição local e global."""
    concepts = dictionary.get("conceitos", {})
    occurrences: dict[str, list[dict]] = {}
    global_offset = 0

    for clause_index, clause in enumerate(_normalized_clauses(text)):
        tokens = clause.split()

        for concept_id in concepts:
            for pattern in _concept_patterns(concepts, concept_id):
                pattern_tokens = normalize_text(pattern).split()
                if not pattern_tokens:
                    continue

                width = len(pattern_tokens)
                for start in range(max(0, len(tokens) - width + 1)):
                    if tokens[start:start + width] != pattern_tokens:
                        continue

                    occurrences.setdefault(concept_id, []).append(
                        {
                            "pattern": pattern,
                            "clause": clause_index,
                            "start": start,
                            "end": start + width - 1,
                            "global_start": global_offset + start,
                            "global_end": global_offset + start + width - 1,
                        }
                    )

        global_offset += len(tokens)

    return occurrences


def _concept_requirement_occurrences(
    requirement,
    occurrences: dict[str, list[dict]],
) -> list[dict]:
    """Obtém ocorrências de qualquer alternativa de um requisito."""
    items = []
    for concept_id in _normalize_concept_requirement(requirement):
        for occurrence in occurrences.get(concept_id, []):
            items.append(
                {
                    **occurrence,
                    "concept_id": concept_id,
                }
            )
    return items


def _coordinated_distinct_targets(
    text: str,
    dictionary: dict,
    max_distance: int = 8,
) -> bool:
    """Detecta uma ação explícita aplicada a mais de um grupo de classificação."""
    occurrences = _active_concept_occurrences(text, dictionary)
    if not occurrences:
        return False

    fallback_candidates = _fallback_candidates_from_concepts(
        occurrences,
        dictionary,
    )
    if not fallback_candidates:
        return False

    class_by_object = {}
    for candidate in fallback_candidates:
        classification = candidate["definition"].get("classificacao")
        for evidence in candidate["evidence"]:
            class_by_object[
                (
                    evidence["clause"],
                    evidence["start"],
                )
            ] = classification

    # Reconstroi os tokens por cláusula para validar a conjunção entre objetos.
    clauses = _normalized_clauses(text)

    action_occurrences = []
    for concept_id, concept_occurrences in occurrences.items():
        if concept_id.startswith("ACAO_"):
            action_occurrences.extend(concept_occurrences)

    if not action_occurrences:
        return False

    all_objects = []
    for concept_id, concept_occurrences in occurrences.items():
        if not concept_id.startswith("OBJ_"):
            continue
        for occurrence in concept_occurrences:
            classification = class_by_object.get(
                (
                    occurrence["clause"],
                    occurrence["start"],
                )
            )
            if classification:
                all_objects.append(
                    {
                        **occurrence,
                        "classification": classification,
                    }
                )

    for action in action_occurrences:
        same_clause = [
            obj
            for obj in all_objects
            if obj["clause"] == action["clause"]
            and abs(obj["start"] - action["start"]) <= max_distance
        ]

        if len(same_clause) < 2:
            continue

        nearest = min(
            same_clause,
            key=lambda obj: abs(
                obj["start"] - action["start"]
            ),
        )

        related = [nearest]
        clause = clauses[action["clause"]]
        for obj in same_clause:
            if obj is nearest:
                continue

            left = min(nearest["start"], obj["start"])
            right = max(nearest["start"], obj["start"])
            between = clause.split()[left + 1:right]

            if any(token in {"e", "ou"} for token in between):
                related.append(obj)

        if len({obj["classification"] for obj in related}) > 1:
            return True

    return False


def _rule_matches_by_local_scope(
    rule: dict,
    occurrences: dict[str, list[dict]],
    max_action_object_distance: int = 8,
    max_text_distance: int = 80,
    text: str = "",
) -> bool:
    """
    Avalia uma regra conceitual por escopo determinístico.

    ``local`` (padrão): ação, objeto e contextos ficam no mesmo bloco.
    ``texto``: conceitos podem aparecer em blocos diferentes, mas ação e objeto
    ainda precisam estar próximos quando ambos existem.

    Isso permite regras reutilizáveis sem depender de frases completas, mantendo
    a decisão conservadora para evitar associações acidentais.
    """
    requirements = rule.get("requisitos", [])
    if not requirements:
        return False

    groups = [
        _concept_requirement_occurrences(requirement, occurrences)
        for requirement in requirements
    ]

    if any(not group for group in groups):
        return False

    scope = rule.get("escopo", "local")
    action_indexes = [
        index
        for index, requirement in enumerate(requirements)
        if any(
            concept_id.startswith("ACAO_")
            for concept_id in _normalize_concept_requirement(requirement)
        )
    ]
    object_indexes = [
        index
        for index, requirement in enumerate(requirements)
        if any(
            concept_id.startswith("OBJ_")
            for concept_id in _normalize_concept_requirement(requirement)
        )
    ]

    def same_scope(a: dict, b: dict) -> bool:
        if scope == "texto":
            return abs(a["global_start"] - b["global_start"]) <= max_text_distance
        return a["clause"] == b["clause"]

    # Regra composta apenas de objeto/contexto.
    if not action_indexes or not object_indexes:
        anchor_group = groups[0]

        for anchor in anchor_group:
            ok = True
            for group in groups[1:]:
                if not any(same_scope(anchor, occurrence) for occurrence in group):
                    ok = False
                    break
            if ok:
                return True

        return False

    action_occurrences = []
    for action_index in action_indexes:
        action_occurrences.extend(groups[action_index])

    required_object_ids = {
        concept_id
        for index in object_indexes
        for concept_id in _normalize_concept_requirement(requirements[index])
    }

    all_object_occurrences = []
    for concept_id, concept_occurrences in occurrences.items():
        if not concept_id.startswith("OBJ_"):
            continue
        all_object_occurrences.extend(
            {**occurrence, "concept_id": concept_id}
            for occurrence in concept_occurrences
        )

    for action in action_occurrences:
        candidates = []

        for obj in all_object_occurrences:
            if scope == "local":
                if obj["clause"] != action["clause"]:
                    continue
                distance = abs(action["start"] - obj["start"])
                if distance > max_action_object_distance:
                    continue
            else:
                distance = abs(action["global_start"] - obj["global_start"])
                if distance > max_text_distance:
                    continue

            candidates.append((distance, obj))

        if not candidates:
            continue

        nearest_distance = min(distance for distance, _ in candidates)
        nearest_objects = [
            obj
            for distance, obj in candidates
            if distance == nearest_distance
        ]

        associated_objects = list(nearest_objects)

        clause_tokens = _normalized_clauses(text) if text else []
        current_clause = (
            clause_tokens[action["clause"]]
            if action["clause"] < len(clause_tokens)
            else ""
        )
        current_tokens = current_clause.split()

        # Um único verbo pode atuar sobre dois objetos coordenados:
        # "cancelar NF e boleto". Não usamos apenas distância: entre o alvo
        # mais próximo e o segundo alvo precisa aparecer uma conjunção.
        for _, obj in candidates:
            if obj in associated_objects:
                continue

            if obj["start"] <= action["start"]:
                continue

            left = nearest_objects[0]["start"]
            right = obj["start"]
            if right - left > max_action_object_distance:
                continue

            tokens_between = current_tokens[left + 1:right]
            if any(token in {"e", "ou"} for token in tokens_between):
                associated_objects.append(obj)

        if not any(
            obj["concept_id"] in required_object_ids
            for obj in associated_objects
        ):
            continue

        # Contextos/requisitos adicionais devem acompanhar a relação ação +
        # objeto no mesmo escopo declarado pela regra.
        for index, group in enumerate(groups):
            if index in {action_indexes[0], object_indexes[0]}:
                continue

            if not any(same_scope(action, occurrence) for occurrence in group):
                break
        else:
            return True

    return False


def _concept_rule_is_contextual(
    text: str,
    rule: dict,
    occurrences: dict[str, list[dict]],
) -> bool:
    """Identifica regras presentes explicitamente como contexto."""
    markers = ("so contexto", "somente contexto", "apenas contexto")
    clauses = _normalized_clauses(text)
    if not clauses:
        return False

    requirements = rule.get("requisitos", [])
    groups = [
        _concept_requirement_occurrences(requirement, occurrences)
        for requirement in requirements
    ]
    if any(not group for group in groups):
        return False

    for clause_index, clause in enumerate(clauses):
        marker_positions = [clause.find(marker) for marker in markers if clause.find(marker) >= 0]
        if not marker_positions:
            continue

        marker_position = min(marker_positions)
        prefix = clause[:marker_position]

        # A regra só é contextual quando seus conceitos operacionais
        # aparecem no próprio bloco imediatamente anterior ao marcador.
        all_in_clause = True
        for group in groups:
            if not any(occurrence["clause"] == clause_index for occurrence in group):
                all_in_clause = False
                break

        if not all_in_clause:
            continue

        for group in groups:
            if not any(
                occurrence["clause"] == clause_index
                and normalize_text(occurrence["pattern"]) in prefix
                for occurrence in group
            ):
                all_in_clause = False
                break

        if all_in_clause:
            return True

    return False


def _pattern_is_contextual(
    text: str,
    pattern: str,
) -> bool:
    """Verifica se um padrão textual está no bloco declarado como contexto."""
    markers = ("so contexto", "somente contexto", "apenas contexto")
    raw = "" if pd.isna(text) else str(text)

    for chunk in re.split(r"[;\n\r.!?:]+", raw):
        clause = normalize_text(chunk)
        if not clause:
            continue

        positions = [clause.find(marker) for marker in markers if clause.find(marker) >= 0]
        if not positions:
            continue

        marker_position = min(positions)
        prefix = clause[:marker_position]
        normalized_pattern = normalize_text(pattern.replace("+", " "))

        if normalized_pattern and normalized_pattern in prefix:
            return True

    return False


def extract_concepts(
    text: str,
    dictionary: dict,
) -> dict[str, list[str]]:
    """
    Extrai conceitos semânticos do texto de forma determinística.

    O YAML pode declarar:

        conceitos:
          ACAO_CANCELAR:
            - cancelar
            - cancelamento
          OBJ_NF:
            - nota fiscal
            - nf

    O retorno é:

        {
            "ACAO_CANCELAR": ["cancelar"],
            "OBJ_NF": ["nf"],
        }

    Conceitos isolados não geram uma intenção específica. A classificação genérica
    pode ser usada quando o dicionário declarar um fallback de grupo; intenções
    específicas continuam dependendo de regras conceituais ou padrões legados.
    """
    normalized = normalize_text(text)

    if not normalized:
        return {}

    concepts = dictionary.get("conceitos", {})
    extracted: dict[str, list[str]] = {}

    for concept_id in concepts:
        found = [
            pattern
            for pattern in _concept_patterns(concepts, concept_id)
            if _contains_phrase(normalized, pattern)
        ]

        if found:
            extracted[concept_id] = found

    return extracted


def _normalize_concept_requirement(requirement) -> list[str]:
    """
    Normaliza um requisito de regra.

    Pode ser:
        - ACAO_CANCELAR
        - [ACAO_CANCELAR, ACAO_SUBSTITUIR]

    No segundo caso, qualquer um dos conceitos da lista satisfaz
    o requisito.
    """
    if isinstance(requirement, str):
        return [requirement.strip()] if requirement.strip() else []

    if isinstance(requirement, (list, tuple, set)):
        return [
            str(item).strip()
            for item in requirement
            if str(item).strip()
        ]

    return []


def _concept_rule_matches(
    rule: dict,
    concepts: dict[str, list[str]],
) -> bool:
    """Avalia uma regra conceitual contra os conceitos extraídos."""
    requirements = rule.get("requisitos", [])

    if not requirements:
        return False

    for requirement in requirements:
        alternatives = _normalize_concept_requirement(requirement)

        if not alternatives:
            return False

        if not any(
            concept_id in concepts
            for concept_id in alternatives
        ):
            return False

    # Exclusões podem ser IDs de conceito ou padrões de texto previamente
    # extraídos. Como a função recebe conceitos, a forma mais segura aqui
    # é tratar exclusões como IDs de conceito.
    exclusions = rule.get("exclusoes", [])

    for exclusion in exclusions:
        if isinstance(exclusion, str) and exclusion.strip() in concepts:
            return False

    return True


def _concept_rule_matches_for_text(
    text: str,
    dictionary: dict,
) -> tuple[list[dict], dict[str, list[str]], dict[str, str]]:
    """
    Retorna intenções encontradas pelas regras conceituais.

    Retorno:
        matches
        matched_patterns
        matched_rules

    ``matched_patterns`` usa uma representação legível dos conceitos
    encontrados, permitindo que a camada existente de precedência/contexto
    continue funcionando.
    """
    concepts = extract_concepts(text, dictionary)
    occurrences = _concept_occurrences(text, dictionary)

    if not concepts:
        return [], {}, {}

    intents_by_id = {
        intent["id"]: intent
        for intent in dictionary.get("intencoes", [])
    }

    matches = []
    matched_patterns: dict[str, list[str]] = {}
    matched_rules: dict[str, str] = {}

    for rule in dictionary.get("regras_conceituais", []):
        if not isinstance(rule, dict):
            continue

        intent_id = rule.get("intencao")
        if not intent_id or intent_id not in intents_by_id:
            continue

        if not _rule_matches_by_local_scope(
            rule,
            occurrences,
            text=text,
        ):
            continue

        if _concept_rule_is_contextual(text, rule, occurrences):
            continue

        # A relação entre ação e objeto já foi validada pela camada de
        # escopo local acima. Aqui só preservamos as exclusões declaradas
        # pela regra.
        if any(
            isinstance(exclusion, str)
            and exclusion.strip() in concepts
            for exclusion in rule.get("exclusoes", [])
        ):
            continue

        intent = intents_by_id[intent_id]

        if intent_id not in {
            item["id"]
            for item in matches
        }:
            matches.append(intent)

        requirements = rule.get("requisitos", [])
        concept_labels = []

        for requirement in requirements:
            alternatives = _normalize_concept_requirement(requirement)
            selected = next(
                (
                    concept_id
                    for concept_id in alternatives
                    if concept_id in concepts
                ),
                None,
            )

            if selected:
                concept_labels.append(selected)

        synthetic_pattern = " + ".join(concept_labels)

        if synthetic_pattern:
            matched_patterns.setdefault(intent_id, []).append(
                synthetic_pattern
            )

        matched_rules.setdefault(
            intent_id,
            str(rule.get("id") or intent_id),
        )

    return matches, matched_patterns, matched_rules


# ---------------------------------------------------------------------------
# FALLBACK DE CLASSIFICAÇÃO
# ---------------------------------------------------------------------------

def _fallback_definitions(
    dictionary: dict,
) -> list[dict]:
    """Retorna os classificadores genéricos declarados no YAML."""
    return [
        definition
        for definition in dictionary.get(
            "classificacoes_fallback",
            [],
        )
        if isinstance(definition, dict)
    ]


def _active_concept_occurrences(
    text: str,
    dictionary: dict,
) -> dict[str, list[dict]]:
    """Retorna apenas conceitos que não aparecem explicitamente como contexto."""
    occurrences = _concept_occurrences(text, dictionary)
    clauses = _normalized_clauses(text)
    markers = ("so contexto", "somente contexto", "apenas contexto")

    active: dict[str, list[dict]] = {}

    for concept_id, concept_occurrences in occurrences.items():
        for occurrence in concept_occurrences:
            clause_index = occurrence["clause"]
            if clause_index >= len(clauses):
                continue

            clause = clauses[clause_index]
            marker_tokens = []

            for marker in markers:
                marker_index = clause.find(marker)
                if marker_index >= 0:
                    marker_tokens.append(
                        len(clause[:marker_index].split())
                    )

            # Se a ocorrência estiver antes de um marcador de contexto no
            # próprio bloco, ela é considerada contextual.
            if marker_tokens and occurrence["start"] < min(marker_tokens):
                continue

            active.setdefault(
                concept_id,
                [],
            ).append(occurrence)

    return active


def _fallback_candidates_from_concepts(
    active_occurrences: dict[str, list[dict]],
    dictionary: dict,
) -> list[dict]:
    """Encontra classes genéricas sustentadas por conceitos ativos."""
    candidates = []

    for definition in _fallback_definitions(dictionary):
        concept_ids = {
            str(concept_id).strip()
            for concept_id in definition.get("conceitos", [])
            if str(concept_id).strip()
        }

        evidence = []
        for concept_id in concept_ids:
            for occurrence in active_occurrences.get(concept_id, []):
                evidence.append(
                    {
                        **occurrence,
                        "concept_id": concept_id,
                    }
                )

        if not evidence:
            continue

        candidates.append(
            {
                "definition": definition,
                "evidence": evidence,
            }
        )

    return candidates


def _nearest_fallback_class_for_action(
    action_occurrence: dict,
    candidates: list[dict],
    max_distance: int = 8,
) -> str | None:
    """Associa uma ação ao objeto genérico mais próximo na mesma cláusula."""
    nearest = []

    for candidate in candidates:
        definition = candidate["definition"]
        classification = definition.get("classificacao")

        for evidence in candidate["evidence"]:
            if evidence["clause"] != action_occurrence["clause"]:
                continue

            distance = abs(
                evidence["start"]
                - action_occurrence["start"]
            )

            if distance <= max_distance:
                nearest.append(
                    (
                        distance,
                        classification,
                    )
                )

    if not nearest:
        return None

    nearest_distance = min(
        distance
        for distance, _ in nearest
    )

    classifications = {
        classification
        for distance, classification in nearest
        if distance == nearest_distance
    }

    return (
        next(iter(classifications))
        if len(classifications) == 1
        else None
    )


def _generic_classification_fallback(
    text: str,
    dictionary: dict,
) -> dict | None:
    """
    Resolve uma classificação oficial sem exigir uma causa específica.

    Regras: 
        1. Se os conceitos apontarem para uma única classificação, usa essa
           classificação mesmo sem verbo explícito. Isso permite casos como
           "boleto", "NF" ou "cobrança".
        2. Se houver mais de uma classificação, tenta associar uma ação ao
           objeto/grupo mais próximo na mesma cláusula.
        3. Se houver mais de uma classificação e nenhuma ação conseguir
           resolver o alvo, não inventa uma escolha.
        4. Texto contendo somente vários objetos contextuais, sem ação,
           permanece sem correspondência em vez de virar ambíguo.
    """
    active_occurrences = _active_concept_occurrences(
        text,
        dictionary,
    )

    if not active_occurrences:
        return None

    candidates = _fallback_candidates_from_concepts(
        active_occurrences,
        dictionary,
    )

    if not candidates:
        return None

    by_class: dict[str, list[dict]] = {}
    for candidate in candidates:
        classification = candidate["definition"].get("classificacao")
        if classification:
            by_class.setdefault(classification, []).append(candidate)

    classifications = list(by_class)
    if not classifications:
        return None

    action_occurrences = []
    for concept_id, occurrences in active_occurrences.items():
        if concept_id.startswith("ACAO_"):
            action_occurrences.extend(occurrences)

    # Uma única classificação sustentada pelos conceitos é suficiente para
    # o fallback genérico, mesmo que não exista uma ação explícita.
    if len(classifications) == 1:
        selected_class = classifications[0]
        selected = by_class[selected_class][0]
        definition = selected["definition"]

        evidence_patterns = [
            f"{item['concept_id']}: {item['pattern']}"
            for item in selected["evidence"]
        ]

        return {
            "status": "Sugerida",
            "intencao_id": definition["id"],
            "intencao_identificada": definition.get(
                "intencao",
                definition.get("id"),
            ),
            "causa_identificada": list(
                dict.fromkeys(evidence_patterns)
            ),
            "causa_padrao": definition.get("causa_padrao"),
            "classificacao": selected_class,
            "regra": definition.get("id"),
            "candidatas": [definition.get("id")],
            "ambiguo": False,
            "origem_classificacao": "fallback_conceitual",
        }

    # Mais de um grupo só pode ser resolvido quando existe uma ação explícita
    # que consiga ser associada de forma determinística a um único grupo.
    if action_occurrences:
        linked_classes = []
        for action in action_occurrences:
            linked = _nearest_fallback_class_for_action(
                action,
                candidates,
            )
            if linked:
                linked_classes.append(linked)

        linked_unique = list(dict.fromkeys(linked_classes))

        if len(linked_unique) == 1:
            selected_class = linked_unique[0]
            selected = by_class[selected_class][0]
            definition = selected["definition"]

            evidence_patterns = [
                f"{item['concept_id']}: {item['pattern']}"
                for item in selected["evidence"]
            ]

            return {
                "status": "Sugerida",
                "intencao_id": definition["id"],
                "intencao_identificada": definition.get(
                    "intencao",
                    definition.get("id"),
                ),
                "causa_identificada": list(
                    dict.fromkeys(evidence_patterns)
                ),
                "causa_padrao": definition.get("causa_padrao"),
                "classificacao": selected_class,
                "regra": definition.get("id"),
                "candidatas": [definition.get("id")],
                "ambiguo": False,
                "origem_classificacao": "fallback_conceitual",
            }

        # Há múltiplos grupos e uma ou mais ações, mas nenhuma associação
        # determinística suficiente. Mantém a ambiguidade explícita.
        return {
            "status": "Ambígua",
            "intencao_id": None,
            "intencao_identificada": None,
            "causa_identificada": [],
            "causa_padrao": None,
            "classificacao": None,
            "regra": None,
            "candidatas": [
                candidate["definition"].get("id")
                for candidate in candidates
                if candidate["definition"].get("id")
            ],
            "ambiguo": True,
            "classificacoes": classifications,
            "origem_classificacao": "fallback_conceitual",
        }

    # Vários grupos, mas nenhum pedido operacional explícito. Não é
    # ambiguidade operacional; é apenas informação contextual insuficiente.
    return None


# ---------------------------------------------------------------------------
# PRECEDÊNCIA / CONTEXTO
# ---------------------------------------------------------------------------

def _pattern_is_explicit_action(
    pattern: str,
) -> bool:
    """
    Identifica padrões que representam uma ação operacional explícita.

    Exemplos:
        cancelar nf
        cancelar contrato
        corrigir boleto
        alterar vencimento
        prorrogar pagamento
        consultar pagamentos
    """

    normalized = normalize_text(
        pattern
    )

    if normalized.startswith("acao ") or " acao " in f" {normalized} ":
        return True

    action_markers = (
        "cancelar",
        "cancelamento",
        "encerrar",
        "encerramento",
        "reemitir",
        "reemissao",
        "substituir",
        "substituicao",
        "prorrogar",
        "prorrogacao",
        "alterar",
        "alteracao",
        "enviar",
        "reenvio",
        "solicitar",
        "solicitacao",
        "corrigir",
        "correcao",
        "incluir",
        "trocar",
        "mudando",
        "congelar",
        "congelamento",
        "renovacao",
        "confirmar",
        "consultar",
        "consulta",
        "verificar",
        "esclarecer",
        "entender",
        "contestar",
        "contestacao",
    )

    return any(
        marker in normalized
        for marker in action_markers
    )


def _remove_contextual_matches(
    matches: list[dict],
    matched_patterns: dict[str, list[str]],
    text: str,
) -> list[dict]:
    """
    Remove uma intenção quando o próprio texto informa que ela
    aparece apenas como contexto.

    Exemplo:
        congelar o contrato; cancelamento de notas é só contexto
    """

    normalized_text = normalize_text(text)

    context_markers = (
        "so contexto",
        "somente contexto",
        "apenas contexto",
    )

    contextual_ids = set()

    for marker in context_markers:
        marker_position = normalized_text.find(marker)

        if marker_position < 0:
            continue

        # Tudo que aparece antes de "só contexto" pode ser
        # a informação explicitamente tratada como contexto.
        prefix = normalized_text[:marker_position]

        for intent in matches:
            intent_id = intent["id"]

            for pattern in matched_patterns.get(
                intent_id,
                [],
            ):
                normalized_pattern = normalize_text(
                    pattern.replace("+", " ")
                )

                if not normalized_pattern:
                    continue

                if normalized_pattern in prefix:
                    contextual_ids.add(intent_id)

                elif _pattern_is_contextual(
                    text,
                    pattern,
                ):
                    contextual_ids.add(intent_id)

    if not contextual_ids:
        return matches

    remaining = [
        intent
        for intent in matches
        if intent["id"] not in contextual_ids
    ]

    return remaining or matches


def _apply_precedence(
    matches: list[dict],
    dictionary: dict,
    matched_patterns: dict[str, list[str]] | None = None,
    text: str = "",
) -> list[dict]:
    """Aplica precedência determinística e preserva conflitos sem regra."""

    if not matches:
        return matches

    matched_patterns = matched_patterns or {}

    matches = _remove_contextual_matches(
        matches,
        matched_patterns,
        text,
    )

    # Se uma mesma ação foi aplicada a objetos coordenados de grupos
    # diferentes, existe mais de um alvo operacional real. Precedência não
    # deve esconder um dos alvos e transformar o pedido em falso singular.
    if _coordinated_distinct_targets(text, dictionary):
        return matches

    # Primeiro resolve precedências documentadas no YAML. Isso é importante
    # quando duas ações de classes diferentes aparecem no mesmo pedido, mas o
    # próprio dicionário documenta qual intenção domina.
    remaining = {
        intent["id"]: intent
        for intent in matches
    }

    for rule in dictionary.get("precedencia", []):
        preferred = rule.get("preferir")
        if preferred not in remaining:
            continue

        for lower_priority in rule.get("sobre", []):
            remaining.pop(lower_priority, None)

    matches = list(remaining.values())

    if len(matches) <= 1:
        return matches

    normalized_text = normalize_text(text)
    context_markers = (
        "so contexto",
        "somente contexto",
        "apenas contexto",
    )
    has_context_marker = any(
        marker in normalized_text
        for marker in context_markers
    )

    # Depois da precedência, duas intenções explícitas de classes diferentes
    # continuam sendo conflito real -> ambígua.
    explicit_intents = []
    for intent in matches:
        patterns = matched_patterns.get(intent["id"], [])
        if any(
            _pattern_is_explicit_action(pattern)
            for pattern in patterns
        ):
            explicit_intents.append(intent)

    if len(explicit_intents) > 1 and not has_context_marker:
        classes = {
            intent.get("classificacao")
            for intent in explicit_intents
        }
        if len(classes) > 1:
            return matches

    # Uma única ação explícita pode desempatar múltiplas evidências da mesma
    # classe, sem inventar uma escolha entre classes diferentes.
    if len(explicit_intents) == 1:
        return explicit_intents

    return matches


# ---------------------------------------------------------------------------
# IDENTIFICAÇÃO DA INTENÇÃO
# ---------------------------------------------------------------------------

def identify_intent(
    description,
    dictionary: dict | None = None,
) -> dict:
    """Encontra intenções explícitas e deixa conflitos reais sem escolha arbitrária."""

    dictionary = (
        dictionary
        or load_dictionary()
    )

    text = normalize_text(
        description
    )

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
    matched_patterns: dict[str, list[str]] = {}
    matched_rules: dict[str, str] = {}

    # ------------------------------------------------------------------
    # 1. REGRAS CONCEITUAIS
    # ------------------------------------------------------------------
    conceptual_matches, conceptual_patterns, conceptual_rules = (
        _concept_rule_matches_for_text(
            text,
            dictionary,
        )
    )

    for intent in conceptual_matches:
        intent_id = intent["id"]
        matches.append(intent)
        matched_patterns[intent_id] = list(
            conceptual_patterns.get(
                intent_id,
                [],
            )
        )
        matched_rules[intent_id] = conceptual_rules.get(
            intent_id,
            intent_id,
        )

    # ------------------------------------------------------------------
    # 2. PADRÕES LEGADOS
    # ------------------------------------------------------------------
    for intent in dictionary["intencoes"]:
        found = [
            pattern
            for pattern in intent.get(
                "padroes",
                [],
            )
            if _matches_pattern(
                text,
                pattern,
            )
        ]

        if not found:
            continue

        if any(
            _matches_pattern(
                text,
                excluded,
            )
            for excluded in intent.get(
                "exclusoes",
                [],
            )
        ):
            continue

        intent_id = intent["id"]

        if intent_id not in {
            item["id"]
            for item in matches
        }:
            matches.append(intent)

        # Quando existe padrão legado explícito para a mesma intenção,
        # ele é a evidência textual principal. O conceito continua sendo
        # usado para decisão, mas não polui a saída operacional.
        matched_patterns[intent_id] = found

        matched_rules.setdefault(
            intent_id,
            intent_id,
        )

    # IMPORTANTE:
    # a variável correta é "matches".
    # O resultado da precedência precisa substituir
    # a lista original de matches.
    matches = _apply_precedence(
        matches,
        dictionary,
        matched_patterns,
        text,
    )

    if not matches:
        fallback = _generic_classification_fallback(
            text,
            dictionary,
        )

        if fallback is not None:
            return fallback

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

    causes = list(
        dict.fromkeys(
            intent["causa_padrao"]
            for intent in matches
        )
    )

    classes = list(
        dict.fromkeys(
            intent["classificacao"]
            for intent in matches
        )
    )

    unique_cause = (
        len(causes) == 1
    )

    unique_class = (
        len(classes) == 1
    )

    status = (
        "Sugerida"
        if unique_cause
        and unique_class
        else "Ambígua"
    )

    selected = (
        matches[0]
        if unique_cause
        else None
    )

    matched = []
    seen_patterns = set()

    for intent in matches:
        for pattern in matched_patterns.get(
            intent["id"],
            [],
        ):
            normalized_pattern = normalize_text(
                pattern.replace(
                    "+",
                    " ",
                )
            )

            if normalized_pattern in seen_patterns:
                continue

            seen_patterns.add(
                normalized_pattern
            )

            matched.append(
                pattern
            )

    return {
        "status": status,
        "intencao_id": (
            selected["id"]
            if selected
            else None
        ),
        "intencao_identificada": "; ".join(
            dict.fromkeys(
                intent["intencao"]
                for intent in matches
            )
        ),
        "causa_identificada": matched,
        "causa_padrao": (
            causes[0]
            if unique_cause
            else None
        ),
        "classificacao": (
            classes[0]
            if unique_class
            else None
        ),
        "regra": (
            matched_rules.get(
                selected["id"],
                selected["id"],
            )
            if selected
            else None
        ),
        "candidatas": [
            intent["id"]
            for intent in matches
        ],
        "ambiguo": status == "Ambígua",
    }


# ---------------------------------------------------------------------------
# COMPATIBILIDADE
# ---------------------------------------------------------------------------

def identify_cause(
    description,
    rules=None,
) -> dict:
    """Alias de compatibilidade para o passo novo de identificação da intenção."""
    return identify_intent(
        description,
        _dictionary_from_rules(rules),
    )


def _dictionary_from_rules(
    rules=None,
) -> dict:
    if rules is None:
        return load_dictionary()

    if (
        isinstance(rules, dict)
        and "intencoes" in rules
    ):
        return rules

    intents = (
        list(rules.values())
        if isinstance(rules, dict)
        else list(rules)
    )

    base = load_dictionary()

    return {
        **base,
        "intencoes": intents,
    }


# ---------------------------------------------------------------------------
# CAUSA CANÔNICA
# ---------------------------------------------------------------------------

def normalize_root_cause(
    identified: dict,
    dictionary: dict | None = None,
) -> dict:
    """Resolve a causa padrão no dicionário e deriva dela a classe oficial."""

    dictionary = (
        dictionary
        or load_dictionary()
    )

    cause = identified.get(
        "causa_padrao"
    )

    class_by_cause = {
        intent["causa_padrao"]:
            intent["classificacao"]
        for intent in dictionary["intencoes"]
    }

    for fallback in dictionary.get(
        "classificacoes_fallback",
        [],
    ):
        if not isinstance(fallback, dict):
            continue
        fallback_cause = fallback.get("causa_padrao")
        classification = fallback.get("classificacao")
        if fallback_cause and classification:
            class_by_cause[fallback_cause] = classification

    return {
        "causa_canonica": cause,
        "classificacao": class_by_cause.get(
            cause,
            identified.get(
                "classificacao"
            ),
        ),
    }


# ---------------------------------------------------------------------------
# API PRINCIPAL
# ---------------------------------------------------------------------------

def classify(
    description,
    rules=None,
    taxonomy=None,
) -> dict:
    """Descrição -> intenção -> causa padrão -> classificação oficial."""

    dictionary = _dictionary_from_rules(
        rules
    )

    identified = identify_intent(
        description,
        dictionary,
    )

    normalized = normalize_root_cause(
        identified,
        dictionary,
    )

    return {
        **identified,
        **normalized,
    }


def suggest(
    description,
    rules=None,
    taxonomy=None,
    objects: dict | None = None,
    stats: dict | None = None,
) -> dict:
    """Retorna uma classificação explicável; não pontua nem escolhe por score."""

    found = classify(
        description,
        rules,
        taxonomy,
    )

    objects = (
        objects
        or load_objects()
    )

    classification = found[
        "classificacao"
    ]

    return {
        **found,
        "objeto_operacional": objects.get(
            classification
        ),
        "confianca": None,
        "motivo": found.get(
            "intencao_identificada"
        ) or found.get(
            "causa_padrao"
        ) or found.get(
            "classificacao"
        ),
    }


def build_suggestions(
    descriptions: pd.Series,
    history: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Classifica Descrição detalhada; history fica na assinatura por compatibilidade."""

    dictionary = load_dictionary()
    objects = load_objects()

    rows = [
        suggest(
            description,
            dictionary,
            objects=objects,
        )
        for description in descriptions
    ]

    return pd.DataFrame(
        rows,
        index=descriptions.index,
    )


# ---------------------------------------------------------------------------
# AVALIAÇÃO HISTÓRICA
# ---------------------------------------------------------------------------

def evaluate(
    history: pd.DataFrame,
    dictionary: dict | None = None,
) -> dict:
    """Compara classes sugeridas com as classes históricas, sem score nem treino."""

    dictionary = _dictionary_from_rules(
        dictionary
    )

    rows = []

    for _, record in history.iterrows():
        actual = record.get(
            "Classificação"
        )

        if (
            pd.isna(actual)
            or not str(actual).strip()
            or str(actual).strip() == "#N/A"
        ):
            continue

        result = classify(
            record.get(
                "Descrição detalhada"
            ),
            dictionary,
        )

        rows.append(
            {
                "real": str(actual).strip(),
                "motor": result[
                    "classificacao"
                ],
                "status": result[
                    "status"
                ],
                "intencao": result[
                    "intencao_id"
                ],
            }
        )

    frame = pd.DataFrame(
        rows
    )

    if frame.empty:
        frame = pd.DataFrame(
            columns=[
                "real",
                "motor",
                "status",
                "intencao",
            ]
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
                == "Sem correspondência"
            ).sum()
        ),
        "ambiguos": int(
            (
                frame["status"]
                == "Ambígua"
            ).sum()
        ),
        "acertos": correct,
        "acuracia_entre_respostas": (
            round(
                correct
                / len(answered),
                4,
            )
            if len(answered)
            else None
        ),
        "por_classificacao": {
            name: {
                "total": int(
                    (
                        frame["real"]
                        == name
                    ).sum()
                ),
                "respondidos": int(
                    (
                        answered["motor"]
                        == name
                    ).sum()
                ),
                "corretos": int(
                    (
                        (
                            answered["real"]
                            == name
                        )
                        & (
                            answered["motor"]
                            == name
                        )
                    ).sum()
                ),
            }
            for name in sorted(
                frame["real"].unique()
            )
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    dictionary = load_dictionary()

    history = load_compilado_sheet(
        TEMPLATE_PATH
    )

    result = evaluate(
        history,
        dictionary,
    )

    answered = result[
        "com_resposta"
    ]

    print(
        f"Intenções no dicionário: "
        f"{len(dictionary['intencoes'])}"
    )

    print(
        f"Históricos avaliados: "
        f"{result['total']}"
    )

    print(
        f"Cobertura: "
        f"{answered}/{result['total']}"
    )

    print(
        f"Sem correspondência: "
        f"{result['sem_correspondencia']}"
    )

    print(
        f"Ambíguos: "
        f"{result['ambiguos']}"
    )

    if answered:
        print(
            f"Acerto de classe no histórico: "
            f"{result['acertos']}/{answered} "
            f"({result['acuracia_entre_respostas']:.1%})"
        )

    print(
        "\nPor classificação "
        "(total | respondidos | corretos):"
    )

    for name, data in result[
        "por_classificacao"
    ].items():
        print(
            f"  {data['total']:>4} | "
            f"{data['respondidos']:>4} | "
            f"{data['corretos']:>4}"
        )