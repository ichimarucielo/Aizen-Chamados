import pandas as pd
import pytest

import mvp_pilot as pilot
from root_cause_engine import load_dictionary


@pytest.fixture
def scenario(monkeypatch):
    dictionary = load_dictionary()
    classes = dictionary['classes_permitidas']
    manifest = {'versao': 'rc-test', 'chamados_calibracao': ['old']}
    monkeypatch.setattr(pilot, 'version_id', lambda _: 'rc-test')
    rows = [{pilot.ID: str(i), 'Versão': 'rc-test', 'Coorte': 'Nova',
             'Classificação Sugerida': label, 'Status da Sugestão': 'Sugerida',
             'Regra Sugerida': 'rule-' + str(i), 'Score Confiança': None,
             **{column: '' for column in pilot.MANUAL}} for i, label in enumerate(classes)]
    for identifier, status in [('amb', 'Ambígua'), ('none', 'Sem correspondência')]:
        rows.append({**rows[0], pilot.ID: identifier, 'Classificação Sugerida': '',
                     'Status da Sugestão': status})
    snapshot = pd.DataFrame(rows)
    reviews = snapshot.copy()
    reviews['Classificação Validada'] = [*classes, classes[0], 'Fora do escopo']
    reviews['Revisor N2'] = 'Revisor real'
    reviews['Data da Revisão'] = '2026-01-01'
    reviews['Gravidade'] = 'Nenhum'
    criteria = dict(aprovado_por='N2', aprovado_em='2026-01-01', minimo_novos_revisados=8,
                    minimo_por_classe=1, concordancia_geral=.9, concordancia_por_classe=.8,
                    minimo_ambiguos_revisados=1, minimo_sem_sugestao_revisados=1,
                    maximo_erros_criticos=0)
    return snapshot, reviews, manifest, criteria, classes


def test_acceptance_requires_complete_new_reviews(scenario):
    report = pilot.evaluate_pilot(*scenario)
    assert report['impedimentos'] == []
    assert report['metricas_novos']['concordancia_classificacao'] == 1
    assert report['novos_revisados'] == 8


def test_calibration_cannot_be_relabelled_as_new(scenario):
    snapshot, reviews, manifest, criteria, classes = scenario
    manifest['chamados_calibracao'] = snapshot[pilot.ID].tolist()
    report = pilot.evaluate_pilot(snapshot, reviews, manifest, criteria, classes)
    assert report['novos_revisados'] == 0
    assert report['retrospectivos_revisados'] == 8
    assert report['estado'] == 'PENDENTE'


@pytest.mark.parametrize('field,value', [('Revisor N2', ''), ('Data da Revisão', '2099-01-01'),
                                        ('Classificação Validada', 'Inventada'), ('Gravidade', '')])
def test_incomplete_review_does_not_count(scenario, field, value):
    snapshot, reviews, manifest, criteria, classes = scenario
    reviews.loc[0, field] = value
    report = pilot.evaluate_pilot(snapshot, reviews, manifest, criteria, classes)
    assert report['revisados'] == 7
    assert report['estado'] == 'PENDENTE'


def test_disagreement_by_rule_and_class_uses_frozen_suggestion(scenario):
    snapshot, reviews, manifest, criteria, classes = scenario
    reviews.loc[0, 'Classificação Validada'] = classes[1]
    reviews.loc[0, 'Classificação Sugerida'] = classes[1]  # edited sheet is ignored
    report = pilot.evaluate_pilot(snapshot, reviews, manifest, criteria, classes)
    assert report['metricas_novos']['discordancias'] == 1
    assert report['metricas_novos']['erros_por_regra']['rule-0']['erros'] == 1
    assert report['matriz_confusao'][classes[1]][classes[0]] == 1


def test_critical_errors_and_unapproved_criteria_block(scenario):
    snapshot, reviews, manifest, criteria, classes = scenario
    criteria['aprovado_por'] = ''
    reviews.loc[0, 'Gravidade'] = 'Crítico'
    report = pilot.evaluate_pilot(snapshot, reviews, manifest, criteria, classes)
    assert report['estado'] == 'PENDENTE'
    assert any('aprovados' in item for item in report['impedimentos'])
    assert report['erros_criticos'] == 1


@pytest.mark.parametrize('change', ['duplicate', 'missing', 'version'])
def test_review_identity_is_strict(scenario, change):
    snapshot, reviews, manifest, criteria, classes = scenario
    if change == 'duplicate':
        reviews = pd.concat([reviews, reviews.iloc[[0]]])
    elif change == 'missing':
        reviews = reviews.iloc[1:]
    else:
        reviews.loc[0, 'Versão'] = 'different'
    with pytest.raises(ValueError):
        pilot.evaluate_pilot(snapshot, reviews, manifest, criteria, classes)


def test_prepare_classifies_all_rows_and_marks_known_ids():
    rules = load_dictionary()
    frame = pd.DataFrame({pilot.ID: [101, 102], 'Descrição detalhada': ['Quero cancelar a nota fiscal', 'xyz']})
    result = pilot.prepare_pilot(frame, {'versao': 'test', 'chamados_calibracao': ['101']}, rules)
    assert result['Coorte'].tolist() == ['Retrospectiva', 'Nova']
    assert result['Status da Sugestão'].tolist() == ['Sugerida', 'Sem correspondência']
    assert result.loc[0, 'Objeto Operacional Sugerido']
    assert result[pilot.MANUAL].eq('').all().all()


def test_prepare_rejects_duplicate_ids():
    with pytest.raises(ValueError):
        pilot.prepare_pilot(pd.DataFrame({pilot.ID: [1, 1]}),
                            {'versao': 'test', 'chamados_calibracao': []}, load_dictionary())


def test_changed_source_blocks_acceptance(scenario, monkeypatch):
    monkeypatch.setattr(pilot, 'version_id', lambda _: 'different-code')
    report = pilot.evaluate_pilot(*scenario)
    assert any('congelamento' in item for item in report['impedimentos'])


def test_optional_review_time_keeps_old_forms_compatible(scenario):
    report = pilot.evaluate_pilot(*scenario)
    assert report['esforco_revisao']['minutos_total'] is None


def test_review_time_excludes_invalid_values_and_calibration(scenario):
    snapshot, reviews, manifest, criteria, classes = scenario
    reviews[pilot.REVIEW_TIME] = ['1,5', '2', 'erro', '-1', 'inf', '', '4', '3']
    manifest['chamados_calibracao'] = ['0']
    report = pilot.evaluate_pilot(snapshot, reviews, manifest, criteria, classes)
    assert report['esforco_revisao']['novos_com_tempo_registrado'] == 3
    assert report['esforco_revisao']['minutos_total'] == 9
    assert report['esforco_revisao']['tempos_invalidos'] == 3
