"""Normalização e evidência textual compartilhadas pelo motor determinístico."""

import re
import unicodedata
from typing import Any

import pandas as pd

from parse_description import normalize_description


def normalize_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKD", normalize_description(str(value)).lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[\w.+-]+@[\w.-]+\.\w+", " email ", text)
    text = re.sub(r"\be-mail\b", "email", text)
    text = re.sub(
        r"\bnotas?(?:\s+fisc(?:al|ais))?\b|\bnf'?s\b|\bnfs\b|\bnf-?e\b|\bnfs-?e\b",
        " nf ", text,
    )
    # Só normaliza quantidades imediatamente antes de documentos financeiros.
    for number, word in (("2", "dois"), ("3", "tres")):
        text = re.sub(rf"\b{number}(?=\s+(?:nf|boletos?)\b)", word, text)
    text = re.sub(r"\bduas(?=\s+nf\b)", "dois", text)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _concept_spans(text: str, vocabulary: dict) -> list[tuple[int, int, str]]:
    spans = set()
    for concept, aliases in vocabulary.items():
        for alias in aliases:
            phrase = normalize_text(alias)
            if phrase:
                for match in re.finditer(rf"\b{re.escape(phrase)}\b", text):
                    spans.add((match.start(), match.end(), concept))
    return sorted(spans)


def remove_negated_requests(value: Any, vocabulary: dict) -> str:
    """Preserva limites de frases ao remover pedidos explicitamente negados."""
    # A vírgula separa pedidos somente quando inicia uma solicitação explícita.
    # Não separar 'nem reemitir' ou 'não reenviar': a negativa continua valendo.
    affirmative = r"(?:s[oó]|apenas|somente|mas|por[eé]m|favor|solicito|quero|preciso|reenviar|enviar|alterar|atualizar|prorrogar|consultar|verificar)\b"
    segments = re.split(rf"[;!?\n]|\.(?=\s|$)|,(?=\s*{affirmative})",
                        normalize_description(value), flags=re.IGNORECASE)
    return ". ".join(
        filtered for segment in segments
        if (filtered := _remove_negated_segment(normalize_text(segment), vocabulary))
    )


def _remove_negated_segment(text: str, vocabulary: dict) -> str:
    """Preserva 'não recebi' e 'não reconheço', que são evidências positivas."""
    aliases = {
        normalize_text(alias)
        for concept in ("CANCELAR", "SUBSTITUIR", "REEMITIR", "BAIXAR", "SUSPENDER")
        for alias in vocabulary.get("acoes", {}).get(concept, [])
    }
    aliases.update({"reenviar", "enviar", "alterar", "atualizar", "prorrogar", "estornar"})
    verbs = "|".join(re.escape(alias) for alias in sorted(aliases, key=len, reverse=True))
    if not verbs:
        return text
    text = re.sub(
        rf"\b(?:{verbs})\b(?:(?!\b(?:{verbs})\b).)*?\be (?:so|apenas) contexto\b",
        " ", text,
    )
    negation = rf"\b(?:nao\s+(?:(?:quero|queremos|preciso|precisamos|deve|devem|solicito|solicitamos|desejo|desejamos)\s+)?|sem\s+)(?:{verbs})\b"
    # Uma segunda solicitação explícita pode usar verbos sem assinatura cadastrada.
    request_verbs = rf"{verbs}|reenviar|enviar|alterar|atualizar|prorrogar|consultar|verificar"
    boundary = rf"(?=\b(?:mas|porem|contudo|so|apenas|somente)\b|\be\s+(?:sim\s+)?(?:{request_verbs})\b|$)"
    return re.sub(r"\s+", " ", re.sub(negation + r".*?" + boundary, " ", text)).strip()


def action_object_scopes(text: str, vocabulary: dict) -> list[dict[str, set[str]]]:
    """Liga cada ação aos objetos seguintes, encerrando antes de contexto ou outra ação."""
    scopes = [scope for segment in re.split(r"[.;!?\n]", text)
              for scope in _segment_action_object_scopes(normalize_text(segment), vocabulary)]
    normalized = normalize_text(text)
    objects = _concept_spans(normalized, vocabulary.get("objetos", {}))
    # 'Cancelamento do mesmo' retoma um objeto anterior; não deixar apenas
    # o objeto do assunto prevalecer sobre uma solicitação no corpo do chamado.
    for start, end, action in _concept_spans(normalized, vocabulary.get("acoes", {})):
        if not re.match(r"\s+(?:do mesmo|da mesma|deste|desta|desse|dessa)\b", normalized[end:]):
            continue
        previous = [(stop, obj) for _, stop, obj in objects if stop <= start]
        if previous:
            stop, obj = max(previous)
            if len(normalized[stop:start].split()) <= 50:
                scopes.append({"acoes": {action}, "objetos": {obj}})
    return scopes


def _segment_action_object_scopes(text: str, vocabulary: dict) -> list[dict[str, set[str]]]:
    actions = _concept_spans(text, vocabulary.get("acoes", {}))
    objects = _concept_spans(text, vocabulary.get("objetos", {}))
    scopes = []
    for start, end, action in actions:
        next_action = min((a for a, _, _ in actions if a >= end), default=len(text))
        targets = set()
        previous_end = end
        for obj_start, obj_end, obj in objects:
            if obj_start < end or obj_start >= next_action:
                continue
            bridge = text[previous_end:obj_start].strip()
            if re.search(r"\b(?:referente|porque|por|devido|apos|sobre)\b", bridge):
                break
            if targets and bridge and not re.fullmatch(r"(?:e|ou|a|o|as|os|da|do|das|dos|emitida|emitido|\s)+", bridge):
                break
            if len(bridge.split()) > 8:
                break
            targets.add(obj)
            previous_end = max(previous_end, obj_end)
        if targets:
            scopes.append({"acoes": {action}, "objetos": targets})
    return scopes
