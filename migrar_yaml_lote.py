"""Migração do YAML (lote 157): G5, G6, código diferente e cancelamento + das nf.

Uso (raiz do projeto):  python migrar_yaml_lote.py [caminho_do_yaml]
- Acrescenta padrões nas 4 intenções abaixo (idempotente).
- Troca a exclusão ampla de INT_PAG_VENCIMENTO por exclusões estreitas.
- Remove a precedência INT_CON_CANCELAMENTO > INT_NF_CANCEL_REEMISSAO, se existir.
- Valida (ids de precedência, duplicatas após a normalização do motor, causa -> uma classe),
  faz backup com timestamp e salva. Aborta sem gravar se algo falhar.
"""
import sys
from datetime import datetime
from pathlib import Path
from shutil import copy2

import yaml

sys.path.insert(0, "src")  # roda da raiz do projeto
from root_cause_engine import normalize_text  # mesma normalização do motor

DEFAULT = Path("data/input/dicionario_aizen_intencoes.yaml")

PADROES = {
    # G5
    "INT_NF_DATA_EMISSAO": [
        "emissão no final", "alteração na data de emissão", "alteração da data de emissão",
        "alterar a data de emissão", "mudar a data de emissão",
    ],
    # G6
    "INT_PAG_VENCIMENTO": ["prorrogar + vencimento"],
    # G4
    "INT_NF_CORRECAO_CODIGO": ["código diferente"],
    "INT_NF_CANCEL_REEMISSAO": ["cancelamento + das nf"],
}

# G6: a exclusão 'data de emissão da nf' derrubava pedidos de vencimento que só citam a data de emissão
EXCLUSAO_ANTIGA = ("INT_PAG_VENCIMENTO", "data de emissão da nf")
EXCLUSOES_NOVAS = [
    "alterar data de emissão da nf", "mudar data de emissão da nf",
    "alterar a data de emissão", "mudar a data de emissão",
    "alteração na data de emissão", "alteração da data de emissão",
]

PRECEDENCIA_REMOVER = ("INT_CON_CANCELAMENTO", ["INT_NF_CANCEL_REEMISSAO"])


def _chave(padrao: str) -> str:
    return " + ".join(sorted(normalize_text(parte) for parte in padrao.split("+")))


def migrar(d: dict) -> list[str]:
    log = []
    por_id = {i["id"]: i for i in d["intencoes"]}

    for iid, novos in PADROES.items():
        if iid not in por_id:
            raise ValueError(f"Intenção inexistente: {iid}")
        atuais = por_id[iid].setdefault("padroes", [])
        existentes = {_chave(a) for a in atuais}
        for p in novos:
            if _chave(p) not in existentes:
                atuais.append(p)
                existentes.add(_chave(p))
                log.append(f"+ {iid}: {p!r}")

    iid, antiga = EXCLUSAO_ANTIGA
    exclusoes = por_id[iid].setdefault("exclusoes", [])
    if antiga in exclusoes:
        exclusoes.remove(antiga)
        log.append(f"- {iid} exclusão: {antiga!r}")
    for e in EXCLUSOES_NOVAS:
        if e not in exclusoes:
            exclusoes.append(e)
            log.append(f"+ {iid} exclusão: {e!r}")

    preferir, sobre = PRECEDENCIA_REMOVER
    antes = len(d["precedencia"])
    d["precedencia"] = [
        r for r in d["precedencia"] if not (r["preferir"] == preferir and r["sobre"] == sobre)
    ]
    if len(d["precedencia"]) < antes:
        log.append(f"- precedência: {preferir} > {sobre}")

    # validações (as mesmas do evoluir_dicionario.py)
    erros = []
    for r in d["precedencia"]:
        for alvo in [r["preferir"], *r.get("sobre", [])]:
            if alvo not in por_id:
                erros.append(f"  {alvo!r} (regra preferir={r['preferir']!r})")
    if erros:
        raise ValueError("Precedência aponta para intenção inexistente:\n" + "\n".join(erros))

    donos = {}
    for i in d["intencoes"]:
        for p in i.get("padroes", []):
            donos.setdefault(_chave(p), {}).setdefault(i["id"], p)
    dup = {k: v for k, v in donos.items() if len(v) > 1}
    if dup:
        linhas = "\n".join(f"  {sorted(v.values())}: {sorted(v)}" for v in dup.values())
        raise ValueError("Padrão em mais de uma intenção (remova a cópia errada no YAML):\n" + linhas)

    permitidas = set(d.get("classes_permitidas", []))
    causa_classe = {}
    for i in d["intencoes"]:
        if permitidas and i["classificacao"] not in permitidas:
            raise ValueError(f"classe fora do contrato: {i['id']}")
        if causa_classe.setdefault(i["causa_padrao"], i["classificacao"]) != i["classificacao"]:
            raise ValueError(f"causa com duas classes: {i['causa_padrao']}")
    return log


if __name__ == "__main__":
    caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    dic = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    log = migrar(dic)
    if not log:
        print("Nada a migrar (YAML já está atualizado).")
        sys.exit(0)
    copy2(caminho, caminho.with_name(f"{caminho.name}.{datetime.now():%Y%m%d_%H%M%S}.bak"))
    caminho.write_text(yaml.safe_dump(dic, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    print("\n".join(log))
