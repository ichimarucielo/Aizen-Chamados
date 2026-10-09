"""Snapshot local verificável; aceite operacional é registrado separadamente."""

import hashlib
import argparse
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files(base: Path = BASE_DIR) -> list[Path]:
    files = [*base.joinpath('src').glob('*.py'), *base.joinpath('tests').glob('*.py')]
    files += [base / 'README.md', base / 'requirements.txt']
    files += list(base.glob('*.ini'))
    files += list(base.glob('*contract*.md'))
    files += list(base.joinpath('data/input').glob('*.yaml'))
    files += list(base.joinpath('docs').glob('*.md'))
    return sorted(path for path in files if path.is_file())


def source_hashes(base: Path = BASE_DIR) -> dict[str, str]:
    return {p.relative_to(base).as_posix(): sha256(p) for p in source_files(base)}


def version_id(hashes: dict[str, str]) -> str:
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return f'mvp1-rc-{digest[:12]}'


def freeze(output: Path, baseline_ids: list[str], evidence: dict) -> dict:
    hashes = source_hashes()
    manifest = {
        'versao': version_id(hashes),
        'estado': 'CANDIDATA — aceite N2 pendente',
        'criado_em': datetime.now(timezone.utc).isoformat(),
        'arquivos_sha256': hashes,
        'chamados_calibracao': sorted(set(baseline_ids)),
        'evidencias_tecnicas': evidence,
    }
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / 'manifesto.json'
    if manifest_path.exists():
        raise FileExistsError('Snapshot existente; escolha outro diretório para preservar evidências.')
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    with zipfile.ZipFile(output / 'codigo_dicionario.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in hashes:
            archive.write(BASE_DIR / name, name)
        archive.write(manifest_path, 'manifesto.json')
        dependencies = evidence.get('dependencias', {})
        if dependencies:
            archive.writestr('requirements.lock.txt', ''.join(
                f'{name}=={version}\n' for name, version in sorted(dependencies.items())))
    return manifest


def main() -> None:
    from extract import load_compilado_sheet, load_salesforce
    from mvp_pilot import ID, ticket_id

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saida', type=Path, required=True)
    parser.add_argument('--evidencias', type=Path, required=True)
    args = parser.parse_args()
    paths = [BASE_DIR / 'data/input/plano_n2_template.xlsx',
             BASE_DIR / 'data/output/plano_n2_gerado.xlsx']
    baseline = load_salesforce(BASE_DIR / 'data/input/monitoramento.xlsx')[ID].map(ticket_id).tolist()
    for path in paths:
        if path.exists():
            baseline.extend(load_compilado_sheet(path)[ID].map(ticket_id).tolist())
    evidence = json.loads(args.evidencias.read_text(encoding='utf-8'))
    print(freeze(args.saida, [value for value in baseline if value], evidence)['versao'])


if __name__ == '__main__':
    main()
