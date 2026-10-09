"""Piloto reprodutível e aceite baseado exclusivamente na revisão humana."""

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from classification_input import build_classification_input
from extract import load_salesforce
from mvp_release import BASE_DIR, sha256, source_hashes, version_id
from root_cause_engine import load_dictionary, load_objects, suggest
from validation_analysis import evaluate_validations

ID = 'Número do Chamado'
MANUAL = ['Classificação Validada', 'Objeto Operacional Validado', 'Revisor N2',
          'Data da Revisão', 'Gravidade', 'Observação N2']
REVIEW_TIME = 'Tempo de Revisão Minutos'


def ticket_id(value) -> str:
    if pd.isna(value):
        return ''
    value = str(value).strip()
    return value[:-2] if value.endswith('.0') else value


def prepare_pilot(frame: pd.DataFrame, manifest: dict, rules: dict) -> pd.DataFrame:
    """Inclui todo o lote, sem seleção por resultado; calibração não conta como novo."""
    ids = frame[ID].map(ticket_id)
    if (ids == '').any() or ids.duplicated().any():
        raise ValueError('Chamados devem ter identificadores únicos e preenchidos.')
    known = set(manifest['chamados_calibracao'])
    objects = load_objects()
    rows = []
    for identifier, text in zip(ids, build_classification_input(frame)):
        result = suggest(text, rules=rules, objects=objects)
        rows.append({
            ID: identifier, 'Versão': manifest['versao'],
            'Coorte': 'Retrospectiva' if identifier in known else 'Nova',
            'Texto Operacional': text,
            'Classificação Sugerida': result.get('classificacao') or '',
            'Objeto Operacional Sugerido': result.get('objeto_operacional') or '',
            'ID Causa Padrão': result.get('causa_id') or '',
            'Regra Sugerida': result.get('regra') or '',
            'Motivo da Decisão': result.get('reason_code') or '',
            'Status da Sugestão': 'Ambígua' if result.get('ambiguo') else
                'Sugerida' if result.get('classificacao') else 'Sem correspondência',
            'Score Confiança': None,
            **{column: '' for column in MANUAL},
            REVIEW_TIME: '',
        })
    return pd.DataFrame(rows)


def valid_date(value) -> bool:
    try:
        parsed = date.fromisoformat(str(value)[:10])
        return parsed <= date.today()
    except (TypeError, ValueError):
        return False


def evaluate_pilot(snapshot: pd.DataFrame, reviews: pd.DataFrame,
                   manifest: dict, criteria: dict, classes: list[str]) -> dict:
    """Usa sugestões do snapshot; nunca confia nas sugestões editadas na ficha."""
    if reviews[ID].map(ticket_id).duplicated().any():
        raise ValueError('Há chamados duplicados na revisão.')
    if snapshot[ID].map(ticket_id).duplicated().any():
        raise ValueError('Há chamados duplicados no snapshot.')
    left = snapshot.drop(columns=MANUAL, errors='ignore').copy()
    right = reviews[[ID, 'Versão', *MANUAL]].fillna('').copy()
    right[REVIEW_TIME] = reviews.get(REVIEW_TIME, pd.Series('', index=reviews.index)).fillna('')
    left[ID] = left[ID].map(ticket_id)
    right[ID] = right[ID].map(ticket_id)
    if set(right[ID]) != set(left[ID]):
        raise ValueError('A revisão deve conter exatamente os chamados do snapshot.')
    if not (right['Versão'] == manifest['versao']).all():
        raise ValueError('Revisão de outra versão; gere um novo piloto.')
    if not (left['Versão'] == manifest['versao']).all():
        raise ValueError('Snapshot de outra versão.')
    work = left.drop(columns=REVIEW_TIME, errors='ignore').merge(
        right.drop(columns='Versão'), on=ID, validate='one_to_one')
    complete = (work['Classificação Validada'].isin([*classes, 'Fora do escopo'])
                & work['Revisor N2'].str.strip().ne('')
                & work['Data da Revisão'].map(valid_date)
                & work['Gravidade'].isin(['Nenhum', 'Leve', 'Crítico']))
    reviewed = work[complete].copy()
    # Coorte é recalculada pela lista congelada, não pelo campo editável da ficha.
    new = reviewed[~reviewed[ID].isin(manifest['chamados_calibracao'])].copy()
    metrics = evaluate_validations(new)
    blocks = []
    if not criteria.get('aprovado_por', '').strip() or not valid_date(criteria.get('aprovado_em')):
        blocks.append('Critérios ainda não aprovados pelo N2.')
    if version_id(source_hashes()) != manifest['versao']:
        blocks.append('Código/dicionário/critérios alterados após o congelamento.')
    if len(new) < criteria['minimo_novos_revisados']:
        blocks.append('Amostra de chamados novos revisados insuficiente.')
    expected_new = int((~work[ID].isin(manifest['chamados_calibracao'])).sum())
    if len(new) != expected_new:
        blocks.append('Há revisões incompletas ou inválidas.')
    total_rate = metrics['concordancia_classificacao']
    if total_rate is None or total_rate < criteria['concordancia_geral']:
        blocks.append('Concordância geral insuficiente ou ainda não medida.')
    for label in classes:
        predicted = metrics['precisao_por_classificacao'].get(label, {})
        gold = metrics['cobertura_por_classificacao_validada'].get(label, {})
        if min(predicted.get('validadas', 0), gold.get('rotulados_pelo_n2', 0)) < criteria['minimo_por_classe']:
            blocks.append(f'Amostra por classe insuficiente: {label}.')
        if predicted.get('concordancia') is None or predicted['concordancia'] < criteria['concordancia_por_classe']:
            blocks.append(f'Concordância por classe insuficiente: {label}.')
    for status, key in [('Ambígua', 'minimo_ambiguos_revisados'),
                        ('Sem correspondência', 'minimo_sem_sugestao_revisados')]:
        if int((new['Status da Sugestão'] == status).sum()) < criteria[key]:
            blocks.append(f'Revisão insuficiente de casos: {status}.')
    critical = int((new['Gravidade'] == 'Crítico').sum())
    if critical > criteria['maximo_erros_criticos']:
        blocks.append('Erros críticos acima do limite.')
    labeled = new.assign(predita=new['Classificação Sugerida'].replace('', 'Sem sugestão'))
    confusion = pd.crosstab(labeled['Classificação Validada'], labeled['predita']).to_dict(orient='index')
    errors = new[(new['Status da Sugestão'] == 'Sugerida') &
                 (new['Classificação Sugerida'] != new['Classificação Validada'])]
    times = pd.to_numeric(new[REVIEW_TIME].astype(str).str.replace(',', '.', regex=False), errors='coerce')
    valid_times = times[times.gt(0) & times.lt(float('inf'))]
    invalid_times = int((new[REVIEW_TIME].astype(str).str.strip().ne('') &
                         ~times.index.isin(valid_times.index)).sum())
    return {
        'versao': manifest['versao'], 'estado': 'APTO PARA ACEITE N2' if not blocks else 'PENDENTE',
        'impedimentos': blocks, 'total': len(work), 'revisados': len(reviewed),
        'novos_revisados': len(new), 'retrospectivos_revisados': len(reviewed) - len(new),
        'novos_no_lote': expected_new,
        'erros_criticos': critical, 'metricas_novos': metrics,
        'esforco_revisao': {
            'novos_com_tempo_registrado': len(valid_times), 'tempos_invalidos': invalid_times,
            'minutos_total': round(float(valid_times.sum()), 2) if len(valid_times) else None,
            'minutos_media': round(float(valid_times.mean()), 2) if len(valid_times) else None,
            'minutos_mediana': round(float(valid_times.median()), 2) if len(valid_times) else None,
            'observacao': 'Tempo declarado pelo N2; sem baseline não comprova economia de tempo.',
        },
        'matriz_confusao': confusion,
        'discordancias': errors[[ID, 'Classificação Sugerida', 'Classificação Validada',
                                'Regra Sugerida', 'Gravidade', 'Observação N2']].to_dict('records'),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifesto', type=Path, required=True)
    parser.add_argument('--entrada', type=Path)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--revisao', type=Path)
    parser.add_argument('--relatorio', type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifesto.read_text(encoding='utf-8'))
    dictionary = load_dictionary()
    if args.revisao:
        receipt = json.loads(args.snapshot.with_suffix('.meta.json').read_text(encoding='utf-8'))
        if receipt['sha256'] != sha256(args.snapshot) or receipt['versao'] != manifest['versao']:
            raise ValueError('Snapshot alterado ou de outra versão; preserve as sugestões congeladas.')
        snapshot = pd.read_csv(args.snapshot, keep_default_na=False, dtype=str)
        if args.revisao.suffix.lower() == '.xlsx':
            reviews = pd.read_excel(args.revisao, sheet_name='Revisão N2', header=6,
                                    keep_default_na=False, dtype=str)
        else:
            reviews = pd.read_csv(args.revisao, keep_default_na=False, dtype=str)
        criteria = yaml.safe_load((BASE_DIR / 'data/input/criterios_mvp.yaml').read_text(encoding='utf-8'))
        report = evaluate_pilot(snapshot, reviews, manifest, criteria, dictionary['classes_permitidas'])
        if not args.relatorio:
            parser.error('--relatorio é obrigatório para avaliar.')
        args.relatorio.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(report['estado'])
    else:
        if not args.entrada:
            parser.error('--entrada é obrigatório para preparar.')
        if version_id(source_hashes()) != manifest['versao']:
            raise ValueError('Fontes divergentes do manifesto; congele uma nova candidata.')
        pilot = prepare_pilot(load_salesforce(args.entrada), manifest, dictionary)
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        pilot.to_csv(args.snapshot, index=False, encoding='utf-8-sig')
        args.snapshot.with_suffix('.meta.json').write_text(json.dumps({
            'versao': manifest['versao'], 'sha256': sha256(args.snapshot),
            'entrada_sha256': sha256(args.entrada),
        }, indent=2), encoding='utf-8')
        print(pilot.groupby(['Coorte', 'Status da Sugestão']).size().to_string())


if __name__ == '__main__':
    main()
